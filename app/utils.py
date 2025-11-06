import os
import resend
from resend.exceptions import ResendError
from markupsafe import Markup
from flask import current_app

def allowed_file(filename):
    """
    检查文件扩展名是否在允许的列表中。
    """
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', set())
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def nl2br_filter(s):
    """
    Jinja 过滤器：将换行符 \n 替换为 <br> 标签。 [cite: 8-57]
    """
    if s is None:
        return ""
    s = str(s).replace('\n', '<br>')
    return Markup(s)

def send_contact_email(name, email, subject, company, phone, message_body):
    """
    封装发送联系邮件的逻辑。 [cite: 13-68]
    从 current_app.config 获取配置。
    """
    
    # 1. 获取配置
    api_key = current_app.config.get('RESEND_API_KEY')
    sender_email = current_app.config.get('SENDER_EMAIL')
    recipient_email = current_app.config.get('RECIPIENT_EMAIL')

    if not all([api_key, sender_email, recipient_email]):
        print("邮件配置不完整 (RESEND_API_KEY, SENDER_EMAIL, RECIPIENT_EMAIL)。")
        raise ValueError("缺少邮件服务器配置。")

    resend.api_key = api_key

    # 2. 构造邮件内容
    full_subject = f"[网站咨询] {subject or '无主题'} - From: {name}"
    html_content = f"""
    <html><body>
        <h2>收到来自网站的新的咨询：</h2>
        <p><strong>姓名:</strong> {name}</p>
        <p><strong>公司:</strong> {company or '未填写'}</p>
        <p><strong>电话:</strong> {phone or '未填写'}</p>
        <p><strong>客户邮箱:</strong> {email}</p>
        <p><strong>主题:</strong> {subject or '无主题'}</p>
        <hr>
        <h3>消息正文：</h3>
        <p>{message_body.replace('\n', '<br>')}</p>
    </body></html>
    """

    # 3. 使用 Resend API 发送
    try:
        resend.Emails.send({
            "from": f"{name} <{sender_email}>", 
            "to": [recipient_email],
            "subject": full_subject,
            "html": html_content,
            "headers": {
                "Reply-To": email 
            }
        })
        return True # 发送成功
    except ResendError as e:
        print(f"Resend 邮件发送失败: {e}")
        raise e # 抛出异常，由路由处理
    except Exception as e:
        print(f"邮件发送发生通用错误: {e}")
        raise e # 抛出异常，由路由处理