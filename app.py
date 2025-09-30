from flask import Flask, render_template, request, redirect, url_for, g, session, flash
# 导入 os 用于获取环境变量
import sqlite3
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash 
import math
from functools import wraps
from whitenoise import WhiteNoise
from flask_talisman import Talisman

# --- 新增：加载 .env 文件中的环境变量 ---
from dotenv import load_dotenv
load_dotenv() 

# --- 权限保护装饰器 ---
def login_required(f):
    """确保用户已登录才能访问管理面板路由"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('请先登录才能访问管理面板。', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Flask 应用初始化与配置 ---
app = Flask(__name__)
app.config['DATABASE'] = 'products.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# 🚨 安全修正：从环境变量中加载 SECRET_KEY
# 如果 SECRET_KEY 未设置，则使用一个默认值（但此默认值不应用于生产环境）
app.secret_key = os.environ.get('SECRET_KEY', 'development-fallback-key').encode('utf-8')

# 🚨 启用 WhiteNoise 处理静态文件
# WhiteNoise 将接管静态文件服务，解决 Gunicorn 的问题
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/', prefix='/static/')
# 注意：我们保留此行以确保应用可访问数据库，但在生产环境中应使用权限设置代替
app.wsgi_app.add_files('products.db') 

# 🚨 启用 Talisman 强制 HTTPS 

Talisman(
    app, 
    force_https=True
)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- 数据库辅助函数（保持不变） ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

# --- 用户前台路由 ---
@app.route('/')
def home():
    # 1. 获取分页参数
    page = request.args.get('page', 1, type=int)
    per_page = 9  # 每页显示商品数量
    offset = (page - 1) * per_page
    
    # 2. 获取分类筛选参数
    category_id = request.args.get('category_id', type=int)
    
    # 3. 构建 SQL 查询
    query_condition = ''
    query_args = []
    
    if category_id is not None:
        query_condition = 'WHERE category_id = ?'
        query_args.append(category_id)

    # 4. 查询当前页的商品数据
    products = query_db(f'SELECT * FROM products {query_condition} LIMIT ? OFFSET ?',
                        query_args + [per_page, offset])

    # 5. 查询总商品数（用于分页计算）
    total_products_row = query_db(f'SELECT COUNT(id) AS count FROM products {query_condition}',
                                 query_args, one=True)
    total_products = total_products_row['count']
    
    # 6. 计算总页数
    total_pages = math.ceil(total_products / per_page)

    # 7. 查询所有分类（用于侧边栏导航）
    categories = query_db('SELECT * FROM categories')
    
    return render_template('home.html', 
                           products=products, 
                           categories=categories,
                           current_page=page, 
                           total_pages=total_pages,
                           current_category_id=category_id, 
                           total_products=total_products)

# --- 详细页面 ---
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = query_db('SELECT p.*, c.name AS category_name FROM products p JOIN categories c ON p.category_id = c.id WHERE p.id = ?', 
                       [product_id], one=True)
    if product is None:
        return redirect(url_for('home'))
        
    return render_template('product_detail.html', product=product)


# --- 管理面板：登录/注销 ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # 1. 从数据库中查询用户
        user = query_db('SELECT * FROM users WHERE username = ?', [username], one=True)
        
        # 2. 验证用户是否存在且密码正确
        if user and check_password_hash(user['password_hash'], password):
            session['admin_logged_in'] = True
            flash('登录成功！', 'success')
            return redirect(url_for('admin_index'))
        else:
            flash('用户名或密码错误，请重试。', 'danger')

    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('您已成功注销。', 'info')
    return redirect(url_for('admin_login'))
    
# --- 管理面板路由 (已保护) ---
@app.route('/admin')
@login_required
def admin_index():
    page = request.args.get('page', 1, type=int)
    per_page = 10  # 后台每页显示数量
    
    # 获取筛选和查询参数
    category_id = request.args.get('category_id', type=int)
    search_query = request.args.get('query', '').strip()
    
    # 构建 SQL WHERE 条件和参数列表
    where_clauses = []
    query_args = []
    
    if category_id is not None:
        where_clauses.append('p.category_id = ?')
        query_args.append(category_id)
        
    if search_query:
        where_clauses.append('(p.name LIKE ? OR p.description LIKE ?)')
        query_args.extend(['%' + search_query + '%', '%' + search_query + '%'])

    # 组合 WHERE 条件
    where_condition = ' AND '.join(where_clauses)
    if where_condition:
        where_condition = 'WHERE ' + where_condition

    # 1. 查询总商品数（用于分页计算）
    total_products_row = query_db(f'SELECT COUNT(p.id) AS count FROM products p {where_condition}',
                                 query_args, one=True)
    total_products = total_products_row['count']
    total_pages = math.ceil(total_products / per_page)
    
    offset = (page - 1) * per_page
    
    # 2. 查询当前页的商品数据
    products = query_db(f'''
        SELECT p.*, c.name as category_name 
        FROM products p 
        LEFT JOIN categories c ON p.category_id = c.id 
        {where_condition} 
        LIMIT ? OFFSET ?
    ''', query_args + [per_page, offset])
    
    # 3. 查询所有分类（用于筛选下拉框）
    categories = query_db('SELECT * FROM categories')
    
    return render_template('admin/index.html', 
                           products=products,
                           total_pages=total_pages,
                           current_page=page,
                           categories=categories,
                           current_category_id=category_id,
                           search_query=search_query)

# 管理分类
@app.route('/admin/categories', methods=['GET', 'POST'])
@login_required
def admin_categories():
    if request.method == 'POST':
        category_name = request.form['name']
        db = get_db()
        db.execute('INSERT INTO categories (name) VALUES (?)', (category_name,))
        db.commit()
        return redirect(url_for('admin_categories'))
    
    categories = query_db('SELECT * FROM categories')
    return render_template('admin/categories.html', categories=categories)

# 删除分类
@app.route('/admin/categories/delete/<int:category_id>')
@login_required
def admin_delete_category(category_id):
    db = get_db()
    
    # 1. 查询并删除属于该分类的所有商品的图片文件 (包含 try...except 保护)
    products_to_delete = query_db('SELECT image_url FROM products WHERE category_id = ? AND image_url IS NOT NULL', [category_id])
    
    for product in products_to_delete:
        image_url = product['image_url']
        image_path = os.path.join('static', image_url)
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except OSError as e:
                print(f"无法删除图片文件 {image_path}: {e}")
                
    # 2. 删除属于该分类的所有商品 
    db.execute('DELETE FROM products WHERE category_id = ?', (category_id,))
    
    # 3. 删除该分类记录
    db.execute('DELETE FROM categories WHERE id = ?', (category_id,))
    
    db.commit()
    return redirect(url_for('admin_categories'))

@app.route('/admin/add', methods=['GET', 'POST'])
@login_required
def admin_add_product():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        stock = int(request.form['stock'])
        category_id = request.form.get('category_id')
        if category_id == '': category_id = None
        
        file = request.files.get('image')
        image_url = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            image_url = os.path.join('uploads', filename)

        db = get_db()
        db.execute('INSERT INTO products (name, description, price, stock, image_url, category_id) VALUES (?, ?, ?, ?, ?, ?)',
                   (name, description, price, stock, image_url, category_id))
        db.commit()
        return redirect(url_for('admin_index'))
    
    categories = query_db('SELECT * FROM categories')
    return render_template('admin/add_product.html', categories=categories)

# ... (其他代码保持不变，直到 admin_edit_product) ...

@app.route('/admin/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_product(product_id):
    product = query_db('SELECT * FROM products WHERE id = ?', [product_id], one=True)
    if not product:
        flash(f'商品ID {product_id} 未找到。', 'danger')
        return redirect(url_for('admin_index')) # 确保未找到产品时重定向到列表页

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        stock = int(request.form['stock'])
        category_id = request.form.get('category_id')
        if category_id == '': category_id = None
        
        file = request.files.get('image')
        image_url = product['image_url']
        
        # 新增: 获取删除图片标志
        delete_image_flag = request.form.get('delete_image') 

        # --- 优先级 1: 处理上传新文件请求 (覆盖一切) ---
        if file and allowed_file(file.filename):
            
            # 删除旧文件（无论 delete_image_flag 是否设置）
            if product['image_url']:
                old_image_path = os.path.join('static', product['image_url'])
                if os.path.exists(old_image_path):
                    try:
                        os.remove(old_image_path)
                    except OSError as e:
                        print(f"删除旧图片失败 (新图替换): {old_image_path} - 错误: {e}")
            
            # 保存新文件
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            # 路径兼容性修正：使用 replace('\\', '/') 确保在 Web 上路径正确
            image_url = os.path.join('uploads', filename).replace('\\', '/') 
            
        # --- 优先级 2: 处理删除现有图片请求 (仅在没有新文件上传时执行) ---
        elif delete_image_flag and image_url: 
            # 删除物理文件
            image_path = os.path.join('static', image_url)
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except OSError as e:
                    print(f"删除现有图片失败: {image_path} - 错误: {e}")
            
            # 清除数据库记录
            image_url = None 

        # 提交更新
        db = get_db()
        db.execute('UPDATE products SET name = ?, description = ?, price = ?, stock = ?, image_url = ?, category_id = ? WHERE id = ?',
                   (name, description, price, stock, image_url, category_id, product_id))
        db.commit()
        
        flash('商品信息更新成功！', 'success')
        return redirect(url_for('admin_index'))
    
    categories = query_db('SELECT * FROM categories')
    return render_template('admin/edit_product.html', product=product, categories=categories)

# ... (admin_delete_product 及后续代码保持不变) ...

@app.route('/admin/delete/<int:product_id>')
@login_required
def admin_delete_product(product_id):
    product = query_db('SELECT * FROM products WHERE id = ?', [product_id], one=True)
    if product and product['image_url']:
        image_path = os.path.join('static', product['image_url'])
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except OSError as e:
                print(f"删除图片失败: {image_path} - 错误: {e}")
    
    db = get_db()
    db.execute('DELETE FROM products WHERE id = ?', [product_id])
    db.commit()
    return redirect(url_for('admin_index'))

# --- 运行 Flask 服务器 (仅用于开发/调试) ---
if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    # 注意：生产环境请使用 Gunicorn 启动 application
    app.run(debug=True)