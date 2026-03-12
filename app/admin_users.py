"""
管理员查看用户页面
"""
import sys
import os
# 获取项目根目录的绝对路径（确保和 app_qa.py 一致）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import streamlit as st
import json
from datetime import datetime

st.set_page_config(
    page_title="用户管理",
    page_icon="👥",
    layout="wide"
)

st.title("👥 用户数据管理")

# 调试信息 - 显示当前路径
with st.expander("🔧 调试信息"):
    st.write(f"当前文件路径: {__file__}")
    st.write(f"项目根目录: {project_root}")

    # 使用和 app_qa.py 完全相同的路径
    users_file = os.path.join(project_root, "auth", "users.json")
    st.write(f"users.json 路径: {users_file}")
    st.write(f"文件是否存在: {os.path.exists(users_file)}")

    # 列出 auth 文件夹内容
    auth_dir = os.path.join(project_root, "auth")
    if os.path.exists(auth_dir):
        st.write("auth 文件夹内容:")
        files = os.listdir(auth_dir)
        st.write(files)
    else:
        st.error(f"auth 文件夹不存在: {auth_dir}")

# 设置简单密码保护
st.sidebar.header("管理员登录")
password = st.sidebar.text_input("请输入管理员密码", type="password")

ADMIN_PASSWORD = "admin123"

if password != ADMIN_PASSWORD:
    st.warning("🔒 请输入管理员密码查看用户数据")
    st.stop()

st.sidebar.success("✅ 管理员验证成功")

# 使用绝对路径读取 users.json
users_file = os.path.join(project_root, "auth", "users.json")

# 创建两列布局
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📋 用户列表")

    if os.path.exists(users_file):
        try:
            with open(users_file, 'r', encoding='utf-8') as f:
                users_data = json.load(f)

            st.success(f"✅ 找到 {len(users_data)} 个注册用户")

            # 显示用户列表
            if users_data:
                for username, user_info in users_data.items():
                    with st.expander(f"👤 用户：{username}"):
                        col_info1, col_info2 = st.columns(2)
                        with col_info1:
                            st.write("**邮箱：**", user_info.get('email', '无'))
                            st.write("**会话ID：**", user_info.get('session_id', '无'))
                        with col_info2:
                            st.write("**注册时间：**", user_info.get('created_at', '未知'))
                            pwd_hash = user_info.get('password', '')
                            st.write("**密码哈希：**", pwd_hash[:20] + "..." if pwd_hash else "无")
            else:
                st.info("暂无注册用户")
        except Exception as e:
            st.error(f"读取文件失败: {e}")
    else:
        st.error("❌ users.json 文件不存在")
        # 尝试创建文件
        try:
            os.makedirs(os.path.dirname(users_file), exist_ok=True)
            with open(users_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            st.success("✅ 已创建 users.json 文件，请刷新页面")
        except Exception as e:
            st.error(f"创建文件失败: {e}")

with col2:
    st.subheader("📊 数据统计")

    if os.path.exists(users_file) and 'users_data' in locals() and users_data:
        total_users = len(users_data)
        st.metric("总用户数", total_users)

        # 邮箱域名统计
        email_domains = {}
        for user_info in users_data.values():
            email = user_info.get('email', '')
            if '@' in email:
                domain = email.split('@')[1]
                email_domains[domain] = email_domains.get(domain, 0) + 1

        if email_domains:
            st.subheader("📧 邮箱域名分布")
            for domain, count in email_domains.items():
                st.write(f"{domain}: {count}人")

        # 导出功能
        st.subheader("💾 数据备份")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"users_backup_{timestamp}.json"

        st.download_button(
            label="📥 下载用户数据 JSON",
            data=json.dumps(users_data, ensure_ascii=False, indent=2),
            file_name=filename,
            mime="application/json",
            use_container_width=True
        )

        # 清空数据按钮
        if st.button("⚠️ 清空所有用户数据", type="primary", use_container_width=True):
            confirm = st.text_input("输入 'CONFIRM' 确认清空")
            if confirm == "CONFIRM":
                with open(users_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
                st.success("✅ 已清空所有用户数据")
                st.rerun()
    else:
        st.info("暂无统计数据")

st.markdown("---")
st.caption("⚠️ 注意：Streamlit Cloud 重启后数据可能丢失，请定期备份")