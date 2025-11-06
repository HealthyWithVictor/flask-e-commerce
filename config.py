import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 获取项目根目录的绝对路径
# __file__ 指的是 config.py 所在的路径
# os.path.dirname(__file__) 获取 config.py 所在的目录 (即项目根目录)
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

class Config:
    """
    基础配置类。
    包含所有应用共有的配置，以及从环境变量加载的敏感数据。
    """
    
    # 1. 安全与密钥
    # 强烈建议从环境变量加载，'development-fallback-key' 仅用于开发
    SECRET_KEY = os.environ.get('SECRET_KEY', 'development-fallback-key-please-change-me')
    
    # 2. 数据库配置
    # 使用绝对路径确保无论从哪里运行脚本，数据库路径都正确
    DATABASE = os.path.join(PROJECT_ROOT, 'products.db')

    # 3. 文件上传配置
    # 同样使用绝对路径
    UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024 # 16 MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    # 4. 邮件服务 (Resend) 配置
    # 从环境变量加载
    RESEND_API_KEY = os.environ.get('RESEND_API_KEY', 're_YOUR_API_KEY_HERE')
    SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'info@yourdomain.com')
    RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL', 'admin@yourdomain.com')

    # 5. Talisman 安全配置
    # 从旧 app.py 迁移 [cite: 60-70]
    TALISMAN_CONFIG = {
        'force_https': True, # 在生产中应为 True
        'content_security_policy': {
            'default-src': ["'self'", '*.cloudflare.com'],
            'img-src': ["'self'", 'data:'],
        },
        'content_security_policy_nonce_in': ['script-src'],
        'strict_transport_security': False # 生产中应由 Cloudflare 或 Nginx 处理
    }

class DevelopmentConfig(Config):
    DEBUG = True
    TALISMAN_CONFIG = Config.TALISMAN_CONFIG.copy()
    TALISMAN_CONFIG['force_https'] = False # 开发时禁用 HTTPS 强制

class ProductionConfig(Config):
    DEBUG = False
    # 生产环境应使用更严格的设置
    # TALISMAN_CONFIG['force_https'] 保持为 True

# 映射配置名称到类
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}