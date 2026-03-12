"""
知识库
"""
import sys
import os
# 获取项目根目录的绝对路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import hashlib
from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from datetime import datetime

# 直接导入配置变量
from config.config_data import (
    DASHSCOPE_API_KEY, md5_path, persist_directory, collection_name,
    chunk_size, chunk_overlap, separators, max_split_char_number
)


def check_md5(md5_str: str):
    """检查传入的md5字符串是否已经被处理过了
        return False(md5未处理过)  True(已经处理过，已有记录）
    """
    if not os.path.exists(md5_path):
        # if进入表示文件不存在，那肯定没有处理过这个md5了
        open(md5_path, 'w', encoding='utf-8').close()
        return False
    else:
        for line in open(md5_path, 'r', encoding='utf-8').readlines():
            line = line.strip()     # 处理字符串前后的空格和回车
            if line == md5_str:
                return True         # 已处理过

        return False


def save_md5(md5_str: str):
    """将传入的md5字符串，记录到文件内保存"""
    with open(md5_path, 'a', encoding="utf-8") as f:
        f.write(md5_str + '\n')


def get_string_md5(input_str: str, encoding='utf-8'):
    """将传入的字符串转换为md5字符串"""

    # 将字符串转换为bytes字节数组
    str_bytes = input_str.encode(encoding=encoding)

    # 创建md5对象
    md5_obj = hashlib.md5()     # 得到md5对象
    md5_obj.update(str_bytes)   # 更新内容（传入即将要转换的字节数组）
    md5_hex = md5_obj.hexdigest()       # 得到md5的十六进制字符串

    return md5_hex


class KnowledgeBaseService(object):
    def __init__(self):
        # 如果文件夹不存在则创建，如果存在则跳过
        os.makedirs(persist_directory, exist_ok=True)

        # 创建嵌入模型实例，传入API key
        self.embeddings = DashScopeEmbeddings(
            model="text-embedding-v4",
            dashscope_api_key=DASHSCOPE_API_KEY
        )

        self.chroma = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=persist_directory,
        )

        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len,
        )

    def upload_by_str(self, data: str, filename):
        """将传入的字符串，进行向量化，存入向量数据库中"""
        # 先得到传入字符串的md5值
        md5_hex = get_string_md5(data)

        if check_md5(md5_hex):
            return "[跳过]内容已经存在知识库中"

        if len(data) > max_split_char_number:
            knowledge_chunks: list[str] = self.spliter.split_text(data)
        else:
            knowledge_chunks = [data]

        metadata = {
            "source": filename,
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "operator": "小曹",
        }

        self.chroma.add_texts(
            knowledge_chunks,
            metadatas=[metadata for _ in knowledge_chunks],
        )

        save_md5(md5_hex)

        return "[成功]内容已经成功载入向量库"


if __name__ == '__main__':
    service = KnowledgeBaseService()
    r = service.upload_by_str("周杰轮222", "testfile")
    print(r)