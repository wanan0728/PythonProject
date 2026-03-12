"""
智能客服主应用
添加了用户注册登录功能 + 管理员独立界面
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
    st.session_state.admin_mode = False  # 管理员模式标识
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

# ========== 管理员账户配置（可以修改成你自己的）==========
ADMIN_USERS = ["admin", "wanan"]  # 这里设置哪些用户名是管理员
ADMIN_PASSWORD = "admin123"  # 管理员专用密码（可选，如果不设置则用普通用户密码）

# ========== 如果未登录，显示登录/注册界面 ==========
if not st.session_state.logged_in:
    st.title("🤖 智能客服系统")
    st.markdown("---")

    # 创建三列布局（增加一列用于管理员登录提示）
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        # 切换登录/注册模式
        mode = st.radio("选择操作", ["登录", "注册"], horizontal=True)

        if mode == "登录":
            # 添加管理员登录提示（小字）
            st.caption("👑 管理员请使用管理员账户登录")

            st.subheader("🔐 用户登录")

            with st.form("login_form"):
                username = st.text_input("用户名", placeholder="请输入用户名")
                password = st.text_input("密码", type="password", placeholder="请输入密码")

                # 高级选项（可以展开）
                with st.expander("🔧 高级选项"):
                    admin_login = st.checkbox("以管理员身份登录")

                submit = st.form_submit_button("登录", use_container_width=True)

                if submit:
                    if not username or not password:
                        st.warning("请输入用户名和密码")
                    else:
                        success, message, user_data = auth_manager.login(username, password)
                        if success:
                            # 检查是否是管理员
                            is_admin = username in ADMIN_USERS

                            # 如果勾选了管理员登录但不是管理员
                            if admin_login and not is_admin:
                                st.error("该用户不是管理员，无法以管理员身份登录")
                            else:
                                st.session_state.logged_in = True
                                st.session_state.username = username
                                st.session_state.email = user_data['email']
                                st.session_state.session_id = user_data['session_id']
                                st.session_state.is_admin = is_admin

                                # 如果是管理员登录，设置管理员模式
                                if admin_login and is_admin:
                                    st.session_state.admin_mode = True
                                    st.session_state.current_user = username
                                    st.success(f"👑 管理员 {username} 登录成功！")
                                else:
                                    st.session_state.admin_mode = False
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

                            # ========== 数据验证 ==========
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

# ========== 已登录，根据角色显示不同界面 ==========

# 如果是管理员模式，显示管理员界面
if st.session_state.get('admin_mode', False):
    # ========== 管理员界面 ==========
    st.title("👑 管理员控制台")
    st.markdown(f"欢迎管理员：**{st.session_state.username}**")
    st.divider()

    # 创建选项卡
    tab1, tab2, tab3 = st.tabs(["📋 用户管理", "📊 数据统计", "⚙️ 系统设置"])

    with tab1:
        st.subheader("用户列表")

        # 读取用户数据
        users_file = os.path.join(project_root, "auth", "users.json")

        if os.path.exists(users_file):
            with open(users_file, 'r', encoding='utf-8') as f:
                users_data = json.load(f)

            st.write(f"当前总用户数：{len(users_data)}")

            # 添加搜索框
            search_term = st.text_input("🔍 搜索用户（用户名/邮箱）", placeholder="输入关键字搜索...")

            # 过滤用户
            filtered_users = {}
            for username, user_info in users_data.items():
                if search_term:
                    if (search_term.lower() in username.lower() or
                            search_term.lower() in user_info.get('email', '').lower()):
                        filtered_users[username] = user_info
                else:
                    filtered_users = users_data

            # 遍历显示每个用户
            for username, user_info in filtered_users.items():
                with st.expander(f"👤 用户：{username}", expanded=False):
                    # 用户基本信息
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("**📧 邮箱**")
                        st.code(user_info.get('email', '无'), language="text")

                        st.markdown("**🔑 密码**")
                        st.code(user_info.get('password', '无'), language="text")

                    with col2:
                        st.markdown("**📅 注册时间**")
                        reg_time = user_info.get('created_at', '未知')
                        if reg_time:
                            st.code(reg_time, language="text")
                        else:
                            st.code("未记录", language="text")

                        st.markdown("**🆔 会话ID**")
                        st.code(user_info.get('session_id', '无'), language="text")

                    # 操作按钮
                    col_b1, col_b2, col_b3 = st.columns(3)
                    with col_b1:
                        if st.button(f"✏️ 编辑", key=f"edit_{username}", use_container_width=True):
                            st.session_state[f"edit_{username}"] = True
                    with col_b2:
                        if st.button(f"🗑️ 删除", key=f"delete_{username}", use_container_width=True):
                            st.session_state[f"confirm_delete_{username}"] = True
                    with col_b3:
                        if st.button(f"📊 会话", key=f"session_{username}", use_container_width=True):
                            st.session_state[f"session_{username}"] = True

                    # 编辑功能
                    if st.session_state.get(f"edit_{username}", False):
                        with st.container():
                            st.markdown("---")
                            st.subheader(f"✏️ 编辑用户 {username}")

                            with st.form(f"edit_form_{username}"):
                                new_email = st.text_input("新邮箱", value=user_info.get('email', ''))
                                new_password = st.text_input("新密码", value=user_info.get('password', ''))

                                col_s1, col_s2 = st.columns(2)
                                with col_s1:
                                    if st.form_submit_button("保存修改", use_container_width=True):
                                        # 更新用户数据
                                        users_data[username]['email'] = new_email
                                        users_data[username]['password'] = new_password

                                        # 保存到文件
                                        with open(users_file, 'w', encoding='utf-8') as f:
                                            json.dump(users_data, f, ensure_ascii=False, indent=2)

                                        st.success("用户信息已更新")
                                        st.session_state[f"edit_{username}"] = False
                                        st.rerun()

                                with col_s2:
                                    if st.form_submit_button("取消", use_container_width=True):
                                        st.session_state[f"edit_{username}"] = False
                                        st.rerun()

                    # 删除确认
                    if st.session_state.get(f"confirm_delete_{username}", False):
                        with st.container():
                            st.markdown("---")
                            col_warn1, col_warn2, col_warn3 = st.columns([2, 1, 1])
                            with col_warn1:
                                st.warning(f"⚠️ 确定要删除用户 {username} 吗？此操作不可恢复！")
                            with col_warn2:
                                if st.button("✅ 确认删除", key=f"confirm_yes_{username}", use_container_width=True):
                                    # 执行删除
                                    del users_data[username]
                                    with open(users_file, 'w', encoding='utf-8') as f:
                                        json.dump(users_data, f, ensure_ascii=False, indent=2)
                                    st.success(f"用户 {username} 已删除")
                                    st.session_state[f"confirm_delete_{username}"] = False
                                    st.rerun()
                            with col_warn3:
                                if st.button("❌ 取消", key=f"confirm_no_{username}", use_container_width=True):
                                    st.session_state[f"confirm_delete_{username}"] = False
                                    st.rerun()

                    # 会话历史查看
                    if st.session_state.get(f"session_{username}", False):
                        with st.container():
                            st.markdown("---")
                            st.subheader(f"📊 用户 {username} 的会话历史")

                            # 读取会话历史文件
                            session_file = os.path.join(project_root, "data", "chat_history",
                                                        user_info.get('session_id', ''))
                            if os.path.exists(session_file):
                                with open(session_file, 'r', encoding='utf-8') as f:
                                    sessions = json.load(f)
                                st.json(sessions)
                            else:
                                st.info("暂无会话历史")

                            if st.button("关闭会话历史", key=f"close_session_{username}"):
                                st.session_state[f"session_{username}"] = False
                                st.rerun()

                    st.divider()
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
                # 今日注册数（简单统计）
                today_count = sum(1 for u in users_data.values()
                                if u.get('created_at', '').startswith(datetime.now().strftime("%Y-%m-%d")))
                st.metric("今日注册", today_count)
            with col_s3:
                st.metric("文件大小", f"{os.path.getsize(users_file)} bytes")

            # 邮箱域名统计
            st.subheader("📧 邮箱域名分布")
            domains = {}
            for user_info in users_data.values():
                email = user_info.get('email', '')
                if '@' in email:
                    domain = email.split('@')[1]
                    domains[domain] = domains.get(domain, 0) + 1

            if domains:
                for domain, count in domains.items():
                    st.progress(count / len(users_data), text=f"{domain}: {count}人 ({count/len(users_data)*100:.1f}%)")
            else:
                st.info("暂无邮箱数据")

            # 注册时间分布
            st.subheader("📅 注册时间分布")
            dates = {}
            for user_info in users_data.values():
                date = user_info.get('created_at', '未知')[:10]  # 只取日期部分
                dates[date] = dates.get(date, 0) + 1

            if dates:
                st.bar_chart(dates)
            else:
                st.info("暂无注册时间数据")

    with tab3:
        st.subheader("系统设置")

        st.info("管理员设置功能开发中...")

        # 导出数据
        if st.button("📥 导出所有用户数据"):
            if os.path.exists(users_file):
                with open(users_file, 'r', encoding='utf-8') as f:
                    users_data = json.load(f)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"users_backup_{timestamp}.json"

                st.download_button(
                    label="点击下载备份文件",
                    data=json.dumps(users_data, ensure_ascii=False, indent=2),
                    file_name=filename,
                    mime="application/json"
                )

    # 管理员侧边栏
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
            st.session_state.admin_mode = False
            st.rerun()

# ========== 普通用户界面 ==========
else:
    # 侧边栏显示用户信息
    with st.sidebar:
        # 如果是管理员但没用管理员模式，提示可以切换
        if st.session_state.username in ADMIN_USERS:
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