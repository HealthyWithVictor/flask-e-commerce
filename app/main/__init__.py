from flask import Blueprint, session

# 定义蓝图
# 我们告诉 Flask，这个蓝图的模板和静态文件在 app 目录的父目录中
main_bp = Blueprint('main', 
                    __name__, 
                    template_folder='../templates', 
                    static_folder='../static')

# --- [新增] 上下文处理器 ---
@main_bp.context_processor
def inject_guest_session():
    """ 将访客会话信息注入到所有 main_bp 的模板 """
    return dict(
        guest_logged_in=session.get('guest_logged_in'),
        username=session.get('username')
    )

# 导入路由，确保蓝图在创建后能找到它们
from . import routes