import os
from flask import Flask, render_template
from config import config_by_name
import whitenoise

# 导入扩展实例
from .extensions import talisman

# 导入数据库工具
from . import db as db_helper

# 导入工具函数
from . import utils

def create_app(config_name='default'):
    """
    应用工厂函数
    """
    
    # 1. 创建应用实例
    # __name__ 是 'app'
    # 我们告诉 Flask 静态文件和模板文件在父目录中
    app = Flask(__name__, 
                static_folder='../static', 
                template_folder='../templates')

    # 2. 加载配置
    config_obj = config_by_name.get(config_name, 'default')
    app.config.from_object(config_obj)

    # 3. 初始化扩展
    talisman_config = app.config.get('TALISMAN_CONFIG', {})
    talisman.init_app(app, **talisman_config)
    
    # 初始化 WhiteNoise [cite: 8-36]
    # 我们需要告诉 WhiteNoise 静态文件的根目录在哪里
    static_root = os.path.join(app.root_path, '..', 'static')
    app.wsgi_app = whitenoise.WhiteNoise(app.wsgi_app, root=static_root, prefix='/static/')


    # 确保上传目录也被 WhiteNoise 服务 (如果需要的话)
    upload_path = app.config['UPLOAD_FOLDER']
    if os.path.exists(upload_path):
        app.wsgi_app.add_files(upload_path, prefix='static/uploads/')

    # 4. 初始化数据库
    db_helper.init_app(app)

    # 5. 注册 Jinja 过滤器
    app.jinja_env.filters['nl2br'] = utils.nl2br_filter

    # 6. 注册蓝图
    from .main import main_bp
    app.register_blueprint(main_bp)

    from .admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # 7. 注册错误处理器
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404 # 假设您有一个 404.html 模板

    return app