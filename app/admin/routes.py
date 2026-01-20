import os
import uuid
import math
import sqlite3
from functools import wraps
from flask import (
    render_template, request, redirect, url_for, session, flash, 
    current_app
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from . import admin_bp
from app.db import query_db, get_db
from app.utils import allowed_file

# --- 权限保护装饰器 ---
def login_required(f):
    """
    确保用户已登录才能访问管理面板路由。
    注意：url_for('.admin_login') 中的 '.' 表示蓝图内的路由。
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('请先登录才能访问管理面板。', 'warning')
            return redirect(url_for('admin.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- 管理面板：登录/注销 ---
@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    """
    管理员登录页。
    """
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = query_db('SELECT * FROM users WHERE username = ?', [username], one=True)
        
        # --- [修改] 增加角色检查 ---
        if user and check_password_hash(user['password_hash'], password) and user['role'] == 'admin':
            session['admin_logged_in'] = True
            flash('登录成功！', 'success')
            return redirect(url_for('admin.admin_index'))
        else:
            flash('用户名或密码错误，或您没有管理员权限。', 'danger')

    return render_template('login.html') # 模板在 'admin/' 目录中

@admin_bp.route('/logout')
@login_required # 登出也需要先登录
def admin_logout():
    """
    管理员登出。
    """
    session.pop('admin_logged_in', None)
    flash('您已成功注销。', 'info')
    return redirect(url_for('admin.admin_login'))
    
# --- 管理面板路由 (已保护) ---

@admin_bp.route('/') # 对应 /admin/
@admin_bp.route('/index') # 对应 /admin/index
@login_required
def admin_index():
    """
    管理面板首页：商品列表。
    """
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category_id', type=int)
    search_query = request.args.get('query', '', type=str).strip()
    per_page = 10
    
    where_clauses = []
    params = []
    
    if category_id:
        where_clauses.append('p.category_id = ?')
        params.append(category_id)

    if search_query:
        where_clauses.append('(p.name LIKE ? OR p.description LIKE ?)')
        params.extend([f'%{search_query}%', f'%{search_query}%'])
    
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

    return render_template('index.html', 
                           products=products, 
                           categories=categories,
                           current_category_id=category_id,
                           search_query=search_query,
                           current_page=page, 
                           total_pages=total_pages)

@admin_bp.route('/categories', methods=['GET', 'POST'])
@login_required
def admin_categories():
    """
    管理分类 (添加)。
    """
    if request.method == 'POST':
        category_name = request.form.get('name', '').strip()
        
        if not category_name:
            flash('分类名称不能为空。', 'danger')
            return redirect(url_for('admin.admin_categories'))
            
        existing_category = query_db('SELECT id FROM categories WHERE name = ?', [category_name], one=True)
        if existing_category:
            flash(f'分类名称 "{category_name}" 已存在。', 'warning')
            return redirect(url_for('admin.admin_categories'))

        db = get_db()
        try:
            db.execute('INSERT INTO categories (name) VALUES (?)', (category_name,))
            db.commit()
            flash(f'分类 "{category_name}" 添加成功!', 'success')
        except sqlite3.IntegrityError:
            db.rollback()
            flash(f'分类名称 "{category_name}" 已存在 (并发冲突)。', 'warning')
        except Exception as e:
            db.rollback()
            flash(f'添加失败: {e}', 'danger')
            
        return redirect(url_for('admin.admin_categories'))
    
    categories = query_db('SELECT * FROM categories ORDER BY name')
    return render_template('categories.html', categories=categories)

@admin_bp.route('/categories/edit/<int:category_id>', methods=['POST'])
@login_required
def admin_edit_category(category_id):
    """
    编辑分类名称。
    """
    new_name = request.form.get('new_category_name', '').strip()
    
    if not new_name:
        flash('分类名称不能为空。', 'danger')
        return redirect(url_for('admin.admin_categories'))
        
    existing_category = query_db('SELECT id FROM categories WHERE name = ? AND id != ?', [new_name, category_id], one=True)
    if existing_category:
        flash(f'分类名称 "{new_name}" 已存在。', 'warning')
        return redirect(url_for('admin.admin_categories'))

    db = get_db()
    try:
        db.execute('UPDATE categories SET name = ? WHERE id = ?', (new_name, category_id))
        db.commit()
        flash('分类名称更新成功！', 'success')
    except sqlite3.Error as e:
        db.rollback()
        flash(f'数据库更新失败: {e}', 'danger')

    return redirect(url_for('admin.admin_categories'))

@admin_bp.route('/categories/delete/<int:category_id>')
@login_required
def admin_delete_category(category_id):
    """
    彻底删除分类及其所有相关数据
    """
    db = get_db()
    try:
        # 1. 获取该分类下的所有商品ID
        products = query_db('SELECT id FROM products WHERE category_id = ?', [category_id])
        product_ids = [product['id'] for product in products]
        
        # 2. 删除这些商品的所有图片文件
        upload_folder = current_app.config['UPLOAD_FOLDER']
        
        if product_ids:
            # 获取所有相关图片
            placeholders = ','.join('?' for _ in product_ids)
            images_to_delete = query_db(
                f'SELECT image_url FROM product_images WHERE product_id IN ({placeholders})',
                product_ids
            )
            
            # 删除物理图片文件
            for image in images_to_delete:
                filename = os.path.basename(image['image_url'])
                image_path = os.path.join(upload_folder, filename)
                if os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                    except OSError as e:
                        print(f"无法删除图片文件 {image_path}: {e}")
            
            # 3. 先删除商品图片记录（避免外键约束问题）
            db.execute(f'DELETE FROM product_images WHERE product_id IN ({placeholders})', product_ids)
            
            # 4. 再删除商品评论（避免外键约束问题）
            db.execute(f'DELETE FROM comments WHERE product_id IN ({placeholders})', product_ids)
            
            # 5. 最后删除商品
            db.execute(f'DELETE FROM products WHERE category_id = ?', [category_id])
        
        # 6. 删除分类
        db.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        db.commit()
        flash('分类及所有相关商品、图片和评论已彻底删除!', 'success')
    except sqlite3.Error as e:
        db.rollback()
        flash(f'删除分类失败: {e}', 'danger')
        print(f"数据库错误: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        db.rollback()
        flash(f'删除过程中发生错误: {e}', 'danger')
        print(f"一般错误: {e}")
        import traceback
        traceback.print_exc()
    return redirect(url_for('admin.admin_categories'))

@admin_bp.route('/add', methods=['GET', 'POST'])
@login_required
def admin_add_product():
    """
    添加商品。
    **重构修复**：使用绝对路径配置来保存文件。
    """
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        stock = int(request.form['stock'])
        category_id = request.form.get('category_id')
        if category_id == '': category_id = None
        
        files = request.files.getlist('images') 
        upload_folder = current_app.config['UPLOAD_FOLDER']
        
        db = get_db()
        cursor = None
        try:
            cursor = db.execute('INSERT INTO products (name, description, price, stock, image_url, category_id) VALUES (?, ?, ?, ?, ?, ?)',
                               (name, description, price, stock, None, category_id))
            product_id = cursor.lastrowid
            
            is_primary = 1
            
            for file in files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # 使用 UUID 确保文件名唯一
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    
                    # 使用 config 中的绝对路径保存
                    file_path = os.path.join(upload_folder, unique_filename)
                    file.save(file_path)
                    
                    # 数据库中只存相对路径
                    image_url = os.path.join('uploads', unique_filename).replace('\\', '/') 

                    db.execute('INSERT INTO product_images (product_id, image_url, is_primary) VALUES (?, ?, ?)',
                               (product_id, image_url, is_primary))
                    is_primary = 0
            
            db.commit()
            flash('商品及图片添加成功！', 'success')
            return redirect(url_for('admin.admin_index'))
            
        except Exception as e:
            db.rollback()
            flash(f'添加商品时出错: {e}', 'danger')
            print(f"Error in admin_add_product: {e}")
    
    categories = query_db('SELECT * FROM categories')
    return render_template('add_product.html', categories=categories)

@admin_bp.route('/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_product(product_id):
    """
    编辑商品。
    **重构修复**：使用绝对路径配置来保存文件。
    """
    product_row = query_db('SELECT * FROM products WHERE id = ?', [product_id], one=True)
    if not product_row:
        flash(f'商品ID {product_id} 未找到。', 'danger')
        return redirect(url_for('admin.admin_index')) 
    
    product = dict(product_row)
    images = query_db('SELECT id, image_url, is_primary FROM product_images WHERE product_id = ? ORDER BY is_primary DESC, id ASC', 
                      [product_id])

    if request.method == 'POST':
        db = get_db()
        try:
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            category_id = request.form.get('category_id')
            if category_id == '': category_id = None
            price = float(request.form.get('price', product['price']))
            stock = int(request.form.get('stock', product['stock']))
            
            db.execute('UPDATE products SET name = ?, description = ?, price = ?, stock = ?, category_id = ? WHERE id = ?',
                       (name, description, price, stock, category_id, product_id))
            
            new_files = request.files.getlist('images') 
            upload_folder = current_app.config['UPLOAD_FOLDER']

            if any(f.filename for f in new_files):
                current_image_count = query_db('SELECT COUNT(id) FROM product_images WHERE product_id = ?', [product_id], one=True)['COUNT(id)']
                is_primary = current_image_count == 0

                for file in new_files:
                    if file and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4().hex}_{filename}"
                        
                        file_path = os.path.join(upload_folder, unique_filename)
                        file.save(file_path)
                        image_url = os.path.join('uploads', unique_filename).replace('\\', '/')
                        
                        db.execute('INSERT INTO product_images (product_id, image_url, is_primary) VALUES (?, ?, ?)',
                                   (product_id, image_url, is_primary))
                        is_primary = False 
            
            db.commit()
            flash('商品信息更新成功！', 'success')
            return redirect(url_for('admin.admin_index'))

        except (ValueError, TypeError) as e:
            db.rollback()
            flash(f'输入错误：请检查价格和库存。{e}', 'danger')
            # 回填错误数据
            product['name'] = request.form.get('name')
            product['description'] = request.form.get('description')
            product['price'] = request.form.get('price')
            product['stock'] = request.form.get('stock')
            product['category_id'] = request.form.get('category_id')
        
        except Exception as e:
            db.rollback()
            flash(f'更新时发生严重错误: {e}', 'danger')

    categories = query_db('SELECT * FROM categories')
    return render_template('edit_product.html', 
                           product=product, 
                           categories=categories, 
                           images=images,
                           current_page=1, # 修复基模板 UndefinedError
                           total_pages=1, 
                           search_query='',
                           current_category_id=None)

@admin_bp.route('/delete_image/<int:image_id>', methods=['POST'])
@login_required
def admin_delete_image(image_id):
    """
    删除单张图片。
    **重构修复**：使用绝对路径配置来删除文件。
    """
    db = get_db()
    
    image_record = query_db('SELECT * FROM product_images WHERE id = ?', [image_id], one=True)
    if not image_record:
        flash('图片未找到!', 'danger')
        return redirect(request.referrer or url_for('admin.admin_index'))
        
    product_id = image_record['product_id']
    
    try:
        # 1. 删除物理文件
        upload_folder = current_app.config['UPLOAD_FOLDER']
        # image_record['image_url'] 是 'uploads/filename.jpg'
        filename = os.path.basename(image_record['image_url'])
        image_path = os.path.join(upload_folder, filename)
        
        if os.path.exists(image_path):
            os.remove(image_path)

        # 2. 删除数据库记录
        db.execute('DELETE FROM product_images WHERE id = ?', [image_id])
        
        # 3. 如果删除的是主图，重新指定主图
        if image_record['is_primary']:
            other_image = query_db('SELECT id FROM product_images WHERE product_id = ? ORDER BY id ASC LIMIT 1', [product_id], one=True)
            if other_image:
                db.execute('UPDATE product_images SET is_primary = 1 WHERE id = ?', [other_image['id']])
        
        db.commit()
        flash('图片删除成功!', 'success')
        
    except Exception as e:
        db.rollback()
        flash(f'删除图片时出错: {e}', 'danger')

    return redirect(url_for('admin.admin_edit_product', product_id=product_id))

@admin_bp.route('/delete/<int:product_id>')
@login_required
def admin_delete_product(product_id):
    """
    删除整个商品。
    **重构修复**：使用绝对路径配置来删除文件。
    """
    db = get_db()

    # 1. 查询所有相关图片
    images_to_delete = query_db('SELECT image_url FROM product_images WHERE product_id = ?', [product_id])
    
    try:
        # 2. 删除物理文件
        upload_folder = current_app.config['UPLOAD_FOLDER']
        for image in images_to_delete:
            filename = os.path.basename(image['image_url'])
            image_path = os.path.join(upload_folder, filename)
            if os.path.exists(image_path):
                os.remove(image_path)
                
        # 3. 删除商品记录 (ON DELETE CASCADE 会自动删除 product_images)
        db.execute('DELETE FROM products WHERE id = ?', [product_id])
        db.commit()
        flash('商品已删除!', 'success')
        
    except Exception as e:
        db.rollback()
        flash(f'删除商品时出错: {e}', 'danger')
        
    return redirect(url_for('admin.admin_index'))