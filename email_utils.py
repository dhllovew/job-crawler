#邮件发送功能
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import logging

# 配置日志
logger = logging.getLogger('email_utils')

def send_verification_email(email, token):
    """发送验证邮件"""
    try:
        # 邮件服务器配置
        smtp_server = os.environ.get('SMTP_SERVER', 'smtp.qq.com')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        email_user = os.environ.get('EMAIL_USER')
        email_pwd = os.environ.get('EMAIL_PWD')
        
        # 验证链接
        verification_url = f"https://your-username.github.io/your-repo/verify.html?token={token}"
        
        # 创建邮件
        msg = MIMEMultipart()
        msg['From'] = email_user
        msg['To'] = email
        msg['Subject'] = "请验证您的邮箱 - 求职助手服务"
        
        # 邮件正文
        body = f"""
        <html>
        <body>
            <h2>欢迎使用求职助手服务！</h2>
            <p>感谢您注册我们的服务。请点击以下链接完成邮箱验证：</p>
            <p><a href="{verification_url}">{verification_url}</a></p>
            <p>如果您没有注册此服务，请忽略此邮件。</p>
            <p>此致,<br>求职助手团队</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # 发送邮件
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_user, email_pwd)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"已发送验证邮件至: {email}")
        return True
    except Exception as e:
        logger.error(f"发送验证邮件失败: {str(e)}")
        return False

def send_job_report(email, html_content, attachment_path=None):
    """发送职位报告邮件"""
    try:
        # 邮件服务器配置
        smtp_server = os.environ.get('SMTP_SERVER', 'smtp.qq.com')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        email_user = os.environ.get('EMAIL_USER')
        email_pwd = os.environ.get('EMAIL_PWD')
        
        # 创建邮件
        msg = MIMEMultipart()
        msg['From'] = email_user
        msg['To'] = email
        msg['Subject'] = f"求职报告更新 - {datetime.now().strftime('%Y-%m-%d')}"
        
        # 邮件正文
        msg.attach(MIMEText(html_content, 'html'))
        
        # 添加附件
        if attachment_path:
            with open(attachment_path, 'rb') as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
            msg.attach(part)
            logger.info(f"已添加附件: {attachment_path}")
        
        # 发送邮件
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_user, email_pwd)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"已发送职位报告至: {email}")
        return True
    except Exception as e:
        logger.error(f"发送职位报告失败: {str(e)}")
        return False
