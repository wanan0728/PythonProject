"""
智能客服主应用
添加了用户注册登录功能 + 管理员独立界面 + 弹窗提示
"""
import sys
import os
# 获取项目根目录的绝对路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import time
import json
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
if 'show_success_popup' not in st.session_state:
    st.session_state.show_success_popup = False
if 'show_error_popup' not in st.session_state:
    st.session_state.show_error_popup = False
if 'popup_message' not in st.session_state:
    st.session_state.popup_message = ""
if 'popup_username' not in st.session_state:
    st.session_state.popup_username = ""
if 'selected_tab' not in st.session_state:
    st.session_state.selected_tab = "登录"  # 默认显示登录页

# ========== 管理员账户配置 ==========
ADMIN_USERS = ["admin", "wanan"]

# ========== 自定义CSS弹窗样式 ==========
st.markdown("""
<style>
.custom-popup {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 400px;
    background: white;
    border-radius: 20px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    z-index: 999999;
    animation: slideIn 0.3s ease;
    padding: 30px;
    text-align: center;
    border: 1px solid #e0e0e0;
}

.popup-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.5);
    z-index: 999998;
    animation: fadeIn 0.3s ease;
}

@keyframes slideIn {
    from {
        opacity: 0;
        transform: translate(-50%, -60%);
    }
    to {
        opacity: 1;
        transform: translate(-50%, -50%);
    }
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

.popup-success {
    border-top: 5px solid #28a745;
}

.popup-error {
    border-top: 5px solid #dc3545;
}

.popup-icon {
    font-size: 60px;
    margin-bottom: 15px;
}

.popup-title {
    font-size: 24px;
    font-weight: bold;
    margin-bottom: 10px;
}

.popup-message {
    font-size: 16px;
    color: #666;
    margin-bottom: 20px;
}

.popup-timer {
    font-size: 14px;
    color: #999;
    margin-top: 15px;
}

.countdown-circle {
    width: 50px;
    height: 50px;
    border-radius: 50%;
    background: #f0f0f0;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto;
    font-weight: bold;
    color: #333;
    animation: pulse 1s infinite;
}

@keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.1); }
    100% { transform: scale(1); }
}
</style>
""", unsafe_allow_html=True)

# ========== 显示成功弹窗 ==========
def show_success_popup(username):
    placeholder = st.empty()
    for i in range(3, 0, -1):
        with placeholder.container():
            st.markdown(f"""
            <div class="popup-overlay"></div>
            <div class="custom-popup popup-success">
                <div class="popup-icon">✅</div>
                <div class="popup-title">注册成功！</div>
                <div class="popup-message">
                    欢迎 <strong>{username}</strong> 加入智能客服<br>
                    您的账号已创建成功
                </div>
                <div style="margin: 20px 0;">
                    <div class="countdown-circle">{i}</div>
                </div>
                <div class="popup-timer">{i}秒后自动跳转到登录页...</div>
            </div>
            """, unsafe_allow_html=True)
        time.sleep(1)
    placeholder.empty()

    # 关键修复：强制切换到登录模式
    st.session_state.selected_tab = "登录"  # 切换到登录标签
    st.session_state.register_mode = False  # 关闭注册模式

# ========== 显示失败弹窗 ==========
def show_error_popup(error_msg):
    placeholder = st.empty()
    for i in range(3, 0, -1):
        with placeholder.container():
            st.markdown(f"""
            <div class="popup-overlay"></div>
            <div class="custom-popup popup-error">
                <div class="popup-icon">❌</div>
                <div class="popup-title">注册失败</div>
                <div class="popup-message">
                    {error_msg}<br>
                    请检查后重新尝试
                </div>
                <div style="margin: 20px 0;">
                    <div class="countdown-circle">{i}</div>
                </div>
                <div class="popup-timer">{i}秒后自动关闭...</div>
            </div>
            """, unsafe_allow_html=True)
        time.sleep(1)
    placeholder.empty()

# ========== 如果未登录，显示登录/注册界面 ==========
if not st.session_state.logged_in:

    # 显示成功弹窗
    if st.session_state.show_success_popup:
        show_success_popup(st.session_state.popup_username)
        st.session_state.show_success_popup = False
        st.session_state.popup_username = ""
        st.rerun()

    # 显示失败弹窗
    if st.session_state.show_error_popup:
        show_error_popup(st.session_state.popup_message)
        st.session_state.show_error_popup = False
        st.session_state.popup_message = ""
        st.rerun()

    st.title("🤖 智能客服系统")
    st.markdown("---")

    # 创建三列布局
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        # 切换登录/注册模式 - 使用session_state保持状态
        mode = st.radio(
            "选择操作",
            ["登录", "注册"],
            horizontal=True,
            key="selected_tab"  # 绑定到session_state
        )

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
                        success, message, user_data = auth_manager.login(username, password)
                        if success:
                            is_admin = username in ADMIN_USERS

                            if admin_login and not is_admin:
                                st.error("该用户不是管理员，无法以管理员身份登录")
                            else:
                                st.session_state.logged_in = True
                                st.session_state.username = username
                                st.session_state.email = user_data['email']
                                st.session_state.session_id = user_data['session_id']
                                st.session_state.is_admin = is_admin

                                if admin_login and is_admin:
                                    st.session_state.admin_mode = True
                                    st.success(f"👑 管理员 {username} 登录成功！")
                                else:
                                    st.session_state.admin_mode = False
                                    st.success("登录成功！")
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
                                st.success("验证码已发送，请查收邮件")
                            else:
                                st.error("验证码发送失败，请检查邮箱地址")
                        else:
                            st.warning("请先输入邮箱")

                st.markdown("---")
                submit = st.form_submit_button("注册", use_container_width=True)

                if submit:
                    if not all([email, username, password, confirm_password, verification_code]):
                        st.warning("请填写所有字段")
                    elif password != confirm_password:
                        st.warning("两次输入的密码不一致")
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
                            st.session_state.show_success_popup = True
                            st.session_state.popup_username = username
                            st.rerun()
                        else:
                            st.session_state.show_error_popup = True
                            st.session_state.popup_message = message
                            st.rerun()

    st.stop()

# ========== 已登录，根据角色显示不同界面 ==========

# 管理员界面
if st.session_state.get('admin_mode', False):
    st.title("👑 管理员控制台")
    st.markdown(f"欢迎管理员：**{st.session_state.username}**")
    st.divider()

    tab1, tab2, tab3 = st.tabs(["📋 用户管理", "📊 数据统计", "⚙️ 系统设置"])

    with tab1:
        st.subheader("用户列表")
        users_file = os.path.join(project_root, "auth", "users.json")

        if os.path.exists(users_file):
            with open(users_file, 'r', encoding='utf-8') as f:
                users_data = json.load(f)

            st.write(f"当前总用户数：{len(users_data)}")

            # 搜索框
            search_term = st.text_input("🔍 搜索用户", placeholder="输入用户名或邮箱...")

            # 过滤用户
            filtered_users = {}
            for username, user_info in users_data.items():
                if search_term:
                    if (search_term.lower() in username.lower() or
                        search_term.lower() in user_info.get('email', '').lower()):
                        filtered_users[username] = user_info
                else:
                    filtered_users = users_data

            for username, user_info in filtered_users.items():
                with st.expander(f"👤 用户：{username}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**📧 邮箱**")
                        st.code(user_info.get('email', '无'))
                        st.markdown("**🔑 密码**")
                        st.code(user_info.get('password', '无'))
                    with col2:
                        st.markdown("**📅 注册时间**")
                        st.code(user_info.get('created_at', '无'))
                        st.markdown("**🆔 会话ID**")
                        st.code(user_info.get('session_id', '无'))
        else:
            st.error("用户文件不存在")

    with tab2:
        st.subheader("数据统计")
        if os.path.exists(users_file):
            with open(users_file, 'r', encoding='utf-8') as f:
                users_data = json.load(f)

            # 基础统计
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                st.metric("总用户数", len(users_data))
            with col_s2:
                # 今日注册数
                today_count = sum(1 for u in users_data.values()
                                if u.get('created_at', '').startswith(datetime.now().strftime("%Y-%m-%d")))
                st.metric("今日注册", today_count)
            with col_s3:
                st.metric("文件大小", f"{os.path.getsize(users_file)} bytes")

            # 邮箱域名统计
            domains = {}
            for user_info in users_data.values():
                email = user_info.get('email', '')
                if '@' in email:
                    domain = email.split('@')[1]
                    domains[domain] = domains.get(domain, 0) + 1

            if domains:
                st.subheader("📧 邮箱域名分布")
                for domain, count in domains.items():
                    st.progress(count / len(users_data),
                              text=f"{domain}: {count}人 ({count/len(users_data)*100:.1f}%)")

    with tab3:
        st.subheader("系统设置")
        st.info("管理员设置功能开发中...")

    with st.sidebar:
        st.markdown(f"### 👑 管理员：**{st.session_state.username}**")
        st.markdown(f"📧 {st.session_state.email}")
        st.markdown("---")

        # 退出管理员模式
        if st.button("🔙 退出管理员模式", use_container_width=True):
            st.session_state.admin_mode = False
            st.rerun()

        # 退出登录
        if st.button("🚪 退出登录", use_container_width=True):
            auth_manager.logout()
            st.rerun()

# 普通用户界面
else:
    with st.sidebar:
        # 如果是管理员但没用管理员模式，提示可以切换
        if st.session_state.get('username') and st.session_state.username in ADMIN_USERS:
            st.info("👑 您是管理员，可以切换到管理员模式")
            if st.button("🔐 进入管理员模式", use_container_width=True):
                st.session_state.admin_mode = True
                st.rerun()
            st.markdown("---")

        st.markdown(f"### 👋 欢迎，**{st.session_state.username}**")
        st.markdown(f"📧 {st.session_state.email}")
        st.markdown("---")

        # 退出登录按钮
        if st.button("🚪 退出登录", use_container_width=True):
            auth_manager.logout()
            st.rerun()

        st.markdown("---")
        st.markdown("### 📊 使用说明")
        st.markdown("""
        1. 输入问题，AI会基于知识库回答
        2. 支持多轮对话
        3. 历史记录自动保存
        """)

    # 标题
    st.title("🤖 智能客服")
    st.divider()

    # 初始化消息历史
    if "message" not in st.session_state:
        st.session_state["message"] = [{"role": "assistant", "content": "你好，有什么可以帮助你？"}]

    # 初始化RAG服务
    if "rag" not in st.session_state:
        with st.spinner("初始化服务..."):
            st.session_state["rag"] = RagService()

    # 显示历史消息
    for message in st.session_state["message"]:
        st.chat_message(message["role"]).write(message["content"])

    # 聊天输入
    prompt = st.chat_input("请输入您的问题...")

    if prompt:
        # 显示用户消息
        st.chat_message("user").write(prompt)
        st.session_state["message"].append({"role": "user", "content": prompt})

        # 调用RAG服务
        ai_res_list = []
        with st.spinner("AI思考中..."):
            try:
                # 使用用户特定的session_id
                user_session_config = {
                    "configurable": {
                        "session_id": st.session_state.session_id
                    }
                }

                res_stream = st.session_state["rag"].chain.stream(
                    {"input": prompt},
                    user_session_config
                )

                def capture(generator, cache_list):
                    for chunk in generator:
                        cache_list.append(chunk)
                        yield chunk

                # 流式显示回答
                response = st.chat_message("assistant").write_stream(capture(res_stream, ai_res_list))

                # 保存到历史
                full_response = "".join(ai_res_list)
                st.session_state["message"].append({"role": "assistant", "content": full_response})

            except Exception as e:
                st.error(f"出错了: {e}")