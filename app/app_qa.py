"""
智能客服主应用
添加了用户注册登录功能 + 管理员独立界面 + 弹窗拼图验证
"""
import sys
import os
# 获取项目根目录的绝对路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import time
import json
import random
import base64
import streamlit as st
from core.rag import RagService
from auth.auth import auth_manager
from datetime import datetime

# 页面配置
st.set_page_config(
    page_title="智能客服",
    page_icon="🤖",
    layout="wide"
)

# ========== 初始化会话状态 ==========
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'register_mode' not in st.session_state:
    st.session_state.register_mode = False
if 'admin_mode' not in st.session_state:
    st.session_state.admin_mode = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'show_captcha' not in st.session_state:
    st.session_state.show_captcha = False  # 是否显示验证弹窗
if 'captcha_passed' not in st.session_state:
    st.session_state.captcha_passed = False
if 'captcha_target' not in st.session_state:
    st.session_state.captcha_target = random.randint(30, 70)  # 缺口目标位置
if 'pending_login' not in st.session_state:
    st.session_state.pending_login = None  # 暂存的登录信息

# ========== 管理员账户配置 ==========
ADMIN_USERS = ["admin", "wanan"]

# ========== 生成拼图背景（纯CSS模拟）==========
def generate_captcha_html(target_position):
    """生成拼图验证的HTML代码"""

    # 随机选择背景颜色
    colors = ["#667eea", "#764ba2", "#f093fb", "#f5576c"]
    bg_color = random.choice(colors)

    # 随机选择缺口位置（在target附近）
    gap_start = target_position - 5
    gap_end = target_position + 5

    html_code = f"""
    <div style="
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.5);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 9999;
    ">
        <div style="
            background: white;
            padding: 30px;
            border-radius: 15px;
            width: 400px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        ">
            <h3 style="text-align: center; margin-bottom: 20px;">🔐 安全验证</h3>
            
            <!-- 拼图区域 -->
            <div style="
                background: {bg_color};
                height: 200px;
                border-radius: 10px;
                position: relative;
                overflow: hidden;
                margin-bottom: 20px;
            ">
                <!-- 拼图背景条纹 -->
                <div style="
                    background: repeating-linear-gradient(
                        45deg,
                        rgba(255,255,255,0.2) 0px,
                        rgba(255,255,255,0.2) 10px,
                        rgba(255,255,255,0.4) 10px,
                        rgba(255,255,255,0.4) 20px
                    );
                    width: 100%;
                    height: 100%;
                "></div>
                
                <!-- 缺口区域（黑色阴影） -->
                <div style="
                    position: absolute;
                    top: 50px;
                    left: {gap_start}%;
                    width: 10%;
                    height: 100px;
                    background: rgba(0,0,0,0.6);
                    border-radius: 5px;
                    box-shadow: 0 0 20px rgba(0,0,0,0.5);
                    transform: translateY(-50%);
                "></div>
                
                <!-- 拼图滑块（可移动部分） -->
                <div id="moving-block" style="
                    position: absolute;
                    top: 50px;
                    left: 0%;
                    width: 10%;
                    height: 100px;
                    background: rgba(255,255,255,0.3);
                    border: 3px solid white;
                    border-radius: 5px;
                    cursor: grab;
                    transition: left 0.1s;
                    box-shadow: 0 0 20px rgba(255,255,255,0.5);
                "></div>
            </div>
            
            <!-- 滑块轨道 -->
            <div style="
                background: #f0f0f0;
                height: 40px;
                border-radius: 20px;
                position: relative;
                margin: 20px 0;
            ">
                <div style="
                    position: absolute;
                    left: 0;
                    top: 0;
                    height: 40px;
                    width: 40px;
                    background: {bg_color};
                    border-radius: 20px;
                    cursor: pointer;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                "></div>
                <p style="
                    text-align: center;
                    line-height: 40px;
                    color: #999;
                ">按住滑块拖动完成拼图</p>
            </div>
            
            <!-- 提示文字 -->
            <p style="
                text-align: center;
                color: #666;
                font-size: 14px;
            ">请将拼图滑块拖动到缺口位置</p>
        </div>
    </div>
    """
    return html_code

# ========== 渲染验证弹窗 ==========
def render_captcha_modal():
    """渲染验证弹窗"""

    # 使用 st.markdown 插入 HTML
    st.markdown(
        generate_captcha_html(st.session_state.captcha_target),
        unsafe_allow_html=True
    )

    # 创建滑块（实际交互）
    st.markdown("---")
    st.markdown("### 拖动滑块完成验证")

    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        # 滑块输入
        slider_value = st.slider(
            "验证滑块",
            min_value=0,
            max_value=100,
            value=0,
            key="captcha_slider",
            label_visibility="collapsed"
        )

        # 显示目标位置提示（调试用，正式可隐藏）
        target = st.session_state.captcha_target
        st.caption(f"目标位置: {target}% (误差±5%)")

        # 验证按钮
        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b2:
            if st.button("确认验证", use_container_width=True):
                # 允许5%误差
                if abs(slider_value - target) <= 5:
                    st.session_state.captcha_passed = True
                    st.session_state.show_captcha = False

                    # 执行暂存的登录
                    if st.session_state.pending_login:
                        username, password, admin_login = st.session_state.pending_login
                        success, message, user_data = auth_manager.login(username, password)
                        if success:
                            is_admin = username in ADMIN_USERS
                            if admin_login and not is_admin:
                                st.error("该用户不是管理员")
                            else:
                                st.session_state.logged_in = True
                                st.session_state.username = username
                                st.session_state.email = user_data['email']
                                st.session_state.session_id = user_data['session_id']
                                st.session_state.is_admin = is_admin
                                if admin_login and is_admin:
                                    st.session_state.admin_mode = True
                                st.success("登录成功！")
                                st.rerun()
                        else:
                            st.error(message)
                    st.rerun()
                else:
                    st.error("验证失败，请重试")
                    # 重置目标位置
                    st.session_state.captcha_target = random.randint(30, 70)
                    st.rerun()

# ========== 如果未登录，显示登录/注册界面 ==========
if not st.session_state.logged_in:

    # 如果显示验证弹窗
    if st.session_state.show_captcha:
        render_captcha_modal()
        st.stop()

    st.title("🤖 智能客服系统")
    st.markdown("---")

    # 创建三列布局
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        # 切换登录/注册模式
        mode = st.radio("选择操作", ["登录", "注册"], horizontal=True)

        if mode == "登录":
            st.caption("👑 管理员请使用管理员账户登录")

            st.subheader("🔐 用户登录")

            with st.form("login_form"):
                username = st.text_input("用户名", placeholder="请输入用户名")
                password = st.text_input("密码", type="password", placeholder="请输入密码")

                with st.expander("🔧 高级选项"):
                    admin_login = st.checkbox("以管理员身份登录")

                submit = st.form_submit_button("登录", use_container_width=True)

                if submit:
                    if not username or not password:
                        st.warning("请输入用户名和密码")
                    else:
                        # 先验证用户名密码是否正确
                        success, message, user_data = auth_manager.login(username, password)
                        if success:
                            # 暂存登录信息，显示验证弹窗
                            st.session_state.pending_login = (username, password, admin_login)
                            st.session_state.show_captcha = True
                            st.session_state.captcha_target = random.randint(30, 70)
                            st.rerun()
                        else:
                            st.error(message)

        else:  # 注册模式
            st.subheader("📝 用户注册")

            with st.form("register_form"):
                email = st.text_input("邮箱", placeholder="请输入您的邮箱")
                username = st.text_input("用户名", placeholder="请输入用户名（登录用）")
                password = st.text_input("密码", type="password", placeholder="请输入密码")
                confirm_password = st.text_input("确认密码", type="password", placeholder="请再次输入密码")

                st.markdown("---")
                col_code1, col_code2 = st.columns([3, 1])

                with col_code1:
                    verification_code = st.text_input("验证码", placeholder="请输入6位数字验证码")

                with col_code2:
                    get_code = st.form_submit_button("获取验证码")
                    if get_code:
                        if email:
                            if auth_manager.send_verification_code(email):
                                st.success("验证码已发送")
                            else:
                                st.error("发送失败")
                        else:
                            st.warning("请先输入邮箱")

                st.markdown("---")
                submit = st.form_submit_button("注册", use_container_width=True)

                if submit:
                    # 注册验证逻辑...
                    if not all([email, username, password, confirm_password, verification_code]):
                        st.warning("请填写所有字段")
                    elif password != confirm_password:
                        st.warning("密码不一致")
                    elif len(verification_code) != 6 or not verification_code.isdigit():
                        st.warning("验证码必须是6位数字")
                    else:
                        success, message = auth_manager.register(
                            email=email,
                            username=username,
                            password=password,
                            verification_code=verification_code
                        )
                        if success:
                            st.success("注册成功！请登录")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(message)

    st.stop()

# ========== 重置验证码状态 ==========
def reset_captcha():
    st.session_state.captcha_passed = False
    st.session_state.show_captcha = False
    st.session_state.captcha_target = random.randint(30, 70)
    st.session_state.pending_login = None

# ========== 已登录，根据角色显示不同界面 ==========

# 如果是管理员模式，显示管理员界面
if st.session_state.get('admin_mode', False):
    # ... 管理员界面代码保持不变 ...
    st.title("👑 管理员控制台")
    # ... 其余管理员代码 ...

# ========== 普通用户界面 ==========
else:
    with st.sidebar:
        if st.session_state.username in ADMIN_USERS:
            st.info("👑 您是管理员")
            if st.button("🔐 进入管理员模式"):
                st.session_state.admin_mode = True
                st.rerun()
            st.markdown("---")

        st.markdown(f"### 👋 欢迎，**{st.session_state.username}**")
        st.markdown(f"📧 {st.session_state.email}")
        st.markdown("---")

        if st.button("🚪 退出登录", use_container_width=True):
            auth_manager.logout()
            reset_captcha()
            st.rerun()

    # 聊天界面
    st.title("🤖 智能客服")
    st.divider()

    if "message" not in st.session_state:
        st.session_state["message"] = [{"role": "assistant", "content": "你好，有什么可以帮助你？"}]

    if "rag" not in st.session_state:
        with st.spinner("初始化服务..."):
            st.session_state["rag"] = RagService()

    for message in st.session_state["message"]:
        st.chat_message(message["role"]).write(message["content"])

    prompt = st.chat_input("请输入您的问题...")
    if prompt:
        # ... 聊天逻辑 ...
        pass