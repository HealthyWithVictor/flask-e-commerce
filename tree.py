import os
import sys

def generate_tree(startpath, output_filename='directory_structure.txt'):
    """
    递归地遍历目录结构并将其保存到文件中。
    """
    
    # 获取要遍历的根目录，如果未提供则使用当前目录
    root_dir = startpath if startpath else os.getcwd()

    if not os.path.isdir(root_dir):
        print(f"错误：目录 '{root_dir}' 不存在。", file=sys.stderr)
        return

    # 要排除的目录名称（例如，如果您不想看到 .git 文件夹）
    # 在 Python 脚本中，直接在 os.walk 中跳过它们更高效
    EXCLUDE_DIRS = ['.git', '__pycache__', 'node_modules']
    
    print(f"正在生成 '{root_dir}' 的目录结构到 {output_filename} ...")

    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(f"项目目录结构: {root_dir}\n")
        f.write("-" * 30 + "\n")
        
        # os.walk(top, topdown=True, onerror=None, followlinks=False)
        for root, dirs, files in os.walk(root_dir):
            
            # 使用列表切片来修改 dirs，以便 os.walk 知道要跳过哪些目录
            # 这比在循环内检查更高效
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            # 计算当前深度和缩进
            # 如果 root_dir 是 "."，则 level 只是路径分隔符的计数
            # 如果是绝对路径，您可能需要更复杂的计算
            level = root.replace(root_dir, '').count(os.sep)
            indent = ' ' * 4 * (level)

            # 写入当前目录
            # 仅在不是根目录本身的情况下打印目录名（因为我们在开头已经打印了）
            if root != root_dir:
                f.write(f'{indent}**{os.path.basename(root)}/**\n')
            else:
                f.write(f'{root_dir}/\n')
            
            # 写入文件
            subindent = ' ' * 4 * (level + 1)
            for file in files:
                # 排除隐藏文件
                if not file.startswith('.'):
                    f.write(f'{subindent}{file}\n')

    print(f"完成。目录结构已保存到 {output_filename}")


if __name__ == "__main__":
    # 允许通过命令行参数指定目录
    # python generate_tree.py /path/to/your/project
    target_path = sys.argv[1] if len(sys.argv) > 1 else "."
    generate_tree(target_path)