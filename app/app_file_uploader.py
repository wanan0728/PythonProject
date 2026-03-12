"""
基于Streamlit完成WEB网页上传服务
"""
import sys
import os
# 获取项目根目录的绝对路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import time
import streamlit as st
from core.knowledge_base import KnowledgeBaseService

# 添加网页标题
st.title("知识库更新服务")

# file_uploader
uploader_file = st.file_uploader(
    "请上传TXT文件",
    type=['txt'],
    accept_multiple_files=False,
)

# session_state就是一个字典
if "service" not in st.session_state:
    st.session_state["service"] = KnowledgeBaseService()

if uploader_file is not None:
    # 提取文件的信息
    file_name = uploader_file.name
    file_type = uploader_file.type
    file_size = uploader_file.size / 1024    # KB

    st.subheader(f"文件名：{file_name}")
    st.write(f"格式：{file_type} | 大小：{file_size:.2f} KB")

    # get_value -> bytes -> decode('utf-8')
    text = uploader_file.getvalue().decode("utf-8")

    with st.spinner("载入知识库中。。。"):
        time.sleep(1)
        result = st.session_state["service"].upload_by_str(text, file_name)
        st.write(result)