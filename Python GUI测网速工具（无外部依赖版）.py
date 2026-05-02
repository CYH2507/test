import tkinter as tk
from tkinter import ttk, messagebox
import time
import requests
from concurrent.futures import ThreadPoolExecutor
import threading
from threading import Thread
import random

class NetworkSpeedTestGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("网络速度测试工具")
        self.root.geometry("800x700")
        self.root.resizable(True, True)
        
        # 设置样式
        style = ttk.Style()
        style.theme_use('clam')
        
        # 创建主框架
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # 标题
        title_label = ttk.Label(main_frame, text="网络速度测试工具", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # 控制区域
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Ping结果显示
        ttk.Label(control_frame, text="Ping:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.ping_var = tk.StringVar(value="-- ms")
        self.ping_label = ttk.Label(control_frame, textvariable=self.ping_var, font=("Arial", 12))
        self.ping_label.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        # 下载速度显示
        ttk.Label(control_frame, text="下载速度:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.download_var = tk.StringVar(value="-- MB/s")
        self.download_label = ttk.Label(control_frame, textvariable=self.download_var, font=("Arial", 12))
        self.download_label.grid(row=0, column=3, sticky=tk.W, padx=(0, 20))
        
        # 上传速度显示
        ttk.Label(control_frame, text="上传速度:").grid(row=0, column=4, sticky=tk.W, padx=(0, 10))
        self.upload_var = tk.StringVar(value="-- MB/s")
        self.upload_label = ttk.Label(control_frame, textvariable=self.upload_var, font=("Arial", 12))
        self.upload_label.grid(row=0, column=5, sticky=tk.W, padx=(0, 20))
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(control_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=1, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=10)
        
        # 状态标签
        self.status_var = tk.StringVar(value="就绪")
        self.status_label = ttk.Label(control_frame, textvariable=self.status_var)
        self.status_label.grid(row=1, column=4, columnspan=2, pady=10)
        
        # 测试按钮
        self.test_button = ttk.Button(control_frame, text="开始测试", command=self.start_test)
        self.test_button.grid(row=2, column=0, columnspan=6, pady=10)
        
        # 创建绘图区域
        plot_frame = ttk.LabelFrame(main_frame, text="网络速度趋势图", padding="10")
        plot_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(0, weight=1)
        
        # 创建Canvas用于绘制图表
        self.canvas = tk.Canvas(plot_frame, bg='white', bd=1, relief='sunken')
        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 初始化数据
        self.data_points = 50  # 显示50个数据点
        self.time_data = list(range(self.data_points))
        self.ping_data = [0] * self.data_points
        self.download_data = [0] * self.data_points
        self.upload_data = [0] * self.data_points
        
        # 绘制初始坐标轴
        self.draw_chart()
        
        # 结果文本框
        result_frame = ttk.LabelFrame(main_frame, text="详细结果", padding="10")
        result_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        result_frame.columnconfigure(0, weight=1)
        
        self.result_text = tk.Text(result_frame, height=6, width=50)
        scrollbar = ttk.Scrollbar(result_frame, orient="vertical", command=self.result_text.yview)
        self.result_text.configure(yscrollcommand=scrollbar.set)
        
        self.result_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # 初始化测试类
        self.tester = NetworkSpeedTest()
        self.is_testing = False
        
        # 更新图表的定时器
        self.update_plot()
        
    def draw_chart(self):
        # 清除画布
        self.canvas.delete("all")
        
        # 获取画布尺寸
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        
        if width <= 1 or height <= 1:
            # 如果画布还没初始化，使用默认尺寸
            width = 760
            height = 300
        
        # 边距
        margin_x = 60
        margin_y = 30
        
        # 计算绘图区域
        plot_width = width - 2 * margin_x
        plot_height = height - 2 * margin_y
        
        # 绘制坐标轴
        self.canvas.create_line(margin_x, height - margin_y, width - margin_x, height - margin_y, fill='black')  # X轴
        self.canvas.create_line(margin_x, margin_y, margin_x, height - margin_y, fill='black')  # Y轴
        
        # 找到最大值以便缩放
        max_ping = max(self.ping_data) if any(self.ping_data) else 100
        max_download = max(self.download_data) if any(self.download_data) else 10
        max_upload = max(self.upload_data) if any(self.upload_data) else 5
        
        # 如果所有值都是0，设置默认最大值
        if max_ping == 0:
            max_ping = 100
        if max_download == 0:
            max_download = 10
        if max_upload == 0:
            max_upload = 5
        
        # 绘制Y轴刻度和标签
        y_max = max(max_ping, max_download * 10, max_upload * 20)  # 按比例缩放不同的指标
        for i in range(0, 6):  # 画5条水平线
            y_pos = height - margin_y - (i * plot_height // 5)
            self.canvas.create_line(margin_x, y_pos, width - margin_x, y_pos, dash=(2, 2), fill='lightgray')
            # 标签值
            if i == 0:
                label_val = 0
            elif i == 1:
                label_val = int(y_max * 0.2)
            elif i == 2:
                label_val = int(y_max * 0.4)
            elif i == 3:
                label_val = int(y_max * 0.6)
            elif i == 4:
                label_val = int(y_max * 0.8)
            else:
                label_val = int(y_max)
                
            self.canvas.create_text(margin_x - 10, y_pos, text=str(label_val), anchor='e', fill='black')
        
        # 绘制X轴刻度和标签
        for i in range(0, 11):  # 画10个刻度
            x_pos = margin_x + (i * plot_width // 10)
            self.canvas.create_line(x_pos, height - margin_y, x_pos, height - margin_y + 5, fill='black')
            label_val = i * (self.data_points // 10)
            self.canvas.create_text(x_pos, height - margin_y + 15, text=str(label_val), anchor='n', fill='black')
        
        # 绘制标题
        self.canvas.create_text(width // 2, margin_y - 10, text='网络速度实时监测', anchor='center', font=('Arial', 12, 'bold'))
        
        # 绘制图例
        self.canvas.create_line(margin_x + 10, margin_y + 10, margin_x + 30, margin_y + 10, fill='blue', width=2)
        self.canvas.create_text(margin_x + 35, margin_y + 10, text='Ping (ms)', anchor='w', fill='blue')
        
        self.canvas.create_line(margin_x + 10, margin_y + 30, margin_x + 30, margin_y + 30, fill='green', width=2)
        self.canvas.create_text(margin_x + 35, margin_y + 30, text='下载速度 (MB/s)', anchor='w', fill='green')
        
        self.canvas.create_line(margin_x + 10, margin_y + 50, margin_x + 30, margin_y + 50, fill='red', width=2)
        self.canvas.create_text(margin_x + 35, margin_y + 50, text='上传速度 (MB/s)', anchor='w', fill='red')
        
        # 绘制数据线
        self.draw_line(self.ping_data, 'blue', y_max, margin_x, margin_y, plot_width, plot_height)
        self.draw_line(self.download_data, 'green', y_max/10, margin_x, margin_y, plot_width, plot_height)
        self.draw_line(self.upload_data, 'red', y_max/20, margin_x, margin_y, plot_width, plot_height)
    
    def draw_line(self, data, color, scale_factor, margin_x, margin_y, plot_width, plot_height):
        points = []
        for i, value in enumerate(data):
            x = margin_x + (i * plot_width) // (len(data) - 1) if len(data) > 1 else margin_x
            y = margin_y + plot_height - (value * plot_height) / scale_factor if scale_factor != 0 else margin_y + plot_height
            points.extend([x, y])
        
        if len(points) >= 4:  # 至少需要两个点才能画线
            self.canvas.create_line(points, fill=color, width=2, smooth=True)
    
    def update_plot(self):
        # 更新数据（模拟实时数据）
        self.ping_data.pop(0)
        self.download_data.pop(0)
        self.upload_data.pop(0)
        
        # 添加新的随机数据（仅用于演示，实际应用中应使用真实数据）
        self.ping_data.append(random.uniform(20, 100))
        self.download_data.append(random.uniform(1, 10))
        self.upload_data.append(random.uniform(0.5, 5))
        
        # 重绘图表
        self.draw_chart()
        
        # 每秒更新一次
        self.root.after(1000, self.update_plot)
    
    def start_test(self):
        if not self.is_testing:
            self.is_testing = True
            self.test_button.config(text="测试中...", state="disabled")
            self.progress_var.set(0)
            self.result_text.delete(1.0, tk.END)
            
            # 在新线程中执行测试
            test_thread = Thread(target=self.run_test_in_thread)
            test_thread.daemon = True
            test_thread.start()
    
    def run_test_in_thread(self):
        try:
            self.root.after(0, lambda: self.status_var.set("正在测试Ping..."))
            self.root.after(0, lambda: self.progress_var.set(10))
            
            # 测试Ping
            ping_result = self.tester.test_ping()
            if ping_result is not None:
                self.root.after(0, lambda: self.ping_var.set(f"{ping_result} ms"))
                self.root.after(0, lambda r=ping_result: self.append_result(f"Ping: {r} ms\n"))
            
            self.root.after(0, lambda: self.status_var.set("正在测试下载速度..."))
            self.root.after(0, lambda: self.progress_var.set(40))
            
            # 测试下载速度
            download_result = self.tester.test_download_speed()
            self.root.after(0, lambda: self.download_var.set(f"{download_result} MB/s"))
            self.root.after(0, lambda r=download_result: self.append_result(f"下载速度: {r} MB/s ({round(r * 8, 2)} Mbps)\n"))
            
            self.root.after(0, lambda: self.status_var.set("正在测试上传速度..."))
            self.root.after(0, lambda: self.progress_var.set(70))
            
            # 测试上传速度
            upload_result = self.tester.test_upload_speed()
            self.root.after(0, lambda: self.upload_var.set(f"{upload_result} MB/s"))
            self.root.after(0, lambda r=upload_result: self.append_result(f"上传速度: {r} MB/s ({round(r * 8, 2)} Mbps)\n"))
            
            self.root.after(0, lambda: self.status_var.set("测试完成!"))
            self.root.after(0, lambda: self.progress_var.set(100))
            
            # 添加测试结果到图表
            self.add_test_result_to_chart(ping_result, download_result, upload_result)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("错误", f"测试过程中发生错误: {str(e)}"))
        finally:
            self.root.after(0, self.reset_ui)
    
    def add_test_result_to_chart(self, ping, download, upload):
        # 将测试结果添加到图表数据中
        self.ping_data[-1] = ping if ping is not None else 0
        self.download_data[-1] = download if download > 0 else 0
        self.upload_data[-1] = upload if upload > 0 else 0
        
        # 重绘图表
        self.draw_chart()
    
    def append_result(self, text):
        self.result_text.insert(tk.END, text)
        self.result_text.see(tk.END)
    
    def reset_ui(self):
        self.is_testing = False
        self.test_button.config(text="开始测试", state="normal")
        # 保持进度条显示一段时间让用户看到完成状态
        self.root.after(1000, lambda: self.progress_var.set(0))

class NetworkSpeedTest:
    def __init__(self):
        self.download_speed = 0
        self.upload_speed = 0
        self.ping_time = 0
        
    def test_ping(self, url="http://www.baidu.com", timeout=5):
        """测试ping值"""
        try:
            start_time = time.time()
            response = requests.get(url, timeout=timeout)
            end_time = time.time()
            self.ping_time = round((end_time - start_time) * 1000, 2)  # 转换为毫秒
            return self.ping_time
        except Exception as e:
            print(f"Ping测试失败: {e}")
            return None
    
    def download_chunk(self, url, size):
        """下载指定大小的数据块"""
        try:
            response = requests.get(url, stream=True, timeout=10)
            downloaded = 0
            start_time = time.time()
            
            for chunk in response.iter_content(chunk_size=8192):
                downloaded += len(chunk)
                if downloaded >= size:
                    break
                    
            end_time = time.time()
            elapsed_time = end_time - start_time
            speed = (downloaded / 1024 / 1024) / elapsed_time if elapsed_time > 0 else 0  # MB/s
            return speed
        except Exception as e:
            print(f"下载测试出错: {e}")
            return 0
    
    def test_download_speed(self):
        """测试下载速度"""
        # 使用多个线程同时下载以获得更准确的速度
        urls = [
            "https://httpbin.org/drip?duration=2&numbytes=1048576",  # 1MB
            "https://httpbin.org/drip?duration=2&numbytes=1048576",
            "https://httpbin.org/drip?duration=2&numbytes=1048576"
        ]
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(self.download_chunk, url, 1048576) for url in urls]
            speeds = [future.result() for future in futures]
        
        self.download_speed = round(sum(speeds), 2)
        return self.download_speed
    
    def upload_chunk(self, size):
        """上传指定大小的数据"""
        try:
            data = b"x" * size  # 创建指定大小的字节数据
            start_time = time.time()
            
            # 使用httpbin测试上传
            response = requests.post(
                "https://httpbin.org/post",
                data={"file": data},
                timeout=10
            )
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            speed = (size / 1024 / 1024) / elapsed_time if elapsed_time > 0 else 0  # MB/s
            return speed
        except Exception as e:
            print(f"上传测试出错: {e}")
            return 0
    
    def test_upload_speed(self):
        """测试上传速度"""
        sizes = [1024*512, 1024*512, 1024*512]  # 3次0.5MB上传
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(self.upload_chunk, size) for size in sizes]
            speeds = [future.result() for future in futures]
        
        self.upload_speed = round(sum(speeds), 2)
        return self.upload_speed

def main():
    root = tk.Tk()
    app = NetworkSpeedTestGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
