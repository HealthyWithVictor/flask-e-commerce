from flask import Blueprint

# 定义蓝图，并指定 URL 前缀 /admin
# 模板路径指向 ../templates/admin，这样在路由中可直接用 'login.html'
admin_bp = Blueprint('admin', 
                     __name__, 
                     template_folder='../templates/admin',
                     static_folder='../static')

# 导入路由
from . import routes