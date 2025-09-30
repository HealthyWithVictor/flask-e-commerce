import sys
# 假设您的 app.py 文件在项目根目录
from app import app as application

if __name__ == "__main__":
    # Gunicorn 会调用 application，但如果直接运行这个文件可以用于本地测试
    application.run()