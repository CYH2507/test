#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
人脸特征提取脚本（Windows 7兼容版）

此脚本使用OpenCV库从图像中提取人脸边界框，
并将结果保存为JSON格式文件。
适用于Windows 7系统，使用OpenCV 4.2.0.32版本。
"""

import os          # 用于文件和目录操作
import sys         # 用于系统相关功能，如退出程序
import json        # 用于处理JSON数据格式
import argparse    # 用于处理命令行参数
import platform    # 用于检测操作系统
import time        # 用于延时处理

def check_windows_version():
    """检查是否为Windows 7系统"""
    system = platform.system()
    if system != "Windows":
        print("警告: 此脚本主要用于Windows系统")
        return False
    
    version = platform.version()
    if version.startswith("6.1"):  # Windows 7版本号
        print(f"检测到Windows 7系统 (版本: {version})")
        return True
    else:
        print(f"当前系统: {system} {version}")
        return False

def safe_import_cv2():
    """安全导入OpenCV，处理Windows 7兼容性问题"""
    try:
        import cv2
        # 检查OpenCV版本
        version = cv2.__version__
        print(f"OpenCV版本: {version}")
        
        if version >= "4.3.0":
            print("警告: OpenCV版本可能不兼容Windows 7")
            print("建议安装版本: pip install opencv-python==4.2.0.32")
        
        return cv2
    except ImportError as e:
        print(f"错误：无法导入cv2模块 - {e}")
        print("请安装兼容的OpenCV版本：")
        print("pip install opencv-python==4.2.0.32")
        sys.exit(1)
    except OSError as e:
        print(f"错误：OpenCV DLL加载失败 - {e}")
        print("请确保已安装 Microsoft Visual C++ 2015/2019 Redistributable")
        sys.exit(1)
    except Exception as e:
        print(f"未知错误：{e}")
        sys.exit(1)

def safe_import_imutils():
    """安全导入imutils"""
    try:
        from imutils import paths
        return paths
    except ImportError as e:
        print(f"错误：无法导入imutils模块 - {e}")
        print("请安装imutils：")
        print("pip install imutils")
        sys.exit(1)

def get_face_bounding_boxes(image_path, face_cascade, cv2_module):
    """
    从图像中检测人脸并返回边界框
    
    参数:
        image_path: 图像文件路径
        face_cascade: OpenCV人脸检测分类器
        cv2_module: cv2模块对象
    
    返回值:
        list: 包含人脸边界框信息的列表
    """
    try:
        # 使用OpenCV读取图像文件
        image = cv2_module.imread(image_path)
        if image is None:
            print(f"无法读取图像: {image_path}")
            return []
        
        # 将彩色图像转换为灰度图像
        # Haar级联分类器需要灰度图像作为输入
        gray = cv2_module.cvtColor(image, cv2_module.COLOR_BGR2GRAY)
        
        # 使用Haar级联分类器检测图像中的人脸
        faces = face_cascade.detectMultiScale(
            gray,               # 输入的灰度图像
            scaleFactor=1.1,    # 每次图像缩小的比例，用于多尺度检测
            minNeighbors=5,     # 每个人脸矩形保留的邻近矩形数量
            minSize=(30, 30),   # 检测窗口的最小尺寸
            flags=cv2_module.CASCADE_SCALE_IMAGE  # 检测模式标志
        )
        
        # 创建存储人脸信息的列表
        face_data = []
        for i, (x, y, w, h) in enumerate(faces):
            # 为每个人脸创建详细信息字典
            face_info = {
                "face_id": i,                    # 人脸ID，从0开始编号
                "bounding_box": {               # 人脸边界框坐标
                    "top": int(y),              # 上边界Y坐标
                    "right": int(x + w),        # 右边界X坐标
                    "bottom": int(y + h),       # 下边界Y坐标
                    "left": int(x)              # 左边界X坐标
                },
                "width": int(w),                # 人脸宽度
                "height": int(h)                # 人脸高度
            }
            face_data.append(face_info)
        
        return face_data
    except Exception as e:
        print(f"处理图像时出错 {image_path}: {str(e)}")
        return []

def process_images(input_folder, output_folder):
    """
    处理文件夹中的所有图像
    
    参数:
        input_folder: 输入图像文件夹路径
        output_folder: 输出数据文件夹路径
    """
    # 导入cv2和imutils
    cv2 = safe_import_cv2()
    paths = safe_import_imutils()
    
    # 如果输出文件夹不存在，则创建它
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"创建输出文件夹: {output_folder}")
    
    try:
        # 加载OpenCV内置的人脸检测分类器
        # 这是一个预先训练好的Haar级联分类器
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        print(f"加载分类器: {cascade_path}")
        
        face_cascade = cv2.CascadeClassifier(cascade_path)
        
        if face_cascade.empty():
            print("错误：无法加载Haar级联分类器")
            print("可能的解决方案:")
            print("1. 确保OpenCV安装正确")
            print("2. 尝试重新安装: pip install opencv-python==4.2.0.32")
            sys.exit(1)
    except Exception as e:
        print(f"初始化人脸检测器失败: {str(e)}")
        sys.exit(1)
    
    # 定义支持的图像格式扩展名
    supported_formats = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp')
    
    # 手动查找图像文件（避免imutils可能的问题）
    image_paths = []
    print(f"扫描输入文件夹: {input_folder}")
    
    for root, dirs, files in os.walk(input_folder):
        for file in files:
            if file.lower().endswith(supported_formats):
                image_paths.append(os.path.join(root, file))
    
    print(f"找到 {len(image_paths)} 张图像")
    
    # 遍历所有图像文件
    for i, image_path in enumerate(image_paths):
        print(f"正在处理图像 {i+1}/{len(image_paths)}: {os.path.basename(image_path)}")
        
        try:
            # 检测图像中的人脸
            face_data = get_face_bounding_boxes(image_path, face_cascade, cv2)
            
            # 生成对应的输出JSON文件名
            # 将原图像文件名（不含扩展名）加上.json扩展名
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            output_file = os.path.join(output_folder, f"{base_name}.json")
            
            # 将人脸检测结果保存为JSON格式
            with open(output_file, 'w', encoding='utf-8') as f:
                # 构建完整的JSON数据结构
                json.dump({
                    "image_path": image_path,    # 原始图像路径
                    "faces_count": len(face_data),  # 检测到的人脸数量
                    "faces": face_data           # 人脸详细信息列表
                }, f, indent=2, ensure_ascii=False)  # 格式化输出，支持中文字符
            
            print(f"数据已保存至: {output_file}")
            
            # 在Windows 7上添加短暂延迟以避免资源冲突
            time.sleep(0.1)
            
        except Exception as e:
            print(f"处理图像 {image_path} 时出错: {str(e)}")

def main():
    """
    主函数，处理命令行参数并启动图像处理流程
    """
    print("="*50)
    print("Windows 7 人脸检测脚本")
    print("="*50)
    
    # 检查Windows版本
    is_win7 = check_windows_version()
    if is_win7:
        print("系统兼容性检查通过")
    
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(
        description="从图像中提取人脸边界框并保存为JSON格式 (Windows 7兼容版)",
        formatter_class=argparse.RawTextHelpFormatter  # 保持帮助文本的原始格式
    )
    
    # 添加必需的输入参数
    parser.add_argument(
        "-i", "--input",      # 短参数和长参数
        required=True,        # 此参数是必需的
        help="输入图像文件夹路径"  # 参数描述
    )
    
    # 添加必需的输出参数
    parser.add_argument(
        "-o", "--output",     # 短参数和长参数
        required=True,        # 此参数是必需的
        help="输出数据文件夹路径"  # 参数描述
    )
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 检查输入文件夹是否存在
    if not os.path.isdir(args.input):
        print(f"错误: 输入文件夹不存在 - {args.input}")
        sys.exit(1)  # 退出程序，状态码为1表示错误
    
    # 打印处理信息
    print("开始处理图像...")
    print(f"输入文件夹: {args.input}")
    print(f"输出文件夹: {args.output}")
    print("-"*50)
    
    # 调用图像处理函数，捕获可能的异常
    try:
        process_images(args.input, args.output)
        print("\n" + "="*50)
        print("处理完成!")
        print("="*50)
    except KeyboardInterrupt:
        print("\n用户中断处理")
        sys.exit(0)
    except Exception as e:
        # 如果发生异常，打印错误信息并退出
        print(f"\n处理过程中发生严重错误: {str(e)}")
        print("可能的解决方案:")
        print("1. 确保已安装兼容版本: pip install opencv-python==4.2.0.32")
        print("2. 安装Visual C++运行库")
        print("3. 检查图像文件是否损坏")
        sys.exit(1)

# 当脚本直接运行时执行主函数
if __name__ == "__main__":
    main()