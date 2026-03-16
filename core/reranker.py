"""
重排序器
功能：对检索结果进行重新排序，提高相关性
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from typing import List, Dict, Any, Optional
import numpy as np
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder
import torch

from utils.logger import logger


class Reranker:
    """
    重排序器
    使用交叉编码器对检索结果重新打分
    """

    def __init__(self, model_name: str = "BAAI/bge-reranker-base", device: Optional[str] = None):
        """
        初始化重排序器
        :param model_name: 重排序模型名称
        :param device: 运行设备 (cuda/cpu)
        """
        self.model_name = model_name
        self.model = None
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')

        logger.info(f"正在加载重排序模型: {model_name} (设备: {self.device})")
        try:
            self.model = CrossEncoder(model_name, device=self.device)
            logger.info(f"✅ 重排序模型加载成功")
        except Exception as e:
            logger.error(f"❌ 重排序模型加载失败: {e}")
            raise

    def rerank(
            self,
            query: str,
            documents: List[Document],
            top_k: Optional[int] = None,
            return_scores: bool = False
    ) -> List[Document]:
        """
        对文档进行重排序
        :param query: 查询字符串
        :param documents: 待排序的文档列表
        :param top_k: 返回前k个结果，默认返回全部
        :param return_scores: 是否在metadata中返回分数
        :return: 重排序后的文档列表
        """
        if not documents:
            return []

        if not self.model:
            logger.warning("重排序模型未加载，返回原始顺序")
            return documents

        # 准备输入对 (query, document_content)
        pairs = [(query, doc.page_content) for doc in documents]

        # 计算分数
        try:
            scores = self.model.predict(pairs)

            # 将分数归一化到0-1之间
            scores = self._normalize_scores(scores)

            # 创建 (score, index) 对并排序
            scored_indices = [(scores[i], i) for i in range(len(documents))]
            scored_indices.sort(key=lambda x: x[0], reverse=True)

            # 重新排序文档
            reranked_docs = []
            for score, idx in scored_indices:
                doc = documents[idx]
                if return_scores:
                    # 保存重排序分数
                    if doc.metadata is None:
                        doc.metadata = {}
                    doc.metadata['rerank_score'] = float(score)
                reranked_docs.append(doc)

            # 截取 top_k
            if top_k:
                reranked_docs = reranked_docs[:top_k]

            logger.debug(f"重排序完成: {len(documents)}个文档 -> 返回{len(reranked_docs)}个")
            return reranked_docs

        except Exception as e:
            logger.error(f"重排序失败: {e}")
            return documents[:top_k] if top_k else documents

    def _normalize_scores(self, scores: np.ndarray) -> np.ndarray:
        """将分数归一化到0-1之间"""
        min_score = scores.min()
        max_score = scores.max()
        if max_score - min_score > 1e-6:
            return (scores - min_score) / (max_score - min_score)
        return scores

    def batch_rerank(
            self,
            queries: List[str],
            documents_batch: List[List[Document]],
            top_k: Optional[int] = None
    ) -> List[List[Document]]:
        """
        批量重排序
        :param queries: 查询列表
        :param documents_batch: 文档列表的列表
        :param top_k: 返回前k个结果
        :return: 重排序后的文档列表的列表
        """
        results = []
        for query, docs in zip(queries, documents_batch):
            results.append(self.rerank(query, docs, top_k))
        return results


# ========== 轻量版重排序器（使用相似度计算）==========
class SimilarityReranker:
    """
    轻量版重排序器
    使用向量相似度进行重排序（不需要额外模型）
    """

    def __init__(self, embeddings_model):
        """
        初始化
        :param embeddings_model: 向量化模型
        """
        self.embeddings_model = embeddings_model
        logger.info("✅ 相似度重排序器初始化完成")

    def rerank(
            self,
            query: str,
            documents: List[Document],
            top_k: Optional[int] = None,
            return_scores: bool = False
    ) -> List[Document]:
        """
        使用向量相似度重排序
        """
        if not documents:
            return []

        # 计算查询向量
        query_embedding = self.embeddings_model.embed_query(query)

        # 计算文档向量
        doc_texts = [doc.page_content for doc in documents]
        doc_embeddings = self.embeddings_model.embed_documents(doc_texts)

        # 计算相似度
        scores = []
        for doc_emb in doc_embeddings:
            # 余弦相似度
            similarity = np.dot(query_embedding, doc_emb) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(doc_emb) + 1e-6
            )
            scores.append(similarity)

        # 排序
        scored_indices = [(scores[i], i) for i in range(len(documents))]
        scored_indices.sort(key=lambda x: x[0], reverse=True)

        # 重新排序文档
        reranked_docs = []
        for score, idx in scored_indices:
            doc = documents[idx]
            if return_scores:
                if doc.metadata is None:
                    doc.metadata = {}
                doc.metadata['similarity_score'] = float(score)
            reranked_docs.append(doc)

        if top_k:
            reranked_docs = reranked_docs[:top_k]

        return reranked_docs