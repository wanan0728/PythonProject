"""
知识库（多模态版本）
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import hashlib
import shutil
from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from datetime import datetime
from pathlib import Path
from typing import Union, List, Dict, Any, Optional

from config.config_data import *
from utils.logger import logger, log_performance
from core.multimodal_processor import MultimodalProcessor, MultimodalLoader


class KnowledgeBaseService:
    def __init__(self, use_multimodal: bool = True):
        logger.info("初始化 KnowledgeBaseService（多模态）")

        # 确保目录存在
        os.makedirs(persist_directory, exist_ok=True)
        os.makedirs(os.path.dirname(md5_path), exist_ok=True)

        # 打印确认路径
        print(f"🔍 Chroma数据库路径: {persist_directory}")
        print(f"🔍 MD5文件路径: {md5_path}")

        self.embeddings = DashScopeEmbeddings(
            model="text-embedding-v4",
            dashscope_api_key=DASHSCOPE_API_KEY
        )

        # 尝试获取或创建集合
        try:
            self.chroma = Chroma(
                collection_name=collection_name,
                embedding_function=self.embeddings,
                persist_directory=persist_directory,
            )
            # 测试集合是否存在
            count = self.chroma._collection.count()
            logger.info(f"✅ 成功连接到集合: {collection_name}，当前文档数: {count}")
        except Exception as e:
            logger.warning(f"⚠️ 集合不存在，正在创建: {e}")
            # 创建新集合
            self.chroma = Chroma.from_documents(
                documents=[],
                embedding=self.embeddings,
                collection_name=collection_name,
                persist_directory=persist_directory,
            )
            logger.info(f"✅ 已创建新集合: {collection_name}")

        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len,
        )

        # 多模态处理器
        self.multimodal = MultimodalProcessor(use_image_captioning=False)
        self.multimodal_loader = MultimodalLoader(self.multimodal)

        # 记录初始化时的文档数
        try:
            self.doc_count = self.chroma._collection.count()
            logger.info(f"知识库初始化完成，当前文档数: {self.doc_count}")
        except Exception as e:
            logger.warning(f"无法获取文档数: {e}")
            self.doc_count = 0

    def check_md5(self, md5_str: str) -> bool:
        """检查MD5是否已存在"""
        if not os.path.exists(md5_path):
            return False
        try:
            with open(md5_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip() == md5_str:
                        return True
        except:
            pass
        return False

    def save_md5(self, md5_str: str):
        """保存MD5"""
        with open(md5_path, 'a', encoding='utf-8') as f:
            f.write(md5_str + '\n')

    def get_file_md5(self, file_path: Union[str, Path]) -> str:
        """计算文件MD5"""
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5()
            while chunk := f.read(8192):
                file_hash.update(chunk)
        return file_hash.hexdigest()

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """获取所有文档的元数据"""
        try:
            # 先检查集合是否存在
            count = self.chroma._collection.count()
            if count == 0:
                return []

            all_docs = self.chroma.get()
            documents = []
            for i, (doc_id, metadata) in enumerate(zip(all_docs['ids'], all_docs['metadatas'])):
                if metadata:
                    content_preview = ""
                    if all_docs['documents'] and i < len(all_docs['documents']):
                        content = all_docs['documents'][i]
                        content_preview = content[:100] + "..." if content else ""

                    # 从source中提取文件名（去掉路径）
                    source = metadata.get('source', '未知')
                    if '\\' in source:
                        source = source.split('\\')[-1]
                    elif '/' in source:
                        source = source.split('/')[-1]

                    documents.append({
                        'id': doc_id,
                        'source': source,
                        'full_source': metadata.get('source', '未知'),
                        'create_time': metadata.get('create_time', '未知'),
                        'type': metadata.get('type', 'text'),
                        'content_preview': content_preview
                    })
            return documents
        except Exception as e:
            logger.error(f"获取文档列表失败: {e}")
            return []

    def delete_document(self, doc_id: str) -> bool:
        """根据文档ID删除单个文档"""
        try:
            self.chroma._collection.delete(ids=[doc_id])
            logger.info(f"✅ 删除文档: {doc_id}")

            # 强制持久化
            if hasattr(self.chroma, 'persist'):
                self.chroma.persist()

            self.doc_count = self.chroma._collection.count()
            return True
        except Exception as e:
            logger.error(f"删除文档失败: {doc_id}, 错误: {e}")
            return False

    def delete_by_source(self, source_name: str) -> int:
        """根据源文件名删除所有相关文档"""
        try:
            # 查找所有匹配的文档
            all_docs = self.chroma.get()
            ids_to_delete = []

            for doc_id, metadata in zip(all_docs['ids'], all_docs['metadatas']):
                if metadata:
                    # 支持匹配完整路径或文件名
                    meta_source = metadata.get('source', '')
                    if source_name in meta_source or meta_source.endswith(source_name):
                        ids_to_delete.append(doc_id)

            if ids_to_delete:
                self.chroma._collection.delete(ids=ids_to_delete)
                logger.info(f"✅ 删除源文件 {source_name} 的 {len(ids_to_delete)} 个文档块")

                # 强制持久化
                if hasattr(self.chroma, 'persist'):
                    self.chroma.persist()

                self.doc_count = self.chroma._collection.count()
                return len(ids_to_delete)
            return 0
        except Exception as e:
            logger.error(f"删除源文件失败: {source_name}, 错误: {e}")
            return 0

    def clear_all_documents(self) -> bool:
        """清空所有文档（同时删除MD5文件）"""
        try:
            # 1. 删除整个集合
            self.chroma.delete_collection()
            logger.info("✅ Chroma集合已删除")

            # 2. 重新创建集合
            self.chroma = Chroma.from_documents(
                documents=[],
                embedding=self.embeddings,
                collection_name=collection_name,
                persist_directory=persist_directory,
            )
            logger.info("✅ 已重新创建空集合")

            # 3. 彻底删除MD5文件
            if os.path.exists(md5_path):
                os.remove(md5_path)
                logger.info(f"✅ MD5文件已删除: {md5_path}")
            else:
                logger.info("MD5文件不存在，无需删除")

            # 4. 确保目录存在（重新创建空的MD5文件）
            os.makedirs(os.path.dirname(md5_path), exist_ok=True)
            with open(md5_path, 'w', encoding='utf-8') as f:
                f.write('')  # 创建空文件
            logger.info("✅ 已创建空MD5文件")

            self.doc_count = 0
            logger.warning("⚠️ 已清空所有文档和MD5记录")
            return True

        except Exception as e:
            logger.error(f"清空文档失败: {e}")
            return False

    @log_performance("INFO")
    def upload_file(self, file_path: Union[str, Path], original_filename: Optional[str] = None, force: bool = False) -> str:
        """
        上传文件（支持多模态）
        :param file_path: 文件路径（临时文件）
        :param original_filename: 原始文件名（用户上传时的名字）
        :param force: 是否强制上传（忽略MD5检查）
        """
        file_path = Path(file_path)
        display_name = original_filename or file_path.name  # 优先使用原始文件名
        logger.info(f"开始上传文件: {display_name}")

        # 计算MD5（基于文件内容，不是文件名）
        file_md5 = self.get_file_md5(file_path)

        # 如果不是强制上传，检查MD5
        if not force and self.check_md5(file_md5):
            logger.info(f"文件已存在，跳过: {display_name}")
            return f"[跳过]文件已存在知识库中"

        try:
            # 使用多模态处理器加载文档
            docs = self.multimodal_loader.load(file_path)

            if not docs:
                return f"[失败]无法解析文件: {display_name}"

            # 分割文档
            all_chunks = []
            texts = []
            metadatas = []

            for doc in docs:
                # 修改metadata中的source为原始文件名
                if doc.metadata:
                    doc.metadata['source'] = display_name
                    # 同时保存原始路径（可选）
                    doc.metadata['original_path'] = str(file_path)

                if doc.page_content and len(doc.page_content) > max_split_char_number:
                    chunks = self.spliter.split_text(doc.page_content)
                    for chunk in chunks:
                        new_doc = type(doc)(
                            page_content=chunk,
                            metadata=doc.metadata.copy() if doc.metadata else {}
                        )
                        all_chunks.append(new_doc)
                        texts.append(chunk)
                        metadatas.append(new_doc.metadata)
                else:
                    all_chunks.append(doc)
                    texts.append(doc.page_content)
                    metadatas.append(doc.metadata)

            logger.info(f"生成 {len(all_chunks)} 个文档块")

            # 添加到向量库
            self.chroma.add_texts(texts, metadatas=metadatas)

            # 强制持久化
            if hasattr(self.chroma, 'persist'):
                self.chroma.persist()

            # 保存MD5（如果是强制上传，也保存新的MD5）
            self.save_md5(file_md5)

            self.doc_count = self.chroma._collection.count()
            logger.info(f"上传成功: {display_name}, 当前总文档数: {self.doc_count}")

            # ===== 新增：更新 BM25 索引 =====
            try:
                # 获取新上传的文档
                from langchain_core.documents import Document
                new_docs = []
                for chunk_text, metadata in zip(texts, metadatas):
                    doc = Document(page_content=chunk_text, metadata=metadata)
                    new_docs.append(doc)

                # 更新 BM25 索引
                from core.vector_stores import VectorStoreService
                vector_service = VectorStoreService(self.embeddings)
                vector_service.update_bm25_index(new_docs)
                logger.info(f"✅ BM25 索引已更新，新增 {len(new_docs)} 个文档")
            except Exception as e:
                logger.error(f"更新 BM25 索引失败: {e}")
            # ===== 新增结束 =====

            return f"[成功]文件已载入知识库 (生成{len(all_chunks)}个块，当前共{self.doc_count}个文档)"

        except Exception as e:
            logger.error(f"上传失败: {display_name}, 错误: {e}", exc_info=True)
            return f"[失败]上传出错: {str(e)}"

    def upload_by_str(self, data: str, filename: str) -> str:
        """原有方法，保持兼容"""
        logger.info(f"开始上传文本: {filename}")

        md5_hex = hashlib.md5(data.encode()).hexdigest()

        if self.check_md5(md5_hex):
            logger.info(f"内容已存在，跳过: {filename}")
            return "[跳过]内容已经存在知识库中"

        if len(data) > max_split_char_number:
            knowledge_chunks = self.spliter.split_text(data)
        else:
            knowledge_chunks = [data]

        metadata = {
            "source": filename,
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "operator": "小曹",
        }

        texts = knowledge_chunks
        metadatas = [metadata for _ in knowledge_chunks]

        try:
            self.chroma.add_texts(
                texts,
                metadatas=metadatas,
            )

            self.save_md5(md5_hex)

            if hasattr(self.chroma, 'persist'):
                self.chroma.persist()

            self.doc_count = self.chroma._collection.count()
            logger.info(f"上传成功: {filename}, 当前总文档数: {self.doc_count}")

            # ===== 新增：更新 BM25 索引 =====
            try:
                # 获取新上传的文档
                from langchain_core.documents import Document
                new_docs = []
                for chunk_text, metadata in zip(texts, metadatas):
                    doc = Document(page_content=chunk_text, metadata=metadata)
                    new_docs.append(doc)

                # 更新 BM25 索引
                from core.vector_stores import VectorStoreService
                vector_service = VectorStoreService(self.embeddings)
                vector_service.update_bm25_index(new_docs)
                logger.info(f"✅ BM25 索引已更新，新增 {len(new_docs)} 个文档")
            except Exception as e:
                logger.error(f"更新 BM25 索引失败: {e}")
            # ===== 新增结束 =====

            return f"[成功]内容已载入向量库 (当前共{self.doc_count}个文档)"

        except Exception as e:
            logger.error(f"上传失败: {filename}, 错误: {e}")
            return f"[失败]上传出错: {str(e)}"