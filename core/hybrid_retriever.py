"""
混合检索器
功能：结合向量检索（语义）和 BM25 检索（关键词）
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_chroma import Chroma
from rank_bm25 import BM25Okapi
from pydantic import Field

from config.config_data import *
from utils.logger import logger


class BM25Retriever:
    """
    BM25 关键词检索器
    基于词频统计，擅长精确匹配
    """
    def __init__(self, index_path: str = "data/bm25_index.pkl"):
        self.index_path = index_path
        self.bm25 = None
        self.documents = []
        self.corpus = []

    def add_documents(self, documents: List[Document]):
        """添加文档到 BM25 索引"""
        if not documents:
            return

        # 提取文本内容
        self.documents = documents
        self.corpus = [doc.page_content for doc in documents]

        # 分词（简单按空格分词，中文需要额外处理）
        tokenized_corpus = [self._tokenize(doc) for doc in self.corpus]

        # 创建 BM25 索引
        self.bm25 = BM25Okapi(tokenized_corpus)

        # 保存索引到文件
        self._save_index()
        logger.info(f"✅ BM25 索引已更新，共 {len(documents)} 个文档")

    def _tokenize(self, text: str) -> List[str]:
        """
        分词函数
        中文：按字分词（简单版）
        英文：按空格分词
        """
        import re
        # 匹配中文（汉字）和英文单词
        tokens = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z0-9]+', text)
        return [t.lower() for t in tokens]

    def get_relevant_documents(self, query: str, k: int = 5) -> List[Document]:
        """检索相关文档"""
        if not self.bm25:
            logger.warning("BM25 索引为空")
            return []

        # 查询分词
        tokenized_query = self._tokenize(query)

        # 计算 BM25 分数
        scores = self.bm25.get_scores(tokenized_query)

        # 获取 top-k 索引
        top_indices = np.argsort(scores)[-k:][::-1]

        # 返回文档
        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # 只返回有分数的结果
                doc = self.documents[idx]
                # 添加分数到 metadata
                doc.metadata['bm25_score'] = float(scores[idx])
                results.append(doc)

        return results

    def _save_index(self):
        """保存 BM25 索引到文件"""
        try:
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
            with open(self.index_path, 'wb') as f:
                pickle.dump({
                    'documents': self.documents,
                    'corpus': self.corpus,
                    'bm25': self.bm25
                }, f)
            logger.debug(f"BM25 索引已保存: {self.index_path}")
        except Exception as e:
            logger.error(f"保存 BM25 索引失败: {e}")

    def load_index(self) -> bool:
        """从文件加载 BM25 索引"""
        if not os.path.exists(self.index_path):
            return False

        try:
            with open(self.index_path, 'rb') as f:
                data = pickle.load(f)
                self.documents = data['documents']
                self.corpus = data['corpus']
                self.bm25 = data['bm25']
            logger.info(f"✅ BM25 索引已加载: {self.index_path}")
            return True
        except Exception as e:
            logger.error(f"加载 BM25 索引失败: {e}")
            return False


class HybridRetriever(BaseRetriever):
    """
    混合检索器
    结合向量检索（语义）和 BM25 检索（关键词）
    """

    # 使用 Pydantic Field 定义字段
    vector_retriever: Any = Field(description="向量检索器实例")
    bm25_retriever: Any = Field(description="BM25检索器实例")
    vector_weight: float = Field(default=0.7, description="向量检索权重")
    bm25_weight: float = Field(default=0.3, description="BM25检索权重")
    k: int = Field(default=5, description="返回文档数量")

    class Config:
        """Pydantic 配置"""
        arbitrary_types_allowed = True

    def __init__(
        self,
        vector_retriever,
        bm25_retriever: BM25Retriever,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        k: int = 5
    ):
        """
        初始化混合检索器
        :param vector_retriever: 向量检索器
        :param bm25_retriever: BM25检索器
        :param vector_weight: 向量检索权重
        :param bm25_weight: BM25检索权重
        :param k: 返回文档数量
        """
        # 调用父类初始化，传入所有字段
        super().__init__(
            vector_retriever=vector_retriever,
            bm25_retriever=bm25_retriever,
            vector_weight=vector_weight,
            bm25_weight=bm25_weight,
            k=k
        )
        logger.info(f"✅ 混合检索器初始化完成 (向量{vector_weight} + BM25{bm25_weight})")

    def _get_relevant_documents(self, query: str, **kwargs) -> List[Document]:
        """
        检索相关文档（混合检索）
        """
        # 1. 向量检索（语义）
        vector_docs = self.vector_retriever.get_relevant_documents(query, k=self.k*2)

        # 2. BM25 检索（关键词）
        bm25_docs = self.bm25_retriever.get_relevant_documents(query, k=self.k*2)

        # 3. 合并结果并去重
        all_docs = {}

        # 处理向量检索结果
        for i, doc in enumerate(vector_docs):
            # 生成唯一ID（基于内容和元数据）
            doc_id = doc.page_content[:50] + str(doc.metadata.get('source', ''))
            # 向量分数（基于位置衰减）
            score = self.vector_weight * (1.0 - i / len(vector_docs)) if vector_docs else 0
            if doc_id in all_docs:
                all_docs[doc_id]['score'] += score
            else:
                all_docs[doc_id] = {
                    'doc': doc,
                    'score': score
                }

        # 处理 BM25 检索结果
        for i, doc in enumerate(bm25_docs):
            doc_id = doc.page_content[:50] + str(doc.metadata.get('source', ''))
            bm25_score = doc.metadata.get('bm25_score', 1.0)
            # BM25 分数（基于实际分数）
            score = self.bm25_weight * bm25_score
            if doc_id in all_docs:
                all_docs[doc_id]['score'] += score
            else:
                all_docs[doc_id] = {
                    'doc': doc,
                    'score': score
                }

        # 4. 按总分排序
        sorted_items = sorted(
            all_docs.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )[:self.k]

        # 5. 返回文档
        results = [item[1]['doc'] for item in sorted_items]

        logger.debug(f"混合检索: 向量{len(vector_docs)}个, BM25{len(bm25_docs)}个, 合并后{len(results)}个")

        return results

    async def _aget_relevant_documents(self, query: str, **kwargs) -> List[Document]:
        """异步检索（暂不支持）"""
        return self._get_relevant_documents(query, **kwargs)