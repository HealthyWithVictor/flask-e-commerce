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
    return (rv[0] if rv else None) if one else rv

def check_column_exists(db, table_name, column_name):
    """[新增] 辅助函数：检查列是否存在"""
    try:
        cursor = db.execute(f"PRAGMA table_info({table_name})")
        columns = [row['name'] for row in cursor.fetchall()]
        return column_name in columns
    except sqlite3.Error as e:
        print(f"检查列是否存在时出错: {e}")
        return False

def init_db():
    """
    [修改] 初始化数据库表的函数，包含安全迁移逻辑。
    """
    db = get_db()
    
    # 1. 创建所有表（如果它们不存在）
    # 注意：这里的 users 表是旧结构，以确保 IF NOT EXISTS 正常工作
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

        /* 使用旧结构，以便安全地检查和迁移 */
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        );

        /* [新增] comments 表 */
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
    ''')
    
    # 2. [修改] 安全迁移逻辑，用于 users 表
    try:
        if not check_column_exists(db, 'users', 'email'):
            # 第1步：添加列，但不带 UNIQUE 约束
            db.execute('ALTER TABLE users ADD COLUMN email TEXT')
            print("迁移：已成功添加 'email' 列到 'users' 表。")
            
            # 第2步：为现有 admin 用户设置一个默认 email
            db.execute("UPDATE users SET email = 'admin@example.com' WHERE username = 'admin' AND email IS NULL")
            print("迁移：已为 'admin' 用户设置默认 'email'。")
            
            # 第3步：现在安全地创建 UNIQUE 索引
            # (SQLite 允许 UNIQUE 索引中存在多个 NULL 值，但为 admin 设置值是好习惯)
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)')
            print("迁移：已为 'email' 列创建 UNIQUE 索引。")
            
        if not check_column_exists(db, 'users', 'role'):
            # 这个操作是安全的，因为它有 DEFAULT 值
            db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'guest'")
            print("迁移：已成功添加 'role' 列到 'users' 表。")

        # 确保现有管理员被正确设置为 'admin' 角色
        db.execute("UPDATE users SET role = 'admin' WHERE username = 'admin' AND (role IS NULL OR role = 'guest')")
        
        db.commit()
        print("数据库迁移检查完成。")
        
    except sqlite3.Error as e:
        db.rollback()
        # 打印修改后的错误信息
        print(f"数据库迁移时发生错误: {e}")

    
    # 3. 检查并创建默认管理员（如果需要）
    admin_user = query_db('SELECT * FROM users WHERE username = ?', ['admin'], one=True)
    if not admin_user:
        # [修改] 使用新结构创建管理员
        try:
            db.execute(
                'INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
                ('admin', 'admin@example.com', generate_password_hash('admin'), 'admin')
            )
            db.commit()
            print("默认管理员 'admin' (密码 'admin') 已创建。")
        except sqlite3.IntegrityError:
             db.rollback()
             print("创建默认管理员失败：'admin' 用户名或 'admin@example.com' 邮箱可能已存在。")
        except sqlite3.Error as e:
            db.rollback()
            print(f"创建默认管理员失败: {e}")
    else:
        print("管理员用户已存在。")

@click.command('init-db')
@with_appcontext
def init_db_command():
    """
    Flask CLI 命令：flask init-db
    用于初始化或安全迁移数据库。
    """
    init_db()
    click.echo('Initialized and/or migrated the database.')

def init_app(app):
    """
    在应用工厂中注册数据库相关函数。
    """
    app.teardown_appcontext(close_db) # 注册应用上下文销毁时的回调
    app.cli.add_command(init_db_command) # 注册 'flask init-db' 命令