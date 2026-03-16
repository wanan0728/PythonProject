"""
向量存储服务（支持混合检索）
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from langchain_chroma import Chroma
from config.config_data import *
from utils.logger import logger
from core.hybrid_retriever import HybridRetriever, BM25Retriever


class VectorStoreService(object):
    def __init__(self, embedding):
        """
        :param embedding: 嵌入模型的传入
        """
        self.embedding = embedding
        self._vector_store = None
        self.bm25_retriever = BM25Retriever()
        self.hybrid_retriever = None

        # 尝试加载 BM25 索引
        self.bm25_retriever.load_index()

    @property
    def vector_store(self):
        """懒加载 vector_store"""
        if self._vector_store is None:
            self._vector_store = Chroma(
                collection_name=collection_name,
                embedding_function=self.embedding,
                persist_directory=persist_directory,
            )
        return self._vector_store

    def get_retriever(self, search_kwargs: dict = None):
        """获取检索器（默认返回混合检索器）"""
        if search_kwargs is None:
            search_kwargs = {"k": similarity_threshold}

        k = search_kwargs.get("k", similarity_threshold)

        # 获取向量检索器
        vector_retriever = self.vector_store.as_retriever(search_kwargs=search_kwargs)

        # 创建混合检索器
        self.hybrid_retriever = HybridRetriever(
            vector_retriever=vector_retriever,
            bm25_retriever=self.bm25_retriever,
            vector_weight=0.7,  # 向量检索权重70%
            bm25_weight=0.3,  # BM25 权重30%
            k=k
        )

        return self.hybrid_retriever

    def update_bm25_index(self, documents=None):
        """更新 BM25 索引"""
        if documents is None:
            # 从向量库获取所有文档
            all_docs = self.vector_store.get()
            from langchain_core.documents import Document
            documents = []
            for i, (content, metadata) in enumerate(zip(all_docs['documents'], all_docs['metadatas'])):
                doc = Document(page_content=content, metadata=metadata)
                documents.append(doc)

        self.bm25_retriever.add_documents(documents)
        logger.info(f"✅ BM25 索引已更新，共 {len(documents)} 个文档")


if __name__ == '__main__':
    from langchain_community.embeddings import DashScopeEmbeddings

    service = VectorStoreService(DashScopeEmbeddings(model="text-embedding-v4"))

    # 测试检索
    retriever = service.get_retriever()
    res = retriever.invoke("我的体重180斤，尺码推荐")
    print(f"检索到 {len(res)} 个结果")
    for i, doc in enumerate(res):
        print(f"\n--- 结果 {i + 1} ---")
        print(f"内容: {doc.page_content[:100]}...")
        print(f"分数: {doc.metadata.get('bm25_score', 'N/A')}")