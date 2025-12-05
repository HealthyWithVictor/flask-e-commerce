from flask import render_template, request, redirect, url_for, flash, session, g
import math
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

from . import main_bp
from app.db import query_db, get_db
from app.utils import send_contact_email

# --- [新增] 访客登录装饰器 ---
def guest_login_required(f):
    """
    确保访客用户已登录。
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('guest_logged_in'):
            flash('您必须登录才能查看此页面。', 'warning')
            return redirect(url_for('main.guest_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- [新增] 访客用户认证路由 ---

@main_bp.route('/register', methods=['GET', 'POST'])
def guest_register():
    if session.get('guest_logged_in'):
        return redirect(url_for('main.home'))
        
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'guest')",
                (username, email, generate_password_hash(password))
            )
            db.commit()
            
            # 注册后自动登录
            user = query_db('SELECT * FROM users WHERE username = ?', [username], one=True)
            session['guest_logged_in'] = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            
            flash('注册成功！', 'success')
            return redirect(url_for('main.home'))
        except sqlite3.IntegrityError:
            db.rollback()
            flash('用户名或邮箱已存在。', 'danger')
        except Exception as e:
            db.rollback()
            flash(f'注册失败: {e}', 'danger')
            
    return render_template('guest_register.html')

@main_bp.route('/login', methods=['GET', 'POST'])
def guest_login():
    if session.get('guest_logged_in'):
        return redirect(url_for('main.home'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = query_db('SELECT * FROM users WHERE username = ?', [username], one=True)
        
        if user and check_password_hash(user['password_hash'], password):
            session['guest_logged_in'] = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('登录成功！', 'success')
            return redirect(url_for('main.home'))
        else:
            flash('用户名或密码错误。', 'danger')
            
    return render_template('guest_login.html')

@main_bp.route('/logout')
def guest_logout():
    session.pop('guest_logged_in', None)
    session.pop('user_id', None)
    session.pop('username', None)
    flash('您已成功注销。', 'info')
    return redirect(url_for('main.home'))


# --- 用户前台路由：首页 ---
@main_bp.route('/')
def home():
    """
    前台首页：展示所有商品，支持分类筛选、分页和搜索。
    """
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category_id', type=int)
    search_query = request.args.get('search_query', '').strip()
    per_page = 12
    
    where_clauses = ['p.stock >= 0']
    params = []
    
    if category_id:
        where_clauses.append('p.category_id = ?')
        params.append(category_id)

    if search_query:
        where_clauses.append('p.name LIKE ?')
        params.append(f'%{search_query}%')
    
    where_sql = 'WHERE ' + ' AND '.join(where_clauses) if where_clauses else ''

    count_sql = f'SELECT COUNT(p.id) FROM products p {where_sql}'
    total_products_result = query_db(count_sql, params, one=True)
    total_products = total_products_result['COUNT(p.id)'] if total_products_result else 0
    total_pages = math.ceil(total_products / per_page)
    
    offset = (page - 1) * per_page
    
    products_sql = f"""
        SELECT 
            p.*, 
            c.name AS category_name,
            (SELECT image_url FROM product_images WHERE product_id = p.id ORDER BY id ASC LIMIT 1) AS primary_image_url
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        {where_sql}
        ORDER BY p.id DESC 
        LIMIT ? OFFSET ?
    """
    
    product_params = params + [per_page, offset]
    products = query_db(products_sql, product_params)
    categories = query_db('SELECT * FROM categories ORDER BY name')

    return render_template('home.html', 
                           products=products, 
                           categories=categories, 
                           current_category_id=category_id,
                           search_query=search_query,
                           current_page=page, 
                           total_pages=total_pages,
                           total_products=total_products)

# --- contact 路由：处理表单提交和发送 ---
@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    """
    联系页面，POST 请求时调用工具函数发送邮件。
    """
    if request.method == 'POST':
        try:
            # 1. 获取表单数据
            name = request.form.get('name')
            email = request.form.get('email')
            subject = request.form.get('subject')
            company = request.form.get('company')
            phone = request.form.get('phone')
            message_body = request.form.get('message')

            # 2. 调用重构后的邮件发送函数
            send_contact_email(name, email, subject, company, phone, message_body)
            
            flash('您的消息已发送成功，我们会尽快与您联系！', 'success')
            return redirect(url_for('main.contact'))

        except Exception as e:
            # 捕获 utils 中抛出的异常
            print(f"邮件发送失败: {e}")
            flash('邮件发送失败，请稍后重试或检查服务器配置。', 'danger')
            return redirect(url_for('main.contact'))
            
    # GET 请求时渲染 contact.html 模板
    return render_template('contact.html')

# --- 详细页面 [修改] ---
@main_bp.route('/product/<int:product_id>')
def product_detail(product_id):
    """
    产品详情页。
    """
    # [修改] 使用 LEFT JOIN 防止产品无分类时出错
    product = query_db('SELECT p.*, c.name AS category_name FROM products p LEFT JOIN categories c ON p.category_id = c.id WHERE p.id = ?',
                       [product_id], one=True)

    if product is None:
        flash('未找到该产品。', 'warning')
        return redirect(url_for('main.home'))

    images = query_db('SELECT image_url FROM product_images WHERE product_id = ? ORDER BY is_primary DESC, sort_order ASC',
                      [product_id])
    
    # --- [新增] 查询留言 ---
    comments = query_db('SELECT * FROM comments WHERE product_id = ? ORDER BY created_at DESC', [product_id])

    return render_template('product_detail.html', product=product, images=images, comments=comments)

# --- [新增] 留言路由 ---
@main_bp.route('/product/<int:product_id>/comment', methods=['POST'])
@guest_login_required
def add_comment(product_id):
    body = request.form.get('body')
    user_id = session.get('user_id')
    username = session.get('username')
    
    if not body:
        flash('留言内容不能为空。', 'danger')
        return redirect(url_for('main.product_detail', product_id=product_id))
        
    try:
        db = get_db()
        db.execute(
            'INSERT INTO comments (product_id, user_id, username, body) VALUES (?, ?, ?, ?)',
            (product_id, user_id, username, body)
        )
        db.commit()
        flash('留言成功！', 'success')
    except Exception as e:
        db.rollback()
        flash(f'留言失败: {e}', 'danger')
        
    return redirect(url_for('main.product_detail', product_id=product_id))

# --- [新增] 删除评论路由 ---
@main_bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
@guest_login_required
def delete_comment(comment_id):
    user_id = session.get('user_id')

    # 首先获取评论信息以验证用户权限
    comment = query_db('SELECT * FROM comments WHERE id = ?', [comment_id], one=True)

    if not comment:
        flash('评论不存在。', 'danger')
        return redirect(request.referrer or url_for('main.home'))

    # 检查是否是评论的作者
    if comment['user_id'] != user_id:
        flash('您没有权限删除此评论。', 'danger')
        return redirect(request.referrer or url_for('main.home'))

    try:
        db = get_db()
        db.execute('DELETE FROM comments WHERE id = ?', [comment_id])
        db.commit()
        flash('评论已成功删除！', 'success')
    except Exception as e:
        db.rollback()
        flash(f'删除评论失败: {e}', 'danger')

    # 重定向回产品详情页
    return redirect(url_for('main.product_detail', product_id=comment['product_id']))