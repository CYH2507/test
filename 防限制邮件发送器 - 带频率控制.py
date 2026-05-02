import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from threading import Thread
import time
import random

class EmailSenderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("防限制邮件发送器 - 带频率控制")
        self.root.geometry("900x700")
        self.root.minsize(700, 600)
        
        # 创建主框架
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(4, weight=1)
        main_frame.rowconfigure(7, weight=1)
        
        # SMTP服务器设置
        ttk.Label(main_frame, text="SMTP服务器:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.smtp_server_var = tk.StringVar(value="smtp.gmail.com")
        smtp_entry = ttk.Entry(main_frame, textvariable=self.smtp_server_var, width=20)
        smtp_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 10), columnspan=2)
        
        ttk.Label(main_frame, text="端口:").grid(row=0, column=3, sticky=tk.W, pady=2)
        self.port_var = tk.StringVar(value="587")
        port_entry = ttk.Entry(main_frame, textvariable=self.port_var, width=10)
        port_entry.grid(row=0, column=4, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # 发送者信息
        ttk.Label(main_frame, text="发件人邮箱:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.sender_email_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.sender_email_var, width=30).grid(
            row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 10), columnspan=3)
        
        ttk.Label(main_frame, text="密码/授权码:").grid(row=1, column=4, sticky=tk.W, pady=2)
        self.password_var = tk.StringVar()
        password_entry = ttk.Entry(main_frame, textvariable=self.password_var, show="*", width=20)
        password_entry.grid(row=1, column=5, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # 收件人列表
        ttk.Label(main_frame, text="收件人邮箱 (每行一个):").grid(row=2, column=0, sticky=tk.W, pady=(10, 2))
        self.recipients_text = scrolledtext.ScrolledText(main_frame, height=6, width=50)
        self.recipients_text.grid(row=3, column=0, columnspan=6, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # 邮件主题
        ttk.Label(main_frame, text="邮件主题:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.subject_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.subject_var, width=60).grid(
            row=4, column=1, columnspan=5, sticky=(tk.W, tk.E), padx=(10, 0))
        
        # 邮件内容
        ttk.Label(main_frame, text="邮件内容:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.content_text = scrolledtext.ScrolledText(main_frame, height=8, width=50)
        self.content_text.grid(row=6, column=0, columnspan=6, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # 控制按钮和设置
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=6, pady=5, sticky=(tk.W, tk.E))
        button_frame.columnconfigure(4, weight=1)
        
        self.send_button = ttk.Button(button_frame, text="开始发送", command=self.start_sending)
        self.send_button.grid(row=0, column=0, padx=(0, 5))
        
        self.stop_button = ttk.Button(button_frame, text="停止发送", command=self.stop_sending, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=(0, 5))
        
        self.clear_button = ttk.Button(button_frame, text="清空日志", command=self.clear_log)
        self.clear_button.grid(row=0, column=2, padx=(0, 5))
        
        # 发送次数设置
        ttk.Label(button_frame, text="发送次数:").grid(row=0, column=3, padx=(10, 0))
        self.send_count_var = tk.StringVar(value="1")
        send_count_spinbox = ttk.Spinbox(button_frame, from_=1, to=999, textvariable=self.send_count_var, width=5)
        send_count_spinbox.grid(row=0, column=4, padx=(5, 10))
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(button_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=0, column=5, sticky=(tk.W, tk.E), padx=(10, 0))
        
        # 发送间隔设置
        ttk.Label(button_frame, text="基础间隔(秒):").grid(row=0, column=6, padx=(10, 0))
        self.interval_var = tk.StringVar(value="5")
        interval_spinbox = ttk.Spinbox(button_frame, from_=1, to=60, textvariable=self.interval_var, width=5)
        interval_spinbox.grid(row=0, column=7, padx=(5, 0))
        
        # 随机延迟设置
        ttk.Label(button_frame, text="随机延迟(秒):").grid(row=0, column=8, padx=(10, 0))
        self.random_delay_var = tk.StringVar(value="3")
        random_delay_spinbox = ttk.Spinbox(button_frame, from_=0, to=30, textvariable=self.random_delay_var, width=5)
        random_delay_spinbox.grid(row=0, column=9, padx=(5, 0))
        
        # 状态标签
        self.status_label = ttk.Label(button_frame, text="就绪")
        self.status_label.grid(row=0, column=10, padx=(10, 0))
        
        # 日志显示区域
        ttk.Label(main_frame, text="发送日志:").grid(row=8, column=0, sticky=tk.W, pady=(10, 2))
        self.log_text = scrolledtext.ScrolledText(main_frame, height=12, width=50)
        self.log_text.grid(row=9, column=0, columnspan=6, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 统计信息
        stats_frame = ttk.Frame(main_frame)
        stats_frame.grid(row=10, column=0, columnspan=6, pady=(10, 0), sticky=(tk.W, tk.E))
        stats_frame.columnconfigure(3, weight=1)
        
        self.total_sent_var = tk.StringVar(value="总发送: 0 封")
        ttk.Label(stats_frame, textvariable=self.total_sent_var).grid(row=0, column=0, padx=(0, 20))
        
        self.success_var = tk.StringVar(value="成功: 0 封")
        ttk.Label(stats_frame, textvariable=self.success_var).grid(row=0, column=1, padx=(0, 20))
        
        self.failed_var = tk.StringVar(value="失败: 0 封")
        ttk.Label(stats_frame, textvariable=self.failed_var).grid(row=0, column=2, padx=(0, 20))
        
        self.current_batch_var = tk.StringVar(value="当前批次: 0/0")
        ttk.Label(stats_frame, textvariable=self.current_batch_var).grid(row=0, column=3, sticky=tk.E)
        
        # 控制变量
        self.is_sending = False
        self.should_stop = False
        self.sent_count = 0
        self.success_count = 0
        self.fail_count = 0
        self.total_expected = 0
        
    def log_message(self, message):
        """在日志区域添加消息"""
        self.log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def update_stats(self):
        """更新统计信息"""
        self.total_sent_var.set(f"总发送: {self.sent_count} 封")
        self.success_var.set(f"成功: {self.success_count} 封")
        self.failed_var.set(f"失败: {self.fail_count} 封")
        self.current_batch_var.set(f"当前批次: {self.sent_count}/{self.total_expected}")
        
    def clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)
        self.sent_count = 0
        self.success_count = 0
        self.fail_count = 0
        self.update_stats()
        
    def start_sending(self):
        """开始发送邮件"""
        if not self.validate_inputs():
            return
            
        self.is_sending = True
        self.should_stop = False
        self.send_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # 重置计数器
        self.sent_count = 0
        self.success_count = 0
        self.fail_count = 0
        
        # 计算总预期发送数量
        recipients = self.recipients_text.get(1.0, tk.END).strip().split('\n')
        recipients = [r.strip() for r in recipients if r.strip()]
        send_count = int(self.send_count_var.get())
        self.total_expected = len(recipients) * send_count
        
        self.log_message(f"开始发送邮件，每个收件人发送 {send_count} 次，共 {self.total_expected} 封")
        self.log_message(f"基础间隔: {self.interval_var.get()}秒，随机延迟: {self.random_delay_var.get()}秒")
        self.update_stats()
        
        # 启动发送线程
        send_thread = Thread(target=self.send_emails, daemon=True)
        send_thread.start()
        
    def stop_sending(self):
        """停止发送邮件"""
        self.should_stop = True
        self.log_message("正在停止发送...")
        
    def validate_inputs(self):
        """验证输入"""
        if not self.sender_email_var.get():
            messagebox.showerror("错误", "请输入发件人邮箱")
            return False
        if not self.password_var.get():
            messagebox.showerror("错误", "请输入密码/授权码")
            return False
        if not self.subject_var.get():
            messagebox.showerror("错误", "请输入邮件主题")
            return False
        recipients = self.recipients_text.get(1.0, tk.END).strip()
        if not recipients:
            messagebox.showerror("错误", "请输入至少一个收件人邮箱")
            return False
        try:
            send_count = int(self.send_count_var.get())
            if send_count <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "发送次数必须是正整数")
            return False
        try:
            float(self.interval_var.get())
            float(self.random_delay_var.get())
        except ValueError:
            messagebox.showerror("错误", "间隔时间必须是数字")
            return False
        return True
        
    def send_emails(self):
        """发送邮件的主要逻辑"""
        recipients = self.recipients_text.get(1.0, tk.END).strip().split('\n')
        recipients = [r.strip() for r in recipients if r.strip()]
        send_count = int(self.send_count_var.get())
        
        total_recipients = len(recipients)
        
        try:
            # 连接SMTP服务器
            server = smtplib.SMTP(self.smtp_server_var.get(), int(self.port_var.get()))
            server.starttls()
            server.login(self.sender_email_var.get(), self.password_var.get())
            
            for batch_num in range(send_count):
                if self.should_stop:
                    break
                    
                self.log_message(f"开始第 {batch_num + 1} 轮发送")
                
                for recipient_idx, recipient in enumerate(recipients):
                    if self.should_stop:
                        break
                        
                    try:
                        # 创建邮件
                        msg = MIMEMultipart()
                        msg['From'] = self.sender_email_var.get()
                        msg['To'] = recipient
                        msg['Subject'] = self.subject_var.get()
                        
                        content = self.content_text.get(1.0, tk.END).strip()
                        msg.attach(MIMEText(content, 'plain', 'utf-8'))
                        
                        # 发送邮件
                        server.send_message(msg)
                        self.success_count += 1
                        self.sent_count += 1
                        self.log_message(f"第 {batch_num + 1} 轮 - 成功发送至 {recipient}")
                        
                    except smtplib.SMTPRecipientsRefused:
                        self.fail_count += 1
                        self.sent_count += 1
                        self.log_message(f"第 {batch_num + 1} 轮 - 收件人拒绝: {recipient}")
                        
                    except smtplib.SMTPHeloError:
                        self.fail_count += 1
                        self.sent_count += 1
                        self.log_message(f"第 {batch_num + 1} 轮 - SMTP HELO错误: {recipient}")
                        
                    except smtplib.SMTPSenderRefused:
                        self.fail_count += 1
                        self.sent_count += 1
                        self.log_message(f"第 {batch_num + 1} 轮 - 发件人被拒绝: {recipient}")
                        
                    except smtplib.SMTPDataError as e:
                        # 处理Too many attempts错误
                        error_code = str(e).lower()
                        if 'too many attempts' in error_code or 'rate limit' in error_code:
                            self.fail_count += 1
                            self.sent_count += 1
                            self.log_message(f"第 {batch_num + 1} 轮 - 触发速率限制，暂停后重试: {recipient}")
                            
                            # 遇到限制时暂停更长时间
                            wait_time = 60 + random.randint(30, 60)  # 等待60-120秒
                            self.log_message(f"遇到频率限制，暂停 {wait_time} 秒...")
                            time.sleep(wait_time)
                        else:
                            self.fail_count += 1
                            self.sent_count += 1
                            self.log_message(f"第 {batch_num + 1} 轮 - 数据错误: {recipient}, 错误: {str(e)}")
                    
                    except Exception as e:
                        self.fail_count += 1
                        self.sent_count += 1
                        self.log_message(f"第 {batch_num + 1} 轮 - 发送失败至 {recipient}: {str(e)}")
                    
                    # 更新进度
                    progress = (self.sent_count / self.total_expected) * 100
                    self.progress_var.set(progress)
                    self.update_stats()
                    
                    # 更新状态
                    self.status_label.config(text=f"正在发送... ({self.sent_count}/{self.total_expected})")
                    
                    # 等待设定的时间间隔（带随机延迟）
                    if not self.should_stop and (recipient_idx < total_recipients - 1 or batch_num < send_count - 1):
                        base_interval = float(self.interval_var.get())
                        random_delay = random.uniform(0, float(self.random_delay_var.get()))
                        total_delay = base_interval + random_delay
                        time.sleep(total_delay)
                
                if batch_num < send_count - 1 and not self.should_stop:
                    self.log_message(f"第 {batch_num + 1} 轮完成，准备开始第 {batch_num + 2} 轮...")
                    
            server.quit()
            
        except Exception as e:
            self.log_message(f"SMTP连接错误: {str(e)}")
            messagebox.showerror("错误", f"SMTP连接失败: {str(e)}")
            
        finally:
            self.is_sending = False
            self.should_stop = False
            self.send_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.status_label.config(text="发送完成")
            
            self.log_message(f"所有批次发送完成! 总计: {self.sent_count}, 成功: {self.success_count}, 失败: {self.fail_count}")
            messagebox.showinfo("完成", f"发送完成!\n总计: {self.sent_count}\n成功: {self.success_count}\n失败: {self.fail_count}")

if __name__ == "__main__":
    root = tk.Tk()
    app = EmailSenderApp(root)
    root.mainloop()
