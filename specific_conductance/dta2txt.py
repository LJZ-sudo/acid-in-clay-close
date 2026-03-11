import os
import argparse

def batch_rename_dta_to_txt(directory):
    """
    批量将指定目录中的dta文件重命名为txt文件
    
    参数:
    directory (str): 要处理的目录路径
    """
    # 检查目录是否存在
    if not os.path.exists(directory):
        print(f"错误: 目录 '{directory}' 不存在")
        return
    
    # 获取目录中的所有文件
    files = os.listdir(directory)
    
    # 遍历处理每个dta文件
    for filename in files:
        # 检查文件是否是dta文件
        if filename.lower().endswith('.dta'):
            # 构建旧文件路径和新文件路径
            old_path = os.path.join(directory, filename)
            new_filename = os.path.splitext(filename)[0] + '.txt'
            new_path = os.path.join(directory, new_filename)
            
            # 重命名文件
            try:
                os.rename(old_path, new_path)
                print(f"已将 '{filename}' 重命名为 '{new_filename}'")
            except Exception as e:
                print(f"无法将 '{filename}' 重命名为 '{new_filename}': {e}")

if __name__ == "__main__":
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='批量将dta文件重命名为txt文件')
    parser.add_argument('directory', nargs='?', default='data/S8-3-20-1-1/300-140K 1K-min', help='要处理的目录路径(默认: data/S8-3-20-1-1/300-140K 1K-min)')
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 执行批量重命名
    batch_rename_dta_to_txt(args.directory)    