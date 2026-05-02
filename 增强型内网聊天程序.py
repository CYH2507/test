import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog, ttk, filedialog
import time
import json
import os
from datetime import datetime
import hashlib

class ChatServer:
    def __init__(self, host='localhost', port=12345, admin_password='admin123'):
        self.host = host
        self.port = port
        self.admin_password = admin_password
        self.clients = {}  # {client_socket: {'username': str, 'is_admin': bool, 'address': tuple}}
        self.server_socket = None
        self.gui = None
        self.lock = threading.Lock()
        self.banned_users = set()  # 存储被封禁的用户名
        self.muted_users = set()   # 存储被静音的用户名
        self.chat_history = []     # 服务器端存储聊天历史
        
    def set_gui(self, gui):
        self.gui = gui
        
    def log(self, message, level="info"):
        """线程安全的日志记录"""
        if self.gui:
            self.gui.root.after(0, lambda: self.gui.display_message(message, level))
    
    def start_server(self):
        """启动服务器"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.log(f"✅ 服务器启动，监听 {self.host}:{self.port} | 管理员密码: {self.admin_password}", "server")
            
            while True:
                client_socket, client_address = self.server_socket.accept()
                self.log(f"🔌 新连接: {client_address}", "info")
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket, client_address))
                client_thread.daemon = True
                client_thread.start()
                
        except Exception as e:
            self.log(f"❌ 服务器错误: {e}", "error")
        finally:
            if self.server_socket:
                self.server_socket.close()
    
    def handle_client(self, client_socket, client_address):
        """处理客户端连接"""
        try:
            # 接收认证信息 (JSON格式: {"username": "...", "password": "..."})
            auth_data = client_socket.recv(1024).decode('utf-8')
            try:
                auth = json.loads(auth_data)
                username = auth.get('username', '').strip()
                password = auth.get('password', '')
            except:
                client_socket.send(json.dumps({"status": "error", "message": "无效认证格式"}).encode())
                client_socket.close()
                return
            
            if not username:
                client_socket.send(json.dumps({"status": "error", "message": "用户名不能为空"}).encode())
                client_socket.close()
                return
            
            # 检查是否被封禁
            if username in self.banned_users:
                client_socket.send(json.dumps({"status": "error", "message": "您已被封禁，无法加入聊天室"}).encode())
                client_socket.close()
                return
            
            # 验证管理员
            is_admin = False
            if username.lower() == "admin" and password == self.admin_password:
                is_admin = True
                self.log(f"🛡️ 管理员 {username} 已认证", "admin")
            elif username.lower() == "admin" and password != self.admin_password:
                client_socket.send(json.dumps({"status": "error", "message": "管理员密码错误"}).encode())
                client_socket.close()
                return
            
            # 检查用户名是否已存在
            with self.lock:
                for info in self.clients.values():
                    if info['username'] == username and not (is_admin and username.lower() == "admin"):
                        client_socket.send(json.dumps({"status": "error", "message": "用户名已存在"}).encode())
                        client_socket.close()
                        return
                
                # 添加客户端
                self.clients[client_socket] = {'username': username, 'is_admin': is_admin, 'address': client_address}
            
            # 发送认证成功响应
            client_socket.send(json.dumps({
                "status": "success", 
                "username": username,
                "is_admin": is_admin,
                "welcome": f"{'🛡️ 管理员模式' if is_admin else '👤 普通用户'} | 欢迎 {username}!",
                "history": self.chat_history[-50:]  # 发送最近50条消息
            }).encode())
            
            self.log(f"✅ {username}{'(管理员)' if is_admin else ''} 加入聊天室", "info")
            self.broadcast_system_message(f"{username} 加入了聊天室", exclude=client_socket)
            
            # 主消息循环
            while True:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                
                try:
                    msg = json.loads(data)
                    msg_type = msg.get('type', 'chat')
                    content = msg.get('content', '').strip()
                    
                    if msg_type == 'chat' and content:
                        # 检查是否被静音
                        user_info = self.clients.get(client_socket, {})
                        if user_info['username'] in self.muted_users and not user_info.get('is_admin', False):
                            client_socket.send(json.dumps({
                                "type": "system", 
                                "message": "您已被静音，无法发送消息"
                            }).encode())
                            continue
                        
                        # 处理管理员命令
                        if user_info.get('is_admin', False) and content.startswith('/'):
                            self.handle_admin_command(client_socket, user_info['username'], content)
                        else:
                            # 普通消息广播
                            self.broadcast_message(user_info['username'], content, user_info.get('is_admin', False))
                    elif msg_type == 'heartbeat':
                        client_socket.send(json.dumps({"type": "heartbeat", "status": "ok"}).encode())
                    elif msg_type == 'file':
                        filename = msg.get('filename', '')
                        file_size = msg.get('size', 0)
                        file_data = msg.get('data', '')
                        self.broadcast_file(user_info['username'], filename, file_data, file_size)
                        
                except json.JSONDecodeError:
                    # 兼容旧格式消息
                    if content:
                        user_info = self.clients.get(client_socket, {})
                        self.broadcast_message(user_info['username'], content, user_info.get('is_admin', False))
                        
        except ConnectionResetError:
            pass
        except Exception as e:
            self.log(f"⚠️ 客户端处理错误 {client_address}: {e}", "error")
        finally:
            self.remove_client(client_socket)
    
    def handle_admin_command(self, admin_socket, admin_name, command):
        """处理管理员命令"""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd == '/kick' and args:
            target_user = args.strip()
            kicked = False
            with self.lock:
                for sock, info in list(self.clients.items()):
                    if info['username'] == target_user and sock != admin_socket:
                        try:
                            sock.send(json.dumps({
                                "type": "system",
                                "message": f"⚠️ 您已被管理员 {admin_name} 踢出聊天室"
                            }).encode())
                            sock.close()
                        except:
                            pass
                        kicked = True
                        self.log(f"👢 管理员 {admin_name} 踢出了 {target_user}", "admin")
                        break
            
            if kicked:
                self.broadcast_system_message(f"🛡️ 管理员 {admin_name} 踢出了 {target_user}")
                admin_socket.send(json.dumps({
                    "type": "system", 
                    "message": f"✅ 已踢出用户: {target_user}"
                }).encode())
            else:
                admin_socket.send(json.dumps({
                    "type": "system", 
                    "message": f"❌ 未找到用户: {target_user}"
                }).encode())
                
        elif cmd == '/ban' and args:
            target_user = args.strip()
            with self.lock:
                if target_user in [info['username'] for info in self.clients.values()]:
                    self.banned_users.add(target_user)
                    # 踢出当前在线的被封禁用户
                    for sock, info in list(self.clients.items()):
                        if info['username'] == target_user:
                            try:
                                sock.send(json.dumps({
                                    "type": "system",
                                    "message": f"⚠️ 您已被管理员 {admin_name} 封禁"
                                }).encode())
                                sock.close()
                            except:
                                pass
                            break
                    self.log(f"🚫 管理员 {admin_name} 封禁了 {target_user}", "admin")
                    self.broadcast_system_message(f"🛡️ 管理员 {admin_name} 封禁了 {target_user}")
                    admin_socket.send(json.dumps({
                        "type": "system", 
                        "message": f"✅ 已封禁用户: {target_user}"
                    }).encode())
                else:
                    admin_socket.send(json.dumps({
                        "type": "system", 
                        "message": f"❌ 未找到用户: {target_user}"
                    }).encode())
                    
        elif cmd == '/unban' and args:
            target_user = args.strip()
            with self.lock:
                if target_user in self.banned_users:
                    self.banned_users.remove(target_user)
                    self.log(f"✅ 管理员 {admin_name} 解封了 {target_user}", "admin")
                    admin_socket.send(json.dumps({
                        "type": "system", 
                        "message": f"✅ 已解封用户: {target_user}"
                    }).encode())
                else:
                    admin_socket.send(json.dumps({
                        "type": "system", 
                        "message": f"❌ 用户未被封禁: {target_user}"
                    }).encode())
                    
        elif cmd == '/mute' and args:
            target_user = args.strip()
            with self.lock:
                if target_user in [info['username'] for info in self.clients.values()]:
                    self.muted_users.add(target_user)
                    self.log(f"🔇 管理员 {admin_name} 静音了 {target_user}", "admin")
                    self.broadcast_system_message(f"🛡️ 管理员 {admin_name} 静音了 {target_user}")
                    admin_socket.send(json.dumps({
                        "type": "system", 
                        "message": f"✅ 已静音用户: {target_user}"
                    }).encode())
                else:
                    admin_socket.send(json.dumps({
                        "type": "system", 
                        "message": f"❌ 未找到用户: {target_user}"
                    }).encode())
                    
        elif cmd == '/unmute' and args:
            target_user = args.strip()
            with self.lock:
                if target_user in self.muted_users:
                    self.muted_users.remove(target_user)
                    self.log(f"🔊 管理员 {admin_name} 取消静音了 {target_user}", "admin")
                    admin_socket.send(json.dumps({
                        "type": "system", 
                        "message": f"✅ 已取消静音用户: {target_user}"
                    }).encode())
                else:
                    admin_socket.send(json.dumps({
                        "type": "system", 
                        "message": f"❌ 用户未被静音: {target_user}"
                    }).encode())
                    
        elif cmd == '/list':
            with self.lock:
                online_users = [f"{'🛡️' if info['is_admin'] else '👤'} {info['username']}" 
                               for info in self.clients.values()]
                banned_users = [f"🚫 {user}" for user in self.banned_users]
                muted_users = [f"🔇 {user}" for user in self.muted_users]
            
            result = f"👥 在线用户 ({len(online_users)}):\n" + "\n".join(online_users) if online_users else "无在线用户"
            if banned_users:
                result += f"\n\n🚫 封禁用户 ({len(banned_users)}):\n" + "\n".join(banned_users)
            if muted_users:
                result += f"\n\n🔇 静音用户 ({len(muted_users)}):\n" + "\n".join(muted_users)
            
            admin_socket.send(json.dumps({
                "type": "system",
                "message": result
            }).encode())
            
        elif cmd == '/broadcast' and args:
            self.broadcast_system_message(f"[公告] {args}", sender=admin_name)
            admin_socket.send(json.dumps({
                "type": "system",
                "message": "✅ 公告已发送"
            }).encode())
            
        elif cmd == '/clear':
            self.chat_history.clear()
            self.broadcast_system_message(f"🛡️ 管理员 {admin_name} 清空了聊天记录", sender=admin_name)
            admin_socket.send(json.dumps({
                "type": "system",
                "message": "✅ 聊天记录已清空"
            }).encode())
            
        elif cmd == '/help':
            help_msg = (
                "🛡️ 管理员命令:\n"
                "/kick <用户名>   - 踢出用户\n"
                "/ban <用户名>    - 封禁用户\n"
                "/unban <用户名>  - 解封用户\n"
                "/mute <用户名>   - 静音用户\n"
                "/unmute <用户名> - 取消静音\n"
                "/list            - 查看在线/封禁/静音用户\n"
                "/broadcast <消息> - 发送系统公告\n"
                "/clear           - 清空聊天记录\n"
                "/help            - 显示此帮助"
            )
            admin_socket.send(json.dumps({"type": "system", "message": help_msg}).encode())
        else:
            admin_socket.send(json.dumps({
                "type": "system",
                "message": "❌ 未知命令。输入 /help 查看可用命令"
            }).encode())
    
    def broadcast_message(self, username, message, is_admin=False):
        """广播普通消息"""
        formatted_msg = f"{username}: {message}"
        self.log(formatted_msg, "message")
        
        # 保存到聊天历史
        timestamp = time.strftime("%H:%M")
        msg_record = {
            "type": "chat",
            "username": username,
            "message": message,
            "is_admin": is_admin,
            "timestamp": timestamp
        }
        self.chat_history.append(msg_record)
        if len(self.chat_history) > 1000:  # 限制历史记录数量
            self.chat_history.pop(0)
        
        msg_data = json.dumps({
            "type": "chat",
            "username": username,
            "message": message,
            "is_admin": is_admin,
            "timestamp": timestamp
        })
        
        disconnected = []
        with self.lock:
            for client_socket in list(self.clients.keys()):
                try:
                    client_socket.send(msg_data.encode())
                except:
                    disconnected.append(client_socket)
        
        for sock in disconnected:
            self.remove_client(sock)
    
    def broadcast_file(self, username, filename, file_data, file_size):
        """广播文件"""
        self.log(f"📁 {username} 发送了文件: {filename} ({file_size} bytes)", "system")
        
        msg_data = json.dumps({
            "type": "file",
            "username": username,
            "filename": filename,
            "data": file_data,
            "size": file_size,
            "timestamp": time.strftime("%H:%M")
        })
        
        disconnected = []
        with self.lock:
            for client_socket in list(self.clients.keys()):
                try:
                    client_socket.send(msg_data.encode())
                except:
                    disconnected.append(client_socket)
        
        for sock in disconnected:
            self.remove_client(sock)
    
    def broadcast_system_message(self, message, exclude=None, sender=None):
        """广播系统消息"""
        prefix = "[系统]" if not sender else f"[{sender}公告]"
        full_msg = f"{prefix} {message}"
        self.log(full_msg, "system")
        
        # 保存到聊天历史
        timestamp = time.strftime("%H:%M")
        msg_record = {
            "type": "system",
            "message": full_msg,
            "timestamp": timestamp
        }
        self.chat_history.append(msg_record)
        if len(self.chat_history) > 1000:  # 限制历史记录数量
            self.chat_history.pop(0)
        
        msg_data = json.dumps({
            "type": "system",
            "message": full_msg,
            "timestamp": timestamp
        })
        
        disconnected = []
        with self.lock:
            for client_socket in list(self.clients.keys()):
                if client_socket != exclude:
                    try:
                        client_socket.send(msg_data.encode())
                    except:
                        disconnected.append(client_socket)
        
        for sock in disconnected:
            self.remove_client(sock)
    
    def remove_client(self, client_socket):
        """安全移除客户端"""
        with self.lock:
            if client_socket in self.clients:
                info = self.clients.pop(client_socket)
                username = info['username']
                self.log(f"❌ {username} 离开了聊天室", "info")
                self.broadcast_system_message(f"{username} 离开了聊天室")
                try:
                    client_socket.close()
                except:
                    pass


class ChatClient:
    def __init__(self, server_host='localhost', server_port=12345):
        self.server_host = server_host
        self.server_port = server_port
        self.client_socket = None
        self.username = None
        self.is_admin = False
        self.running = False
        self.gui = None
        self.file_save_path = os.path.expanduser("~/Downloads")  # 默认下载路径
    
    def set_gui(self, gui):
        self.gui = gui
    
    def log(self, message, level="info"):
        """线程安全的日志记录"""
        if self.gui:
            self.gui.root.after(0, lambda: self.gui.display_message(message, level))
    
    def connect_to_server(self, username, password=""):
        """连接到服务器"""
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.server_host, self.server_port))
            self.log(f"✅ 连接到服务器 {self.server_host}:{self.server_port}", "server")
            
            # 发送认证信息
            auth_data = json.dumps({
                "username": username,
                "password": password if username.lower() == "admin" else ""
            })
            self.client_socket.send(auth_data.encode())
            
            # 接收认证响应
            response = self.client_socket.recv(4096).decode()  # 增大缓冲区以接收历史消息
            resp = json.loads(response)
            
            if resp.get("status") == "error":
                self.log(f"❌ 认证失败: {resp.get('message')}", "error")
                self.client_socket.close()
                return False
            
            self.username = username
            self.is_admin = resp.get("is_admin", False)
            welcome = resp.get("welcome", "欢迎来到聊天室")
            self.log(welcome, "system")
            
            # 显示历史消息
            history = resp.get("history", [])
            if history:
                self.log(f"📋 加载了 {len(history)} 条历史消息", "info")
                for msg in history:
                    if msg["type"] == "chat":
                        sender = msg.get('username', '未知')
                        text = msg.get('message', '')
                        is_admin = msg.get('is_admin', False)
                        prefix = "🛡️" if is_admin else ""
                        self.log(f"{prefix}{sender}: {text}", "chat")
                    elif msg["type"] == "system":
                        self.log(msg.get('message', ''), "system")
            
            # 启动接收线程
            self.running = True
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()
            
            # 启动心跳线程
            heartbeat_thread = threading.Thread(target=self.send_heartbeat)
            heartbeat_thread.daemon = True
            heartbeat_thread.start()
            
            return True
            
        except Exception as e:
            self.log(f"❌ 连接失败: {e}", "error")
            return False
    
    def receive_messages(self):
        """接收消息"""
        while self.running:
            try:
                data = self.client_socket.recv(4096).decode('utf-8')  # 增大缓冲区
                if not data:
                    break
                
                try:
                    msg = json.loads(data)
                    msg_type = msg.get('type')
                    
                    if msg_type == 'chat':
                        sender = msg.get('username', '未知')
                        text = msg.get('message', '')
                        is_admin = msg.get('is_admin', False)
                        timestamp = msg.get('timestamp', time.strftime("%H:%M"))
                        prefix = "🛡️" if is_admin else ""
                        self.log(f"[{timestamp}] {prefix}{sender}: {text}", "chat")
                    
                    elif msg_type == 'system':
                        timestamp = msg.get('timestamp', time.strftime("%H:%M"))
                        self.log(f"[{timestamp}] {msg.get('message', '')}", "system")
                    
                    elif msg_type == 'file':
                        sender = msg.get('username', '未知')
                        filename = msg.get('filename', 'unknown')
                        file_data = msg.get('data', '')
                        file_size = msg.get('size', 0)
                        timestamp = msg.get('timestamp', time.strftime("%H:%M"))
                        self.log(f"[{timestamp}] 📁 {sender} 发送了文件: {filename} ({file_size} bytes)", "system")
                        self.save_received_file(filename, file_data)
                    
                    elif msg_type == 'heartbeat':
                        continue
                        
                except json.JSONDecodeError:
                    # 兼容旧消息格式
                    self.log(data.strip(), "message")
                    
            except Exception as e:
                if self.running:
                    self.log(f"❌ 接收错误: {e}", "error")
                break
        
        self.running = False
        if self.gui:
            self.gui.root.after(0, self.gui.on_disconnect)
    
    def save_received_file(self, filename, file_data):
        """保存接收到的文件"""
        try:
            # 创建保存路径
            save_path = os.path.join(self.file_save_path, filename)
            with open(save_path, 'wb') as f:
                f.write(file_data.encode('latin1'))  # base64编码的数据用latin1解码回二进制
            self.log(f"✅ 文件已保存到: {save_path}", "system")
        except Exception as e:
            self.log(f"❌ 保存文件失败: {e}", "error")
    
    def send_heartbeat(self):
        """定期发送心跳保持连接"""
        while self.running:
            time.sleep(30)
            if self.running and self.client_socket:
                try:
                    self.client_socket.send(json.dumps({"type": "heartbeat"}).encode())
                except:
                    break
    
    def send_message(self, message):
        """发送消息"""
        if not self.running or not self.client_socket:
            self.log("⚠️ 未连接到服务器", "error")
            return False
        
        try:
            msg_data = json.dumps({
                "type": "chat",
                "content": message
            })
            self.client_socket.send(msg_data.encode())
            # 本地回显
            timestamp = time.strftime("%H:%M")
            prefix = "🛡️" if self.is_admin else ""
            self.log(f"[{timestamp}] {prefix}{self.username}: {message}", "own")
            return True
        except Exception as e:
            self.log(f"❌ 发送失败: {e}", "error")
            return False
    
    def send_file(self, filepath):
        """发送文件"""
        if not self.running or not self.client_socket:
            self.log("⚠️ 未连接到服务器", "error")
            return False
        
        try:
            filename = os.path.basename(filepath)
            with open(filepath, 'rb') as f:
                file_data = f.read()
            file_size = len(file_data)
            
            # 编码为base64字符串传输
            import base64
            encoded_data = base64.b64encode(file_data).decode('utf-8')
            
            msg_data = json.dumps({
                "type": "file",
                "filename": filename,
                "data": encoded_data,
                "size": file_size
            })
            
            self.client_socket.send(msg_data.encode())
            self.log(f"📁 已发送文件: {filename} ({file_size} bytes)", "system")
            return True
        except Exception as e:
            self.log(f"❌ 发送文件失败: {e}", "error")
            return False
    
    def disconnect(self):
        """断开连接"""
        self.running = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        self.log("🔌 已断开连接", "info")


class ChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🛡️ 内网聊天程序 - 增强版 v2.0")
        self.root.geometry("900x700")
        self.root.minsize(700, 500)
        
        # 初始化状态
        self.is_server_running = False
        self.is_connected = False
        self.server = None
        self.client = None
        self.admin_password = "admin123"  # 默认密码
        
        # 创建UI
        self.create_widgets()
        
        # 协议处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_widgets(self):
        # 顶部控制栏
        control_frame = tk.Frame(self.root, bg="#f0f0f0", height=50)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        control_frame.pack_propagate(False)
        
        # 模式选择
        mode_frame = tk.Frame(control_frame, bg="#f0f0f0")
        mode_frame.pack(side=tk.LEFT, padx=10)
        
        self.mode_var = tk.StringVar(value="client")
        tk.Radiobutton(mode_frame, text="🖥️ 服务器模式", variable=self.mode_var, 
                      value="server", command=self.update_ui, bg="#f0f0f0").pack(side=tk.LEFT)
        tk.Radiobutton(mode_frame, text="💬 客户端模式", variable=self.mode_var, 
                      value="client", command=self.update_ui, bg="#f0f0f0").pack(side=tk.LEFT, padx=(15, 0))
        
        # 操作按钮
        self.action_button = tk.Button(control_frame, text="🚀 启动服务器", 
                                     command=self.toggle_action, width=15, bg="#4CAF50", fg="white")
        self.action_button.pack(side=tk.RIGHT, padx=10)
        
        # 服务器配置区域
        self.server_config_frame = tk.LabelFrame(self.root, text="服务器配置", padx=10, pady=5)
        self.server_config_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        tk.Label(self.server_config_frame, text="IP:").grid(row=0, column=0, sticky=tk.W)
        self.server_host = tk.Entry(self.server_config_frame, width=15)
        self.server_host.insert(0, "localhost")
        self.server_host.grid(row=0, column=1, padx=5)
        
        tk.Label(self.server_config_frame, text="端口:").grid(row=0, column=2, sticky=tk.W)
        self.server_port = tk.Entry(self.server_config_frame, width=8)
        self.server_port.insert(0, "12345")
        self.server_port.grid(row=0, column=3, padx=5)
        
        tk.Label(self.server_config_frame, text="管理员密码:").grid(row=0, column=4, sticky=tk.W)
        self.admin_pass_entry = tk.Entry(self.server_config_frame, width=12, show="*")
        self.admin_pass_entry.insert(0, "admin123")
        self.admin_pass_entry.grid(row=0, column=5, padx=5)
        
        # 客户端配置区域
        self.client_config_frame = tk.LabelFrame(self.root, text="客户端配置", padx=10, pady=5)
        self.client_config_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        tk.Label(self.client_config_frame, text="服务器IP:").grid(row=0, column=0, sticky=tk.W)
        self.client_host = tk.Entry(self.client_config_frame, width=15)
        self.client_host.insert(0, "localhost")
        self.client_host.grid(row=0, column=1, padx=5)
        
        tk.Label(self.client_config_frame, text="端口:").grid(row=0, column=2, sticky=tk.W)
        self.client_port = tk.Entry(self.client_config_frame, width=8)
        self.client_port.insert(0, "12345")
        self.client_port.grid(row=0, column=3, padx=5)
        
        # 聊天区域
        chat_frame = tk.Frame(self.root)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))
        
        # 聊天历史
        self.chat_history = scrolledtext.ScrolledText(
            chat_frame, wrap=tk.WORD, font=("Arial", 10), 
            bg="#f9f9f9", state=tk.DISABLED, height=20
        )
        self.chat_history.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        # 滚动条
        scrollbar = tk.Scrollbar(chat_frame, orient=tk.VERTICAL, command=self.chat_history.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_history.config(yscrollcommand=scrollbar.set)
        
        # 配置消息标签样式
        self.chat_history.tag_config("server", foreground="#1a73e8", font=("Arial", 9, "bold"))
        self.chat_history.tag_config("system", foreground="#34a853", font=("Arial", 9, "bold"))
        self.chat_history.tag_config("admin", foreground="#d32f2f", font=("Arial", 10, "bold"))
        self.chat_history.tag_config("own", foreground="#8e24aa", font=("Arial", 10, "italic"))
        self.chat_history.tag_config("error", foreground="#d32f2f", background="#ffebee")
        self.chat_history.tag_config("info", foreground="#5f6368")
        self.chat_history.tag_config("chat", foreground="#202124")
        
        # 输入区域
        input_frame = tk.Frame(self.root, height=80)
        input_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        input_frame.pack_propagate(False)
        
        # 消息输入框
        self.message_entry = tk.Entry(input_frame, font=("Arial", 10))
        self.message_entry.pack(side=tk.TOP, fill=tk.X, padx=(0, 10), pady=(5, 0))
        self.message_entry.bind("<Return>", lambda e: self.send_message())
        self.message_entry.bind("<Up>", self.show_admin_help)  # 按上箭头显示帮助
        
        # 按钮框架
        button_frame = tk.Frame(input_frame)
        button_frame.pack(side=tk.TOP, fill=tk.X, pady=(5, 0))
        
        # 发送按钮
        self.send_button = tk.Button(button_frame, text="➤ 发送", command=self.send_message, 
                                   width=10, bg="#1a73e8", fg="white")
        self.send_button.pack(side=tk.RIGHT)
        
        # 文件发送按钮
        self.file_button = tk.Button(button_frame, text="📁 发送文件", command=self.send_file, 
                                   width=10, bg="#ff9800", fg="white")
        self.file_button.pack(side=tk.RIGHT, padx=(0, 5))
        
        # 清屏按钮
        self.clear_button = tk.Button(button_frame, text="🗑️ 清屏", command=self.clear_chat, 
                                    width=8, bg="#f44336", fg="white")
        self.clear_button.pack(side=tk.RIGHT, padx=(0, 5))
        
        # 初始UI状态
        self.update_ui()
    
    def update_ui(self):
        """根据模式更新UI"""
        if self.mode_var.get() == "server":
            self.server_config_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
            self.client_config_frame.pack_forget()
            self.action_button.config(text="🚀 启动服务器", bg="#4CAF50")
            self.message_entry.config(state=tk.DISABLED)
            self.send_button.config(state=tk.DISABLED)
            self.file_button.config(state=tk.DISABLED)
            self.clear_button.config(state=tk.DISABLED)
        else:
            self.server_config_frame.pack_forget()
            self.client_config_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
            self.action_button.config(text="🔌 连接到服务器", bg="#2196F3")
            self.message_entry.config(state=tk.NORMAL if self.is_connected else tk.DISABLED)
            self.send_button.config(state=tk.NORMAL if self.is_connected else tk.DISABLED)
            self.file_button.config(state=tk.NORMAL if self.is_connected else tk.DISABLED)
            self.clear_button.config(state=tk.NORMAL)
    
    def toggle_action(self):
        """切换服务器/客户端状态"""
        if self.mode_var.get() == "server":
            if not self.is_server_running:
                self.start_server()
            else:
                self.stop_server()
        else:
            if not self.is_connected:
                self.connect_to_server()
            else:
                self.disconnect_from_server()
    
    def start_server(self):
        """启动服务器"""
        try:
            host = self.server_host.get().strip() or "localhost"
            port = int(self.server_port.get().strip())
            self.admin_password = self.admin_pass_entry.get().strip() or "admin123"
            
            self.server = ChatServer(host, port, self.admin_password)
            self.server.set_gui(self)
            
            server_thread = threading.Thread(target=self.server.start_server)
            server_thread.daemon = True
            server_thread.start()
            
            self.is_server_running = True
            self.action_button.config(text="🛑 停止服务器", bg="#f44336")
            self.display_message(f"🚀 服务器已启动 | IP: {host} | 端口: {port}", "server")
            self.display_message(f"🛡️ 管理员密码: {self.admin_password} (客户端使用用户名'admin'和此密码登录)", "system")
            self.display_message("💡 提示: 客户端连接后，管理员可使用 /help 查看管理命令", "info")
            
        except ValueError:
            messagebox.showerror("输入错误", "端口号必须是有效数字")
        except Exception as e:
            messagebox.showerror("启动失败", f"无法启动服务器:\n{e}")
    
    def stop_server(self):
        """停止服务器"""
        if self.server and self.server.server_socket:
            try:
                self.server.server_socket.close()
            except:
                pass
        self.is_server_running = False
        self.action_button.config(text="🚀 启动服务器", bg="#4CAF50")
        self.display_message("🛑 服务器已停止", "server")
    
    def connect_to_server(self):
        """连接到服务器"""
        # 获取用户名
        username = simpledialog.askstring("👤 用户名", "请输入您的用户名:", parent=self.root)
        if not username:
            return
        
        # 如果是admin，要求输入密码
        password = ""
        if username.lower() == "admin":
            password = simpledialog.askstring("🛡️ 管理员密码", "请输入管理员密码:", 
                                            show="*", parent=self.root)
            if password is None:  # 用户取消
                return
            if not password:
                messagebox.showwarning("警告", "管理员密码不能为空")
                return
        
        try:
            host = self.client_host.get().strip() or "localhost"
            port = int(self.client_port.get().strip())
            
            self.client = ChatClient(host, port)
            self.client.set_gui(self)
            
            if self.client.connect_to_server(username, password):
                self.is_connected = True
                self.action_button.config(text="🔌 断开连接", bg="#f44336")
                self.message_entry.config(state=tk.NORMAL)
                self.send_button.config(state=tk.NORMAL)
                self.file_button.config(state=tk.NORMAL)
                self.display_message(f"✅ 已连接到 {host}:{port}", "server")
                if self.client.is_admin:
                    self.display_message("🛡️ 您已进入管理员模式！输入 /help 查看可用命令", "admin")
                else:
                    self.display_message("💡 提示: 按 ↑ 键查看管理员命令帮助（仅管理员）", "info")
            else:
                messagebox.showerror("连接失败", "无法连接到服务器，请检查设置")
                
        except ValueError:
            messagebox.showerror("输入错误", "端口号必须是有效数字")
        except Exception as e:
            messagebox.showerror("连接错误", f"连接失败:\n{e}")
    
    def disconnect_from_server(self):
        """断开连接"""
        if self.client:
            self.client.disconnect()
        self.is_connected = False
        self.action_button.config(text="🔌 连接到服务器", bg="#2196F3")
        self.message_entry.config(state=tk.DISABLED)
        self.send_button.config(state=tk.DISABLED)
        self.file_button.config(state=tk.DISABLED)
        self.display_message("🔌 连接已断开", "info")
    
    def on_disconnect(self):
        """处理意外断开"""
        if self.is_connected:
            self.is_connected = False
            self.action_button.config(text="🔌 连接到服务器", bg="#2196F3")
            self.message_entry.config(state=tk.DISABLED)
            self.send_button.config(state=tk.DISABLED)
            self.file_button.config(state=tk.DISABLED)
            self.display_message("⚠️ 与服务器的连接已断开", "error")
    
    def send_message(self):
        """发送消息"""
        message = self.message_entry.get().strip()
        if message and self.client and self.is_connected:
            if self.client.is_admin and message.startswith('/') and not message.startswith('//'):
                # 管理员命令（单斜杠），不本地回显（服务器会返回结果）
                self.client.send_message(message)
            else:
                # 普通消息或转义的命令（//）
                if message.startswith('//'):
                    message = message[1:]  # 去掉一个斜杠
                self.client.send_message(message)
            self.message_entry.delete(0, tk.END)
    
    def send_file(self):
        """发送文件"""
        if not self.client or not self.is_connected:
            messagebox.showwarning("警告", "未连接到服务器")
            return
        
        file_path = filedialog.askopenfilename(title="选择要发送的文件")
        if file_path:
            self.client.send_file(file_path)
    
    def clear_chat(self):
        """清空聊天记录"""
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.delete(1.0, tk.END)
        self.chat_history.config(state=tk.DISABLED)
    
    def show_admin_help(self, event=None):
        """显示管理员命令帮助（按上箭头）"""
        if self.is_connected and self.client and self.client.is_admin:
            help_text = (
                "🛡️ 管理员命令帮助:\n"
                "/kick <用户名>   - 踢出指定用户\n"
                "/ban <用户名>    - 封禁用户（禁止再次连接）\n"
                "/unban <用户名>  - 解封用户\n"
                "/mute <用户名>   - 静音用户（禁止发言）\n"
                "/unmute <用户名> - 取消静音\n"
                "/list            - 显示在线/封禁/静音用户列表\n"
                "/broadcast <消息> - 发送系统公告\n"
                "/clear           - 清空聊天记录\n"
                "/help            - 显示此帮助\n"
                "💡 普通消息前加 // 可发送字面斜杠（如 //hello）"
            )
            self.display_message(help_text, "system")
            return "break"  # 阻止输入框默认行为
    
    def display_message(self, message, msg_type="chat"):
        """线程安全的消息显示"""
        self.chat_history.config(state=tk.NORMAL)
        
        # 添加时间戳
        timestamp = time.strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}\n"
        
        # 选择标签
        tag = msg_type if msg_type in ["server", "system", "admin", "own", "error", "info"] else "chat"
        
        # 特殊处理：包含"🛡️"的消息视为管理员消息
        if "🛡️" in message and msg_type not in ["own", "error"]:
            tag = "admin"
        
        self.chat_history.insert(tk.END, formatted, tag)
        self.chat_history.see(tk.END)
        self.chat_history.config(state=tk.DISABLED)
    
    def on_closing(self):
        """处理窗口关闭"""
        if self.is_server_running:
            if messagebox.askokcancel("关闭确认", "服务器正在运行，确定要退出吗？"):
                self.stop_server()
                self.root.destroy()
        elif self.is_connected:
            if messagebox.askokcancel("关闭确认", "您已连接到服务器，确定要断开并退出吗？"):
                self.disconnect_from_server()
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    app = ChatApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
