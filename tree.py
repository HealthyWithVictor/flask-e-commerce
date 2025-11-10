import os
import sys

# 定义输出文件名
OUTPUT_FILENAME = "project_directory_tree.txt"

def print_directory_tree(startpath, exclude_dirs, output_file):
    """
    Prints the directory tree starting from startpath to the specified output_file,
    excluding directories specified in exclude_dirs.
    """
    # 集合用于更快地查找排除目录
    excluded = set(exclude_dirs)
    
    if not os.path.isdir(startpath):
        output_file.write(f"Error: '{startpath}' is not a valid directory.\n")
        return

    output_file.write(f"Project Tree for: {startpath}\n")
    output_file.write("-" * 30 + "\n")
    output_file.write(f"{startpath}\n")

    # os.walk 遍历目录树
    for root, dirs, files in os.walk(startpath):
        
        # 1. 剪枝：原地修改 `dirs` 列表，防止 os.walk 深入到排除的目录
        dirs[:] = [d for d in dirs if d not in excluded]

        # 计算当前目录相对于起始路径的深度
        # 替换 startpath 为空，然后计算路径分隔符的数量
        level = root.replace(startpath, '').count(os.sep)
        
        # 跳过根目录，因为它已经被打印过了
        if root == startpath:
            continue
            
        # 确定当前级别的缩进
        # '|   ' 用于前一级别的缩进，'|-- ' 用于当前条目
        indent = '|   ' * level + '|-- '

        # 2. 写入当前目录名
        # os.path.basename(root) 获取路径的最后一个部分
        output_file.write(f"{indent}{os.path.basename(root)}/\n")

        # 3. 写入文件
        # 文件的缩进比目录深一级
        file_indent = '|   ' * (level + 1) + '|-- '
        for f in files:
            output_file.write(f"{file_indent}{f}\n")

if __name__ == "__main__":
    # 定义要排除的目录列表
    # 'venv' 是 Flask/Python 项目的关键排除项
    EXCLUDE_DIRS = ['venv', '.git', '__pycache__', '.pytest_cache']
    
    # 将当前目录 ('.') 作为起始路径
    start_directory = '.'
    
    # 使用 `with open(...)` 确保文件在操作完成后会被正确关闭
    try:
        with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
            print(f"Generating directory tree and saving to: {OUTPUT_FILENAME}")
            print_directory_tree(start_directory, EXCLUDE_DIRS, f)
            print("Done!")
    except Exception as e:
        print(f"An error occurred: {e}")