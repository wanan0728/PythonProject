"""
用户认证模块
功能：处理用户注册、登录、会话管理
"""
import json
import os
import hashlib
import streamlit as st
from email_utils import EmailVerification
import config_data as config

# 用户数据文件路径
USERS_FILE = "users.json"


class AuthManager:
    def __init__(self):
        """初始化认证管理器"""
        self.email_verification = EmailVerification(
            sender_email=config.SENDER_EMAIL,
            sender_password=config.SENDER_PASSWORD,
            smtp_server=config.SMTP_SERVER,
            smtp_port=config.SMTP_PORT
        )
        self._init_users_file()

    def _init_users_file(self):
        """初始化用户文件"""
        if not os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f)

    def _hash_password(self, password: str) -> str:
        """密码加密"""
        return hashlib.sha256(password.encode()).hexdigest()

    def _load_users(self) -> dict:
        """加载所有用户"""
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    def _save_users(self, users: dict):
        """保存用户数据"""
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)

    def register(self, email: str, username: str, password: str, verification_code: str) -> tuple:
        """
        用户注册
        :return: (成功与否, 消息)
        """
        # 1. 验证邮箱验证码
        if not self.email_verification.verify_code(email, verification_code):
            return False, "验证码错误或已过期"

        # 2. 加载现有用户
        users = self._load_users()

        # 3. 检查邮箱是否已存在
        for uid, user_data in users.items():
            if user_data.get('email') == email:
                return False, "该邮箱已被注册"

        # 4. 检查用户名是否已存在
        if username in users:
            return False, "用户名已存在"

        # 5. 创建新用户
        users[username] = {
            'email': email,
            'password': self._hash_password(password),
            'created_at': str(st.session_state.get('current_time', '')),
            'session_id': f"{username}_{hash(username)}"
        }

        # 6. 保存用户数据
        self._save_users(users)

        return True, "注册成功"

    def login(self, username: str, password: str) -> tuple:
        """
        用户登录
        :return: (成功与否, 消息, 用户数据)
        """
        users = self._load_users()

        if username not in users:
            return False, "用户名不存在", None

        user_data = users[username]
        hashed_password = self._hash_password(password)

        if user_data['password'] != hashed_password:
            return False, "密码错误", None

        return True, "登录成功", user_data

    def send_verification_code(self, email: str) -> bool:
        """发送验证码"""
        return self.email_verification.send_verification_email(email)

    def check_login(self):
        """检查是否已登录"""
        return st.session_state.get('logged_in', False)

    def get_current_user(self):
        """获取当前登录用户"""
        if self.check_login():
            return {
                'username': st.session_state.get('username'),
                'email': st.session_state.get('email'),
                'session_id': st.session_state.get('session_id')
            }
        return None

    def logout(self):
        """退出登录"""
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.email = None
        st.session_state.session_id = None


# 创建全局认证管理器实例
auth_manager = AuthManager()