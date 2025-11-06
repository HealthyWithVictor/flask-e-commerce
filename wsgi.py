from app import create_app
import os

# Gunicorn/uWSGI 会查找名为 'application' 的可调用对象
# 我们从环境变量加载生产配置
config_name = os.environ.get('FLASK_CONFIG', 'production')
application = create_app(config_name)