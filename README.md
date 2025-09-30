# <Flask 电子商务示例>

## 🛒 项目简介

这是一个基于 **Flask** 框架开发的轻量级电子商务/产品目录应用。

### 主要功能

* **用户界面**：产品列表分页展示、分类筛选、产品详情页。
* **管理面板**：需要登录保护（用户名/密码）。
    * 商品增删改查 (CRUD)。
    * 支持图片上传、编辑和删除。
    * 分类管理。
* **安全与部署**：
    * 使用 **WhiteNoise** 高效服务静态文件。
    * 使用 **Flask-Talisman** 强制 HTTPS 和增强安全性。
    * Secret Key 安全地从环境变量中加载。

## ⚙️ 环境设置与启动

本项目需要 **Python 3.8+** 环境。

### 1. 克隆仓库

```bash
git clone <https://github.com/HealthyWithVictor/flask-e-commerce.git>
cd <flask-e-commerce>

# 创建虚拟环境
python3 -m venv venv 

# 激活虚拟环境 (macOS/Linux)
source venv/bin/activate 

# 激活虚拟环境 (Windows)
venv\Scripts\activate

pip install -r requirements.txt

# .env 文件内容
# 请使用 os.urandom(32) 或在线工具生成一个随机字符串
SECRET_KEY="在这里输入您的长、随机、安全的 SECRET_KEY"

# 运行数据库初始化脚本
python init_db.py 


