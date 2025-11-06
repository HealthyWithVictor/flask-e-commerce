import os
from app import create_app

# 从环境变量或默认'development'获取配置
config_name = os.environ.get('FLASK_CONFIG', 'development')
app = create_app(config_name)

if __name__ == '__main__':
    # 确保上传目录存在 [cite: 63-27]
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
        
    # 运行开发服务器
    app.run(debug=app.config.get('DEBUG', True))