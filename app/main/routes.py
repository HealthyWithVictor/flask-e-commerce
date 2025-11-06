from flask import render_template, request, redirect, url_for, flash
import math
from . import main_bp
from app.db import query_db
from app.utils import send_contact_email

# --- 用户前台路由：首页 ---
@main_bp.route('/')
def home():
    """
    前台首页：展示所有商品，支持分类筛选、分页和搜索。 [cite: 9-52]
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
    联系页面，POST 请求时调用工具函数发送邮件。 [cite: 13-68]
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

# --- 详细页面 ---
@main_bp.route('/product/<int:product_id>')
def product_detail(product_id):
    """
    产品详情页。 [cite: 20-33]
    """
    product = query_db('SELECT p.*, c.name AS category_name FROM products p JOIN categories c ON p.category_id = c.id WHERE p.id = ?',
                       [product_id], one=True)

    if product is None:
        flash('未找到该产品。', 'warning')
        return redirect(url_for('main.home'))

    images = query_db('SELECT image_url FROM product_images WHERE product_id = ? ORDER BY is_primary DESC, sort_order ASC',
                      [product_id])

    return render_template('product_detail.html', product=product, images=images)