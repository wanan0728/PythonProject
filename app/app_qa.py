"""
智能客服主应用
添加了用户注册登录功能 + 管理员独立界面 + 弹窗提示 + 知识库上传
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
from pathlib import Path

# 页面配置
st.set_page_config(
    page_title="Xin计划攻略ai问答助手",
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
    st.session_state.selected_tab = "登录"
if 'kb_service' not in st.session_state:
    st.session_state.kb_service = None

# ========== 管理员账户配置 ==========
ADMIN_USERS = ["admin"]

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
                    欢迎 <strong>{username}</strong> Xin计划攻略助手<br>
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

    # 强制切换到登录模式
    st.session_state.selected_tab = "登录"
    st.session_state.register_mode = False

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

# ========== 初始化知识库服务 ==========
def init_kb_service():
    """初始化知识库服务，返回服务实例"""
    if st.session_state.kb_service is None:
        try:
            from core.knowledge_base import KnowledgeBaseService
            st.session_state.kb_service = KnowledgeBaseService(use_multimodal=True)
            print("✅ 知识库服务初始化成功")
        except Exception as e:
            print(f"❌ 知识库服务初始化失败: {e}")
            st.session_state.kb_service = None
    return st.session_state.kb_service

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

    st.title("🤖 Xin计划攻略ai问答助手")
    st.markdown("---")

    # 创建三列布局
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        # 切换登录/注册模式
        mode = st.radio(
            "选择操作",
            ["登录", "注册"],
            horizontal=True,
            key="selected_tab"
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

                # 限流提示
                if username:
                    try:
                        from utils.ratelimit import rate_limit_manager
                        remaining = rate_limit_manager.get_remaining(username, "login")
                        if remaining <= 2:
                            st.error(f"⚠️ 严重警告：仅剩 {remaining} 次登录机会！")
                        elif remaining <= 5:
                            st.warning(f"⚠️ 今日剩余登录尝试: {remaining}次")
                        elif remaining <= 10:
                            st.info(f"📊 今日剩余登录尝试: {remaining}次")
                    except Exception as e:
                        pass

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
        st.subheader("📤 知识库管理")

        # 创建九个子选项卡（每个都有唯一标识）
        sub_tab1, sub_tab2, sub_tab3, sub_tab4, sub_tab5, sub_tab6, sub_tab7, sub_tab8, sub_tab9 = st.tabs([
            "📁 上传文档",
            "📊 知识库状态",
            "📋 文档管理",
            "📋 系统日志",
            "⚡ 缓存管理",
            "🛡️ 限流管理",
            "🎯 检索配置",
            "📈 重排序配置",
            "🔍 查询优化"
        ])

        with sub_tab1:
            st.markdown("### 📤 上传文档（支持多模态）")
            st.caption("支持格式: TXT, PDF, DOCX, 图片 (JPG/PNG)")

            # 初始化知识库服务（多模态）
            if 'kb_service' not in st.session_state or st.session_state.kb_service is None:
                from core.knowledge_base import KnowledgeBaseService
                try:
                    st.session_state.kb_service = KnowledgeBaseService(use_multimodal=True)
                    st.success("✅ 知识库服务初始化成功（多模态）")
                except Exception as e:
                    st.error(f"❌ 知识库服务初始化失败: {e}")

            kb_service = st.session_state.kb_service

            if kb_service is None:
                st.error("❌ 知识库服务不可用")
            else:
                # 文件上传（支持多格式）
                uploaded_files = st.file_uploader(
                    "选择文件",
                    type=['txt', 'pdf', 'docx', 'jpg', 'jpeg', 'png'],
                    accept_multiple_files=True,
                    key="multimodal_uploader"
                )

                if uploaded_files:
                    st.write(f"已选择 {len(uploaded_files)} 个文件")

                    # 显示文件列表
                    for file in uploaded_files:
                        file_ext = file.name.split('.')[-1].lower()
                        icons = {
                            'pdf': '📕', 'docx': '📘', 'txt': '📄',
                            'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️'
                        }
                        icon = icons.get(file_ext, '📁')

                        col_f1, col_f2, col_f3 = st.columns([3, 2, 1])
                        with col_f1:
                            st.write(f"{icon} {file.name}")
                        with col_f2:
                            st.caption(f"{file.size/1024:.1f} KB")

                    # 添加强制上传选项
                    force_upload = st.checkbox("强制上传（忽略重复检查）", key="force_upload_checkbox")

                    # 上传按钮
                    if st.button("🚀 开始上传所有文件", type="primary", use_container_width=True, key="upload_all_files_button"):
                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        results = []
                        for i, file in enumerate(uploaded_files):
                            status_text.text(f"处理中: {file.name} ({i+1}/{len(uploaded_files)})")

                            temp_path = None
                            try:
                                import tempfile
                                import os

                                # 创建临时文件
                                with tempfile.NamedTemporaryFile(
                                    delete=False,
                                    suffix=os.path.splitext(file.name)[1]
                                ) as tmp_file:
                                    tmp_file.write(file.getvalue())
                                    temp_path = tmp_file.name

                                # 调用多模态上传（传入原始文件名和强制选项）
                                result = kb_service.upload_file(temp_path, file.name, force=force_upload)
                                results.append((file.name, result))

                            except Exception as e:
                                results.append((file.name, f"❌ 失败: {str(e)}"))
                            finally:
                                # 清理临时文件
                                if temp_path and os.path.exists(temp_path):
                                    try:
                                        os.unlink(temp_path)
                                    except:
                                        pass

                            progress_bar.progress((i + 1) / len(uploaded_files))

                        status_text.text("处理完成！")

                        # 显示结果
                        st.markdown("---")
                        st.subheader("上传结果")
                        for name, result in results:
                            if "成功" in result:
                                st.success(f"✅ {name}: {result}")
                            elif "跳过" in result:
                                st.info(f"⏭️ {name}: {result}")
                            else:
                                st.error(f"❌ {name}: {result}")

                        if any("成功" in r for _, r in results):
                            st.balloons()

        with sub_tab2:
            st.markdown("### 📊 知识库状态（多模态）")

            try:
                kb_service = st.session_state.kb_service
                if kb_service and hasattr(kb_service, 'chroma'):
                    count = kb_service.chroma._collection.count()
                    st.metric("📊 文档片段总数", count)

                    if count > 0:
                        all_docs = kb_service.chroma.get()

                        # 统计来源和类型
                        sources = {}
                        types = {"text": 0, "image": 0}

                        for metadata in all_docs['metadatas']:
                            if metadata:
                                source = metadata.get('source', 'unknown')
                                sources[source] = sources.get(source, 0) + 1

                                if metadata.get('type') == 'image':
                                    types["image"] += 1
                                else:
                                    types["text"] += 1

                        # 显示类型分布
                        st.subheader("📁 文档类型分布")
                        col_t1, col_t2 = st.columns(2)
                        with col_t1:
                            st.metric("文本块", types["text"])
                        with col_t2:
                            st.metric("图片块", types["image"])

                        # 显示来源统计
                        if sources:
                            st.subheader("📁 文件来源统计")
                            for source, num in list(sources.items())[:10]:
                                st.progress(num / count, text=f"{Path(source).name}: {num}个块")

                        # 显示最近上传
                        st.subheader("🕒 最近上传")
                        recent = sorted(all_docs['metadatas'],
                                      key=lambda x: x.get('create_time', ''),
                                      reverse=True)[:5]
                        for meta in recent:
                            if meta:
                                source = Path(meta.get('source', '未知')).name
                                st.caption(f"📄 {source} - {meta.get('create_time', '未知')}")
                    else:
                        st.info("知识库暂无数据，请上传文档")
                else:
                    st.warning("知识库服务未初始化")
            except Exception as e:
                st.warning(f"无法读取知识库状态: {e}")

            if st.button("🔄 刷新状态", key="refresh_kb_status"):
                st.rerun()

        with sub_tab3:
            st.markdown("### 📋 文档管理")
            st.caption("查看和管理已上传的文档")

            kb_service = st.session_state.kb_service
            if kb_service is None:
                st.error("❌ 知识库服务未初始化")
            else:
                # 获取所有文档
                documents = kb_service.get_all_documents()

                if not documents:
                    st.info("📭 知识库中暂无文档")
                else:
                    st.write(f"📊 共找到 {len(documents)} 个文档块")

                    # 按源文件分组
                    sources = {}
                    for doc in documents:
                        source = doc['source']
                        if source not in sources:
                            sources[source] = []
                        sources[source].append(doc)

                    # 显示每个源文件
                    for source, docs in sources.items():
                        with st.expander(f"📄 {source} ({len(docs)}个块)", expanded=False):
                            # 显示文档块列表
                            for i, doc in enumerate(docs[:5]):  # 只显示前5个块
                                st.caption(f"块 {i+1}: {doc['content_preview']}")

                            if len(docs) > 5:
                                st.caption(f"... 还有 {len(docs)-5} 个块")

                            # 删除按钮
                            col_d1, col_d2, col_d3 = st.columns([2, 2, 1])
                            with col_d2:
                                if st.button(f"🗑️ 删除整个文件", key=f"del_source_{source}"):
                                    if st.session_state.get(f"confirm_del_{source}", False):
                                        # 执行删除
                                        count = kb_service.delete_by_source(source)
                                        if count > 0:
                                            st.success(f"✅ 已删除 {count} 个文档块")
                                            st.session_state[f"confirm_del_{source}"] = False
                                            st.rerun()
                                        else:
                                            st.error("❌ 删除失败")
                                    else:
                                        st.session_state[f"confirm_del_{source}"] = True
                                        st.warning(f"⚠️ 确定要删除 {source} 吗？再次点击确认")

                            with col_d3:
                                if st.button(f"❌ 取消", key=f"cancel_del_{source}"):
                                    st.session_state[f"confirm_del_{source}"] = False
                                    st.rerun()

                    # 批量操作
                    st.markdown("---")
                    col_b1, col_b2, col_b3 = st.columns(3)
                    with col_b1:
                        if st.button("🗑️ 清空所有文档", type="primary", use_container_width=True, key="clear_all_docs_button"):
                            st.session_state["confirm_clear_all_docs"] = True

                    if st.session_state.get("confirm_clear_all_docs", False):
                        st.warning("⚠️ 确定要清空所有文档吗？此操作不可恢复！")
                        col_c1, col_c2 = st.columns(2)
                        with col_c1:
                            if st.button("✅ 确认清空", use_container_width=True, key="confirm_clear_docs"):
                                if kb_service.clear_all_documents():
                                    st.success("✅ 所有文档已清空")
                                    st.session_state["confirm_clear_all_docs"] = False
                                    st.rerun()
                        with col_c2:
                            if st.button("❌ 取消", use_container_width=True, key="cancel_clear_docs"):
                                st.session_state["confirm_clear_all_docs"] = False
                                st.rerun()

        with sub_tab4:
            st.markdown("### 📋 系统日志")
            st.caption("查看应用运行日志，帮助排查问题")

            # 日志文件路径
            log_dir = os.path.join(project_root, "logs")

            # 创建日志查看选项
            col_log1, col_log2 = st.columns([2, 1])

            with col_log1:
                # 获取可用的日志文件
                log_files = []
                if os.path.exists(log_dir):
                    log_files = [f for f in os.listdir(log_dir)
                               if f.endswith('.log') and not f.endswith('.zip')]
                    log_files.sort(reverse=True)

                if log_files:
                    selected_log = st.selectbox(
                        "选择日志文件",
                        log_files,
                        format_func=lambda x: f"📄 {x}"
                    )
                else:
                    st.info("暂无日志文件")
                    selected_log = None

            with col_log2:
                st.write("")
                st.write("")
                log_level = st.selectbox(
                    "日志级别",
                    ["ALL", "INFO", "WARNING", "ERROR", "DEBUG"],
                    index=0,
                    key="log_level_select"
                )

            if selected_log:
                log_path = os.path.join(log_dir, selected_log)

                # 添加控制按钮
                col_ctl1, col_ctl2, col_ctl3, col_ctl4 = st.columns(4)
                with col_ctl1:
                    lines = st.number_input("显示行数", min_value=10, max_value=1000, value=100, step=10, key="log_lines")
                with col_ctl2:
                    auto_refresh = st.checkbox("自动刷新", key="auto_refresh_log")
                with col_ctl3:
                    if st.button("🔄 刷新", key="refresh_log"):
                        st.rerun()
                with col_ctl4:
                    if st.button("📥 下载日志", key="download_log"):
                        with open(log_path, 'r', encoding='utf-8') as f:
                            log_content = f.read()
                        st.download_button(
                            label="点击下载",
                            data=log_content,
                            file_name=selected_log,
                            mime="text/plain",
                            key="download_log_button"
                        )

                # 读取并显示日志
                try:
                    with open(log_path, 'r', encoding='utf-8') as f:
                        all_lines = f.readlines()

                    # 根据日志级别过滤
                    filtered_lines = []
                    for line in all_lines[-lines:]:
                        if log_level == "ALL":
                            filtered_lines.append(line)
                        elif log_level == "ERROR" and "ERROR" in line:
                            filtered_lines.append(line)
                        elif log_level == "WARNING" and "WARNING" in line:
                            filtered_lines.append(line)
                        elif log_level == "INFO" and "INFO" in line:
                            filtered_lines.append(line)
                        elif log_level == "DEBUG" and "DEBUG" in line:
                            filtered_lines.append(line)

                    if filtered_lines:
                        st.code("".join(filtered_lines), language="text")
                        st.caption(f"显示 {len(filtered_lines)} 行日志 (共 {len(all_lines)} 行)")
                    else:
                        st.info("没有匹配的日志")

                except Exception as e:
                    st.error(f"读取日志失败: {e}")

        with sub_tab5:
            st.markdown("### ⚡ 缓存管理")
            st.caption("管理问答缓存，提高响应速度")

            from utils.cache import cache_manager

            # 显示缓存信息
            st.info(f"当前缓存类型: **{cache_manager.cache_type.upper()}**")

            col_c1, col_c2, col_c3 = st.columns(3)

            with col_c1:
                if st.button("🗑️ 清除所有缓存", use_container_width=True, key="clear_all_cache"):
                    count = cache_manager.clear_cache()
                    st.success(f"已清除 {count} 个缓存项")

            with col_c2:
                if st.button("👤 清除当前用户缓存", use_container_width=True, key="clear_user_cache"):
                    if st.session_state.get('username'):
                        count = cache_manager.clear_cache(f"*{st.session_state.username}*")
                        st.success(f"已清除用户 {st.session_state.username} 的 {count} 个缓存")
                    else:
                        st.warning("未登录")

            with col_c3:
                if st.button("🔄 刷新状态", use_container_width=True, key="refresh_cache"):
                    st.rerun()

            # 缓存说明
            st.markdown("---")
            st.markdown("### 📊 缓存说明")
            st.markdown("""
            - **缓存内容**：用户问答对
            - **缓存时间**：1小时
            - **缓存键**：基于用户名和问题生成
            - **命中效果**：相同问题直接返回，无需调用模型
            """)

        with sub_tab6:
            st.markdown("### 🛡️ 限流管理")
            st.caption("管理API请求频率限制，防止滥用")

            from utils.ratelimit import rate_limit_manager, RATE_LIMITS, USER_BLACKLIST, IP_BLACKLIST

            col_r1, col_r2 = st.columns(2)

            with col_r1:
                st.subheader("📊 限流规则")
                for action, rule in RATE_LIMITS.items():
                    st.info(f"**{action}**: {rule['max_attempts']}次/{rule['window']}秒")

            with col_r2:
                st.subheader("⛔ 黑名单管理")

                # 用户黑名单
                st.markdown("**用户黑名单**")
                if USER_BLACKLIST:
                    for user in list(USER_BLACKLIST):
                        col_u1, col_u2 = st.columns([3, 1])
                        with col_u1:
                            st.write(f"👤 {user}")
                        with col_u2:
                            if st.button("解封", key=f"unblock_user_{user}"):
                                rate_limit_manager.unblock_user(user)
                                st.rerun()
                else:
                    st.caption("暂无黑名单用户")

                # IP黑名单
                st.markdown("**IP黑名单**")
                if IP_BLACKLIST:
                    for ip in list(IP_BLACKLIST):
                        col_i1, col_i2 = st.columns([3, 1])
                        with col_i1:
                            st.write(f"🌐 {ip}")
                        with col_i2:
                            if st.button("解封", key=f"unblock_ip_{ip}"):
                                rate_limit_manager.unblock_ip(ip)
                                st.rerun()
                else:
                    st.caption("暂无黑名单IP")

            # 手动封禁
            st.markdown("---")
            st.subheader("🔨 手动封禁")

            col_ban1, col_ban2 = st.columns(2)

            with col_ban1:
                with st.form("ban_user_form"):
                    ban_user = st.text_input("用户名", key="ban_user_input")
                    ban_user_duration = st.number_input("封禁时长(秒)", min_value=60, value=3600, step=60, key="ban_user_duration")
                    if st.form_submit_button("封禁用户"):
                        rate_limit_manager.block_user(ban_user, ban_user_duration)
                        st.success(f"用户 {ban_user} 已封禁")
                        st.rerun()

            with col_ban2:
                with st.form("ban_ip_form"):
                    ban_ip = st.text_input("IP地址", key="ban_ip_input")
                    ban_ip_duration = st.number_input("封禁时长(秒)", min_value=60, value=3600, step=60, key="ban_ip_duration")
                    if st.form_submit_button("封禁IP"):
                        rate_limit_manager.block_ip(ban_ip, ban_ip_duration)
                        st.success(f"IP {ban_ip} 已封禁")
                        st.rerun()

        with sub_tab7:
            st.markdown("### 🎯 检索配置")
            st.caption("配置混合检索权重")

            col_w1, col_w2 = st.columns(2)
            with col_w1:
                vector_weight = st.slider(
                    "向量检索权重（语义）",
                    min_value=0.0, max_value=1.0, value=0.7, step=0.1,
                    key="vector_weight_slider"
                )
            with col_w2:
                bm25_weight = st.slider(
                    "BM25检索权重（关键词）",
                    min_value=0.0, max_value=1.0, value=0.3, step=0.1,
                    key="bm25_weight_slider"
                )

            if abs(vector_weight + bm25_weight - 1.0) > 0.01:
                st.warning("⚠️ 权重之和应该为 1.0")

            if st.button("保存配置", key="save_retrieval_config"):
                st.session_state.vector_weight = vector_weight
                st.session_state.bm25_weight = bm25_weight
                st.success("✅ 配置已保存")

            st.markdown("---")
            st.markdown("### 📊 BM25 索引状态")

            from core.vector_stores import VectorStoreService
            from core.hybrid_retriever import BM25Retriever

            bm25 = BM25Retriever()
            if bm25.load_index():
                st.success(f"✅ BM25 索引已加载，包含 {len(bm25.documents)} 个文档")
            else:
                st.warning("⚠️ BM25 索引不存在，请上传文档后自动生成")

            if st.button("手动重建 BM25 索引", key="rebuild_bm25"):
                with st.spinner("正在重建索引..."):
                    try:
                        kb_service = st.session_state.kb_service
                        all_docs = kb_service.chroma.get()

                        from langchain_core.documents import Document
                        documents = []
                        for content, metadata in zip(all_docs['documents'], all_docs['metadatas']):
                            doc = Document(page_content=content, metadata=metadata)
                            documents.append(doc)

                        bm25.add_documents(documents)
                        st.success(f"✅ BM25 索引重建完成，共 {len(documents)} 个文档")
                    except Exception as e:
                        st.error(f"❌ 重建失败: {e}")

        with sub_tab8:
            st.markdown("### 📈 重排序配置")
            st.caption("使用专门的模型对检索结果重新排序，提高相关性")

            col_r1, col_r2 = st.columns(2)

            with col_r1:
                enable_reranker = st.checkbox("启用重排序", value=True, key="enable_reranker")
                reranker_model = st.selectbox(
                    "重排序模型",
                    ["BAAI/bge-reranker-base", "BAAI/bge-reranker-large", "cross-encoder/ms-marco-MiniLM-L-6-v2"],
                    index=0,
                    key="reranker_model"
                )

            with col_r2:
                initial_k = st.number_input("初始检索数量", min_value=5, max_value=50, value=20, key="initial_k")
                top_k = st.number_input("最终返回数量", min_value=1, max_value=10, value=5, key="top_k")

            st.markdown("---")
            st.markdown("### 📊 效果说明")
            st.markdown("""
            - **初始检索**：先用混合检索找出前 N 个候选文档
            - **重排序**：用专门的模型对候选文档重新打分
            - **最终结果**：返回最相关的 M 个文档
            
            重排序可以提升问答准确率 5-10%，但会增加少量延迟。
            """)

            if st.button("保存配置", key="save_rerank_config"):
                st.session_state.EnableReranker = enable_reranker
                st.session_state.RerankerModel = reranker_model
                st.session_state.RerankerInitialK = initial_k
                st.session_state.RerankerTopK = top_k
                st.success("✅ 配置已保存，重启后生效")

        with sub_tab9:
            st.markdown("### 🔍 查询优化配置")
            st.caption("对用户问题进行改写、拆分，提高检索效果")

            col_q1, col_q2 = st.columns(2)

            with col_q1:
                enable_optimization = st.checkbox("启用查询优化", value=True, key="enable_query_opt")
                enable_hyde = st.checkbox("启用HyDE（生成假答案检索）", value=False, key="enable_hyde")

            with col_q2:
                expansion_size = st.number_input("查询扩展数量", min_value=1, max_value=5, value=3, key="expansion_size")

            st.markdown("---")
            st.markdown("### 📊 优化效果说明")
            st.markdown("""
            **问题改写**：将口语化问题转为标准形式
            - "雷伊咋整啊？" → "雷伊怎么获得？"
            
            **子查询拆分**：复杂问题拆分成多个简单问题
            - "雷伊怎么获得和怎么培养？" → ["雷伊怎么获得？", "雷伊怎么培养？"]
            
            **HyDE**：先生成假答案再检索，提高准确率
            """)

            if st.button("保存配置", key="save_query_config"):
                st.session_state.UseQueryOptimization = enable_optimization
                st.session_state.UseHyDE = enable_hyde
                st.session_state.QueryExpansionSize = expansion_size
                st.success("✅ 配置已保存，重启后生效")

    with st.sidebar:
        st.markdown(f"### 👑 管理员：**{st.session_state.username}**")
        st.markdown(f"📧 {st.session_state.email}")
        st.markdown("---")

        # 退出管理员模式
        if st.button("🔙 退出管理员模式", use_container_width=True, key="exit_admin_mode"):
            st.session_state.admin_mode = False
            st.rerun()

        # 退出登录
        if st.button("🚪 退出登录", use_container_width=True, key="admin_logout"):
            auth_manager.logout()
            st.rerun()

# 普通用户界面
else:
    with st.sidebar:
        # 如果是管理员但没用管理员模式，提示可以切换
        if st.session_state.get('username') and st.session_state.username in ADMIN_USERS:
            st.info("👑 您是管理员，可以切换到管理员模式")
            if st.button("🔐 进入管理员模式", use_container_width=True, key="enter_admin_mode"):
                st.session_state.admin_mode = True
                st.rerun()
            st.markdown("---")

        st.markdown(f"### 👋 欢迎，**{st.session_state.username}**")
        st.markdown(f"📧 {st.session_state.email}")
        st.markdown("---")

        # 退出登录按钮
        if st.button("🚪 退出登录", use_container_width=True, key="user_logout"):
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
    st.title("🤖 Xin计划攻略ai问答助手")
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

