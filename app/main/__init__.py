from flask import Blueprint

# 定义蓝图
# 我们告诉 Flask，这个蓝图的模板和静态文件在 app 目录的父目录中
main_bp = Blueprint('main', 
                    __name__, 
                    template_folder='../templates', 
                    static_folder='../static')

# 导入路由，确保蓝图在创建后能找到它们
from . import routes