"""
用户认证模块
功能：处理用户注册、登录、会话管理
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import json
import streamlit as st
from datetime import datetime
from utils.logger import logger, log_user_action
from utils.ratelimit import rate_limit_manager, get_client_ip

# 用户数据文件路径
USERS_FILE = os.path.join(os.path.dirname(__file__), "users.json")


class AuthManager:
    def __init__(self):
        """初始化认证管理器"""
        # 在 __init__ 方法内部导入，避免循环导入
        from auth.email_utils import EmailVerification
        from config.config_data import SENDER_EMAIL, SENDER_PASSWORD, SMTP_SERVER, SMTP_PORT

        logger.info("初始化认证管理器")
        self.email_verification = EmailVerification(
            sender_email=SENDER_EMAIL,
            sender_password=SENDER_PASSWORD,
            smtp_server=SMTP_SERVER,
            smtp_port=SMTP_PORT
        )
        self._init_users_file()

    def _init_users_file(self):
        """初始化用户文件"""
        if not os.path.exists(USERS_FILE):
            os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            logger.info(f"创建 users.json 文件: {USERS_FILE}")

    def _load_users(self) -> dict:
        """加载所有用户"""
        try:
            if not os.path.exists(USERS_FILE):
                return {}

            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    return {}
                return json.loads(content)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"users.json 文件损坏: {e}")
            return {}

    def _save_users(self, users: dict):
        """保存用户数据"""
        try:
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存用户数据失败: {e}")
            raise

    def register(self, email: str, username: str, password: str, verification_code: str) -> tuple:
        """
        用户注册
        :return: (成功与否, 消息)
        """
        logger.info(f"用户注册尝试: {username}, {email}")

        # 1. 验证邮箱验证码
        if not self.email_verification.verify_code(email, verification_code):
            logger.warning(f"注册失败 - 验证码错误: {username}, {email}")
            return False, "验证码错误或已过期"

        # 2. 加载现有用户
        users = self._load_users()

        # 3. 检查邮箱是否已被注册
        for existing_username, user_data in users.items():
            if user_data.get('email') == email:
                logger.warning(f"注册失败 - 邮箱已存在: {email} (用户: {existing_username})")
                return False, "该邮箱已被注册"

        # 4. 检查用户名是否已存在
        if username in users:
            logger.warning(f"注册失败 - 用户名已存在: {username}")
            return False, "用户名已存在"

        # 5. 创建新用户
        users[username] = {
            'email': email,
            'password': password,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'session_id': f"{username}_{hash(username)}"
        }

        # 6. 保存用户数据
        self._save_users(users)
        logger.info(f"用户注册成功: {username}, {email}")
        log_user_action(username, "register", {"email": email})

        return True, "注册成功"

    def login(self, username: str, password: str) -> tuple:
        """
        用户登录（带限流，5分钟限制）
        :return: (成功与否, 消息, 用户数据)
        """
        ip = get_client_ip()
        logger.info(f"🔐 用户登录尝试: {username}，IP: {ip}")

        # 限流检查（5分钟 = 300秒）
        allowed, remaining, reset_time = rate_limit_manager.check_rate_limit(
            username, "login", ip
        )

        if not allowed:
            wait_minutes = 5
            logger.warning(f"⛔ 登录限流: {username}，IP: {ip}")
            return False, f"❌ 尝试次数过多，请{wait_minutes}分钟后再试", None

        users = self._load_users()

        if username not in users:
            # 记录失败尝试
            rate_limit_manager.add_attempt(username, "login", ip)
            # 获取更新后的剩余次数
            remaining = rate_limit_manager.get_remaining(username, "login", ip)
            logger.warning(f"登录失败 - 用户名不存在: {username}")

            if remaining > 0:
                return False, f"❌ 用户名不存在 (剩余{remaining}次尝试)", None
            else:
                return False, "❌ 用户名不存在", None

        user_data = users[username]

        if user_data['password'] != password:
            # 记录失败尝试
            rate_limit_manager.add_attempt(username, "login", ip)
            # 获取更新后的剩余次数
            remaining = rate_limit_manager.get_remaining(username, "login", ip)
            logger.warning(f"登录失败 - 密码错误: {username}")

            if remaining > 0:
                return False, f"❌ 密码错误 (剩余{remaining}次尝试)", None
            else:
                return False, "❌ 密码错误", None

        # 登录成功
        logger.info(f"✅ 用户登录成功: {username}")
        log_user_action(username, "login")
        return True, "登录成功", user_data

    def send_verification_code(self, email: str) -> bool:
        """发送验证码"""
        logger.info(f"发送验证码到: {email}")
        result = self.email_verification.send_verification_email(email)
        if result:
            logger.info(f"验证码发送成功: {email}")
        else:
            logger.error(f"验证码发送失败: {email}")
        return result

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
        username = st.session_state.get('username', 'unknown')
        logger.info(f"用户退出登录: {username}")

        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.email = None
        st.session_state.session_id = None
        st.session_state.admin_mode = False


# 创建全局认证管理器实例
auth_manager = AuthManager()

# ========== 测试代码（直接运行此文件时执行）==========
if __name__ == '__main__':
    print("="*50)
    print("🧪 测试 AuthManager")
    print("="*50)

    test_users = auth_manager._load_users()
    print(f"📊 当前用户数: {len(test_users)}")
    print(f"👥 用户列表: {list(test_users.keys())}")

    print("\n✅ 测试完成")