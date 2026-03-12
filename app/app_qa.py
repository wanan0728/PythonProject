"""
智能客服主应用
添加了用户注册登录功能
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

# ========== 如果未登录，显示登录/注册界面 ==========
if not st.session_state.logged_in:
    st.title("🤖 智能客服系统")
    st.markdown("---")

    # 创建两列布局
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        # 切换登录/注册模式
        mode = st.radio("选择操作", ["登录", "注册"], horizontal=True)

        if mode == "登录":
            st.subheader("🔐 用户登录")

            with st.form("login_form"):
                username = st.text_input("用户名", placeholder="请输入用户名")
                password = st.text_input("密码", type="password", placeholder="请输入密码")

                submit = st.form_submit_button("登录", use_container_width=True)

                if submit:
                    if not username or not password:
                        st.warning("请输入用户名和密码")
                    else:
                        success, message, user_data = auth_manager.login(username, password)
                        if success:
                            st.session_state.logged_in = True
                            st.session_state.username = username
                            st.session_state.email = user_data['email']
                            st.session_state.session_id = user_data['session_id']
                            st.success("登录成功！")
                            st.rerun()
                        else:
                            st.error(message)

        else:  # 注册模式
            st.subheader("📝 用户注册")

            # 注册表单
            with st.form("register_form"):
                email = st.text_input("邮箱", placeholder="请输入您的邮箱")
                username = st.text_input("用户名", placeholder="请输入用户名（登录用）")
                password = st.text_input("密码", type="password", placeholder="请输入密码")
                confirm_password = st.text_input("确认密码", type="password", placeholder="请再次输入密码")

                # 验证码区域
                st.markdown("---")
                col_code1, col_code2 = st.columns([3, 1])

                with col_code1:
                    verification_code = st.text_input("验证码", placeholder="请输入6位数字验证码")

                with col_code2:
                    # 获取验证码按钮
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
                    # 表单验证
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
                            st.success("注册成功！请登录")

                            # ========== 添加数据验证 ==========
                            with st.expander("📊 数据验证（查看注册结果）"):
                                users_file = os.path.join(project_root, "auth", "users.json")
                                st.write(f"用户文件路径: {users_file}")
                                st.write(f"文件是否存在: {os.path.exists(users_file)}")

                                if os.path.exists(users_file):
                                    try:
                                        with open(users_file, 'r', encoding='utf-8') as f:
                                            current_users = json.load(f)
                                        st.write(f"当前用户总数: {len(current_users)}")

                                        # 显示所有用户
                                        st.subheader("已注册用户列表")
                                        for uname, uinfo in current_users.items():
                                            with st.container():
                                                col_u1, col_u2 = st.columns(2)
                                                with col_u1:
                                                    st.write(f"**用户名:** {uname}")
                                                    st.write(f"**邮箱:** {uinfo.get('email', '无')}")
                                                with col_u2:
                                                    st.write(f"**会话ID:** {uinfo.get('session_id', '无')}")
                                                    st.write(f"**注册时间:** {uinfo.get('created_at', '无')}")
                                                st.divider()

                                        # 检查刚注册的用户
                                        if username in current_users:
                                            st.success(f"✅ 用户 '{username}' 成功写入文件！")
                                        else:
                                            st.error(f"❌ 用户 '{username}' 未在文件中找到！")

                                    except Exception as e:
                                        st.error(f"读取文件失败: {e}")
                                else:
                                    st.error("users.json 文件不存在，请检查 auth 文件夹")

                            time.sleep(3)
                            st.rerun()
                        else:
                            st.error(message)

    # 未登录状态不显示主内容
    st.stop()

# ========== 已登录，显示主应用内容 ==========

# 侧边栏显示用户信息
with st.sidebar:
    st.markdown(f"### 👋 欢迎，**{st.session_state.username}**")
    st.markdown(f"📧 {st.session_state.email}")
    st.markdown("---")

    # 添加数据查看功能（仅管理员）
    if st.session_state.username == "wanan" or st.session_state.username == "admin":  # 改成你的管理员用户名
        with st.expander("🔐 管理员功能"):
            if st.button("📊 查看所有用户"):
                users_file = os.path.join(project_root, "auth", "users.json")
                if os.path.exists(users_file):
                    with open(users_file, 'r', encoding='utf-8') as f:
                        users_data = json.load(f)
                    st.write(f"当前用户数: {len(users_data)}")
                    st.json(users_data)
                else:
                    st.error("用户文件不存在")

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