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
from dotenv import load_dotenv
import uuid
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
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/', prefix='/static/')

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

# --- 用户前台路由：首页 ---
# 找到 app.py 中的 @app.route('/') def home(): 函数，并替换为以下内容：

@app.route('/')
def home():
    """前台首页：展示所有商品，支持分类筛选和分页。"""
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category_id', type=int)
    per_page = 9 # 每页显示 9 个商品
    
    # 1. 构建查询条件
    where_clauses = ['p.stock > 0'] # 默认只显示有库存的商品
    params = []
    
    if category_id:
        where_clauses.append('p.category_id = ?')
        params.append(category_id)
    
    where_sql = 'WHERE ' + ' AND '.join(where_clauses) if where_clauses else ''

    # 2. 查询总数 (用于分页)
    count_sql = f'SELECT COUNT(p.id) FROM products p {where_sql}'
    total_products = query_db(count_sql, params, one=True)['COUNT(p.id)']
    total_pages = math.ceil(total_products / per_page)
    
    # 3. 计算分页偏移量
    offset = (page - 1) * per_page
    
    # 4. 核心查询：通过子查询获取主图 URL
    # SELECT 的第一个字段 now 替换了之前的 p.image_url 
    products_sql = f"""
        SELECT 
            p.*, 
            c.name AS category_name,
            -- 子查询：查找当前商品 ID 最小（通常就是第一张/主图）的图片 URL
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
                           current_page=page, 
                           total_pages=total_pages,
                           total_products=total_products)

# --- 详细页面 ---
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    # 1. 查询主产品信息
    product = query_db('SELECT p.*, c.name AS category_name FROM products p JOIN categories c ON p.category_id = c.id WHERE p.id = ?', 
                       [product_id], one=True)
    
    if product is None:
        return redirect(url_for('home'))

    # 关键修改：查询所有图片，按 is_primary 和 sort_order 排序 (用于轮播)
    images = query_db('SELECT image_url FROM product_images WHERE product_id = ? ORDER BY is_primary DESC, sort_order ASC', 
                      [product_id])
        
    return render_template('product_detail.html', product=product, images=images)


# --- 管理面板：登录/注销 (保持不变) ---
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
    """管理面板首页：商品列表，支持搜索、筛选和分页。"""
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category_id', type=int)
    search_query = request.args.get('query', '', type=str).strip()
    per_page = 10 # 每页显示 10 个商品
    
    # 1. 构建查询条件
    where_clauses = []
    params = []
    
    if category_id:
        where_clauses.append('p.category_id = ?')
        params.append(category_id)

    if search_query:
        # 搜索商品名称或描述
        where_clauses.append('(p.name LIKE ? OR p.description LIKE ?)')
        params.extend([f'%{search_query}%', f'%{search_query}%'])
    
    where_sql = 'WHERE ' + ' AND '.join(where_clauses) if where_clauses else ''

    # 2. 查询总数 (用于分页)
    count_sql = f'SELECT COUNT(p.id) FROM products p {where_sql}'
    total_products = query_db(count_sql, params, one=True)['COUNT(p.id)']
    total_pages = math.ceil(total_products / per_page)
    
    # 3. 计算分页偏移量
    offset = (page - 1) * per_page
    
    # 4. 核心查询：通过子查询获取主图 URL (已添加)
    products_sql = f"""
        SELECT 
            p.*, 
            c.name AS category_name,
            -- 子查询：查找当前商品 ID 最小（主图）的图片 URL
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

    return render_template('admin/index.html', 
                           products=products, 
                           categories=categories,
                           current_category_id=category_id,
                           search_query=search_query,
                           current_page=page, 
                           total_pages=total_pages)

# 管理分类 (admin_categories, admin_delete_category)
@app.route('/admin/categories', methods=['GET', 'POST'])
@login_required
def admin_categories():
    if request.method == 'POST':
        category_name = request.form['name']
        db = get_db()
        db.execute('INSERT INTO categories (name) VALUES (?)', (category_name,))
        db.commit()
        flash(f'分类 "{category_name}" 添加成功!', 'success')
        return redirect(url_for('admin_categories'))
    
    categories = query_db('SELECT * FROM categories')
    return render_template('admin/categories.html', categories=categories)

@app.route('/admin/categories/delete/<int:category_id>')
@login_required
def admin_delete_category(category_id):
    db = get_db()
    
    # 关键修改：从 product_images 表查询并删除所有相关图片文件
    images_to_delete = query_db('''
        SELECT pi.image_url 
        FROM product_images pi
        JOIN products p ON pi.product_id = p.id
        WHERE p.category_id = ?
    ''', [category_id])
    
    for image in images_to_delete:
        image_path = os.path.join('static', image['image_url'])
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except OSError as e:
                print(f"无法删除图片文件 {image_path}: {e}")
                
    # 2. 删除属于该分类的所有商品 (ON DELETE CASCADE 会自动删除 product_images 中的记录)
    db.execute('DELETE FROM products WHERE category_id = ?', (category_id,))
    
    # 3. 删除该分类记录
    db.execute('DELETE FROM categories WHERE id = ?', (category_id,))
    
    db.commit()
    flash('分类及所属商品已删除!', 'success')
    return redirect(url_for('admin_categories'))

# 添加商品 (admin_add_product)
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
        
        # 关键修改：使用 getlist 获取多张图片
        files = request.files.getlist('images') 
        
        db = get_db()
        
        # 1. 插入主产品信息 (image_url 字段传入 None)
        cursor = db.execute('INSERT INTO products (name, description, price, stock, image_url, category_id) VALUES (?, ?, ?, ?, ?, ?)',
                           (name, description, price, stock, None, category_id))
        product_id = cursor.lastrowid # 获取新插入产品的 ID
        
        is_primary = 1 # 标记第一张上传的图片为主图
        
        # 2. 循环处理所有上传的图片
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                
                # 修复逻辑：先定义路径，后保存
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                # 路径兼容性修正：使用 replace('\\', '/') 确保在 Web 上路径正确
                image_url = os.path.join('uploads', filename).replace('\\', '/') 

                # 3. 插入到 product_images 表
                db.execute('INSERT INTO product_images (product_id, image_url, is_primary) VALUES (?, ?, ?)',
                           (product_id, image_url, is_primary))
                is_primary = 0 # 之后的图片都不是主图
        
        db.commit()
        flash('商品及图片添加成功！', 'success')
        return redirect(url_for('admin_index'))
    
    categories = query_db('SELECT * FROM categories')
    return render_template('admin/add_product.html', categories=categories)

# 编辑商品 (admin_edit_product)
# 找到 app.py 中的 @app.route('/admin/edit/<int:product_id>', methods=['GET', 'POST']) 函数，并替换为以下内容：
# 找到 app.py 中的 @app.route('/admin/edit/<int:product_id>', methods=['GET', 'POST']) 函数，并替换为以下内容：
@app.route('/admin/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_product(product_id):
    # 1. 查询商品基础信息
    product_row = query_db('SELECT * FROM products WHERE id = ?', [product_id], one=True)
    if not product_row:
        flash(f'商品ID {product_id} 未找到。', 'danger')
        return redirect(url_for('admin_index')) 
    
    # 将 sqlite3.Row 对象转换为可修改的 Python 字典
    product = dict(product_row)

    # 2. 查询现有图片列表 (is_primary 字段必须包含)
    images = query_db('SELECT id, image_url, is_primary FROM product_images WHERE product_id = ? ORDER BY is_primary DESC, id ASC', 
                      [product_id])

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        category_id = request.form.get('category_id')
        if category_id == '': category_id = None
        
        # 3. 安全地处理数字输入
        try:
            price = float(request.form.get('price', product['price']))
            stock = int(request.form.get('stock', product['stock']))
            
            if price < 0 or stock < 0:
                 raise ValueError
        except (ValueError, TypeError):
            flash('输入错误：请检查价格和库存是否为有效的正数。', 'danger')
            categories = query_db('SELECT * FROM categories')
            
            # 重新填充 product 字典中的字段，以便模板回显错误输入
            product['name'] = name
            product['description'] = description
            product['category_id'] = category_id
            product['price'] = request.form.get('price', product.get('price'))
            product['stock'] = request.form.get('stock', product.get('stock'))
            
            # 🚨 修正：POST 失败时回填模板，必须传入基模板需要的变量
            return render_template('admin/edit_product.html', 
                                   product=product, 
                                   categories=categories, 
                                   images=images,
                                   current_page=1, # 修复 UndefinedError
                                   total_pages=1, # 修复 UndefinedError
                                   search_query='', # 修复 UndefinedError
                                   current_category_id=None) # 修复 UndefinedError

        # 4. 获取新上传的多图
        new_files = request.files.getlist('images') 

        # 5. 提交主产品信息更新
        db = get_db()
        db.execute('UPDATE products SET name = ?, description = ?, price = ?, stock = ?, category_id = ? WHERE id = ?',
                   (name, description, price, stock, category_id, product_id))
        
        # 6. 处理新的多图上传 (追加)
        if any(f.filename for f in new_files):
            current_image_count = query_db('SELECT COUNT(id) FROM product_images WHERE product_id = ?', [product_id], one=True)['COUNT(id)']
            is_primary = current_image_count == 0

            for file in new_files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # 🚨 使用 UUID 确保文件名唯一，防止覆盖
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(file_path)
                    image_url = os.path.join('uploads', unique_filename).replace('\\', '/')
                    
                    # 插入新图片
                    db.execute('INSERT INTO product_images (product_id, image_url, is_primary) VALUES (?, ?, ?)',
                               (product_id, image_url, is_primary))
                    is_primary = False 
            
        db.commit()
        
        flash('商品信息更新成功！', 'success')
        return redirect(url_for('admin_index'))
    
    # GET 请求处理 (修复 UndefinedError 的关键部分)
    categories = query_db('SELECT * FROM categories')
    
    # 🚨 修复 UndefinedError 的关键：为基模板传入必要的占位变量
    return render_template('admin/edit_product.html', 
                           product=product, 
                           categories=categories, 
                           images=images,
                           current_page=1, 
                           total_pages=1,
                           search_query='',
                           current_category_id=None)
# 图片删除路由（用于 edit_product.html）
@app.route('/admin/delete_image/<int:image_id>', methods=['POST'])
@login_required
def admin_delete_image(image_id):
    db = get_db()
    
    # 1. 查找图片信息
    image_record = query_db('SELECT * FROM product_images WHERE id = ?', [image_id], one=True)
    if not image_record:
        flash('图片未找到!', 'danger')
        return redirect(request.referrer or url_for('admin_index'))
        
    product_id = image_record['product_id']
    
    # 2. 删除物理文件
    image_path = os.path.join('static', image_record['image_url'])
    if os.path.exists(image_path):
        try:
            os.remove(image_path)
        except OSError as e:
            print(f"删除图片失败: {image_path} - 错误: {e}")

    # 3. 删除数据库记录
    db.execute('DELETE FROM product_images WHERE id = ?', [image_id])
    db.commit()
    
    # 4. 如果删除的是主图，则需要重新指定主图（将 sort_order 最小的设为主图）
    if image_record['is_primary']:
        db.execute('UPDATE product_images SET is_primary = 1 WHERE product_id = ? AND sort_order = (SELECT MIN(sort_order) FROM product_images WHERE product_id = ?)', 
                   [product_id, product_id])
        db.commit()
    
    flash('图片删除成功!', 'success')
    # 重定向回编辑页面
    return redirect(url_for('admin_edit_product', product_id=product_id))


@app.route('/admin/delete/<int:product_id>')
@login_required
def admin_delete_product(product_id):
    db = get_db()

    # 关键修改：删除所有相关图片文件
    images_to_delete = query_db('SELECT image_url FROM product_images WHERE product_id = ?', [product_id])
    
    for image in images_to_delete:
        image_path = os.path.join('static', image['image_url'])
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except OSError as e:
                print(f"删除图片失败: {image_path} - 错误: {e}")
                
    # 删除商品记录 (ON DELETE CASCADE 会自动删除 product_images 中的记录)
    db.execute('DELETE FROM products WHERE id = ?', [product_id])
    db.commit()
    flash('商品已删除!', 'success')
    return redirect(url_for('admin_index'))

# --- 运行 Flask 服务器 (仅用于开发/调试) ---
if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    # 注意：生产环境请使用 Gunicorn 启动 application
    app.run(debug=True)