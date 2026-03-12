"""
邮箱验证码工具
功能：生成6位数字验证码，发送到用户邮箱
"""
import sys
import os
# 获取项目根目录的绝对路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import smtplib
import random
import string
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict
import streamlit as st
import socket


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

        # 调试信息
        print(f"📧 EmailVerification初始化:")
        print(f"   - 发件人: {sender_email}")
        print(f"   - 服务器: {smtp_server}")
        print(f"   - 端口: {smtp_port}")
        print(f"   - 密码已设置: {'是' if sender_password else '否'}")

    def _init_verification_codes(self):
        """初始化验证码存储（确保session_state中有verification_codes）"""
        if 'verification_codes' not in st.session_state:
            st.session_state.verification_codes = {}
            print("📧 初始化验证码存储")

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
            print(f"📧 开始发送验证码到: {to_email}")

            # 确保verification_codes已初始化
            self._init_verification_codes()

            # 生成6位数字验证码
            code = self.generate_code()
            print(f"📧 生成验证码: {code}")

            # 存储验证码，5分钟过期
            st.session_state.verification_codes[to_email] = {
                'code': code,
                'expires_at': time.time() + 300  # 300秒 = 5分钟
            }
            print(f"📧 验证码已存储，当前存储数量: {len(st.session_state.verification_codes)}")

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

            print(f"📧 正在连接SMTP服务器 {self.smtp_server}:{self.smtp_port}...")

            # 发送邮件
            server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=30)
            print(f"📧 SMTP连接成功")

            print(f"📧 正在登录...")
            server.login(self.sender_email, self.sender_password)
            print(f"📧 登录成功")

            print(f"📧 正在发送邮件...")
            server.send_message(msg)
            print(f"📧 邮件发送成功")

            server.quit()
            print(f"📧 SMTP连接已关闭")

            return True

        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ SMTP认证失败: {e}")
            print(f"   - 请检查邮箱授权码是否正确")
            return False
        except smtplib.SMTPConnectError as e:
            print(f"❌ SMTP连接失败: {e}")
            print(f"   - 请检查网络连接和防火墙设置")
            return False
        except socket.gaierror as e:
            print(f"❌ 无法解析服务器地址: {e}")
            print(f"   - 请检查SMTP服务器地址是否正确")
            return False
        except Exception as e:
            print(f"❌ 邮件发送失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def verify_code(self, email: str, code: str) -> bool:
        """
        验证邮箱验证码
        :param email: 邮箱
        :param code: 用户输入的验证码
        :return: 是否验证成功
        """
        # 确保verification_codes已初始化
        self._init_verification_codes()

        if email not in st.session_state.verification_codes:
            print(f"验证码验证失败: 邮箱 {email} 没有找到验证码记录")
            return False

        data = st.session_state.verification_codes[email]

        # 检查是否过期
        if time.time() > data['expires_at']:
            print(f"验证码验证失败: 验证码已过期")
            # 删除过期验证码
            del st.session_state.verification_codes[email]
            return False

        # 验证码是否正确
        if data['code'] == code:
            print(f"验证码验证成功")
            # 验证成功后删除，防止重复使用
            del st.session_state.verification_codes[email]
            return True

        print(f"验证码验证失败: 验证码不匹配")
        return False