"""
邮箱验证码工具
功能：生成6位数字验证码，发送到用户邮箱
"""
import smtplib
import random
import string
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict
import streamlit as st

# 存储验证码的临时字典（key:邮箱, value:{code:验证码, expires:过期时间}）
# 生产环境建议用Redis，这里用字典简化
if 'verification_codes' not in st.session_state:
    st.session_state.verification_codes = {}


class EmailVerification:
    def __init__(self, sender_email: str, sender_password: str, smtp_server: str = "smtp.qq.com", smtp_port: int = 465):
        """
        初始化邮件发送器
        :param sender_email: 发件人邮箱（如你的QQ邮箱）
        :param sender_password: 邮箱授权码（不是登录密码！）
        :param smtp_server: SMTP服务器地址
        :param smtp_port: SMTP端口
        """
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port

    def generate_code(self, length: int = 6) -> str:
        """生成6位数字验证码"""
        return ''.join(random.choices(string.digits, k=length))

    def send_verification_email(self, to_email: str) -> bool:
        """
        发送验证码邮件
        :param to_email: 接收验证码的邮箱
        :return: 是否发送成功
        """
        try:
            # 生成6位数字验证码
            code = self.generate_code()

            # 存储验证码，5分钟过期
            st.session_state.verification_codes[to_email] = {
                'code': code,
                'expires_at': time.time() + 300  # 300秒 = 5分钟
            }

            # 创建邮件内容
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = to_email
            msg['Subject'] = '【智能客服】邮箱验证码'

            # HTML格式的邮件正文
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; padding: 20px;">
                    <h2 style="color: #333;">智能客服 - 邮箱验证</h2>
                    <p>您好！</p>
                    <p>您的验证码是：</p>
                    <div style="background-color: #f0f0f0; padding: 20px; font-size: 36px; 
                                font-weight: bold; text-align: center; letter-spacing: 10px;
                                border-radius: 10px; margin: 20px 0;">
                        {code}
                    </div>
                    <p>验证码有效期为<strong style="color: #ff0000;">5分钟</strong>，请尽快完成注册。</p>
                    <p style="color: #666; font-size: 12px;">如果这不是您的操作，请忽略此邮件。</p>
                </body>
            </html>
            """

            msg.attach(MIMEText(html_content, 'html', 'utf-8'))

            # 发送邮件
            server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            server.login(self.sender_email, self.sender_password)
            server.send_message(msg)
            server.quit()

            return True

        except Exception as e:
            print(f"邮件发送失败: {e}")
            return False

    def verify_code(self, email: str, code: str) -> bool:
        """
        验证邮箱验证码
        :param email: 邮箱
        :param code: 用户输入的验证码
        :return: 是否验证成功
        """
        if email not in st.session_state.verification_codes:
            return False

        data = st.session_state.verification_codes[email]

        # 检查是否过期
        if time.time() > data['expires_at']:
            # 删除过期验证码
            del st.session_state.verification_codes[email]
            return False

        # 验证码是否正确
        if data['code'] == code:
            # 验证成功后删除，防止重复使用
            del st.session_state.verification_codes[email]
            return True

        return False