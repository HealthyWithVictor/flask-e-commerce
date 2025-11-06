import sqlite3
import click
from flask import current_app, g
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash # 用于创建初始管理员

def get_db():
    """
    获取当前应用上下文的数据库连接。
    如果连接不存在，则创建一个新连接。
    """
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    """
    关闭数据库连接。
    """
    db = g.pop('db', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    """
    执行数据库查询。
    """
    db = get_db()
    cur = db.execute(query, args)
    rv = cur.fetchall()
    # 注意：在重构中，我们保持了原始 app.py 中移除 cur.close() 的逻辑 [cite: 9-33]
    return (rv[0] if rv else None) if one else rv

def init_db():
    """
    初始化数据库表的函数。
    """
    db = get_db()
    
    # 完整的数据库 Schema (从 init_db.py 迁移而来)
    db.executescript('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            stock INTEGER NOT NULL,
            image_url TEXT,
            category_id INTEGER,
            FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS product_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            image_url TEXT NOT NULL,
            is_primary INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        );
    ''')
    
    # 检查是否已存在管理员
    admin_user = query_db('SELECT * FROM users WHERE username = ?', ['admin'], one=True)
    if not admin_user:
        # 创建默认管理员 (admin / admin)
        db.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            ('admin', generate_password_hash('admin'))
        )
        db.commit()
        print("Default admin user 'admin' with password 'admin' created.")
    else:
        print("Admin user already exists.")

@click.command('init-db')
@with_appcontext
def init_db_command():
    """
    Flask CLI 命令：flask init-db
    用于清空并重建数据库表。
    """
    init_db()
    click.echo('Initialized the database.')

def init_app(app):
    """
    在应用工厂中注册数据库相关函数。
    """
    app.teardown_appcontext(close_db) # 注册应用上下文销毁时的回调
    app.cli.add_command(init_db_command) # 注册 'flask init-db' 命令