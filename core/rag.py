"""
RAG核心流程
功能：串联整个问答流程，支持混合检索、重排序和查询优化，专为赛尔号Xin服攻略优化
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import time
import hashlib
from typing import List, Dict, Any, Optional

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableWithMessageHistory, RunnableLambda
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.chat_models.tongyi import ChatTongyi

from history.file_history_store import get_history
from core.vector_stores import VectorStoreService
from core.reranker import Reranker, SimilarityReranker
from core.query_optimizer import QueryOptimizer, with_query_optimization
from config.config_data import *
from utils.logger import logger, log_performance, log_qa_interaction
from utils.cache import cache_manager


class RagService:
    """
    RAG核心服务
    整合检索、重排序、生成，专为赛尔号Xin服攻略优化
    """

    def __init__(self):
        logger.info("初始化 RagService（赛尔号Xin服攻略版）")

        # 初始化嵌入模型
        self.embeddings = DashScopeEmbeddings(
            model=embedding_model_name,
            dashscope_api_key=DASHSCOPE_API_KEY
        )

        # 初始化向量存储服务
        self.vector_service = VectorStoreService(
            embedding=self.embeddings
        )

        # 初始化重排序器
        self.use_reranker = USE_RERANKER
        if self.use_reranker:
            try:
                self.reranker = Reranker(
                    model_name=RERANKER_MODEL
                )
                logger.info(f"✅ 重排序器初始化成功，模型: {RERANKER_MODEL}")
            except Exception as e:
                logger.warning(f"⚠️ 重排序器初始化失败，使用相似度重排序: {e}")
                self.reranker = SimilarityReranker(self.embeddings)
        else:
            self.reranker = None
            logger.info("重排序器未启用")

        # 初始化查询优化器
        self.use_query_optimization = USE_QUERY_OPTIMIZATION
        self.use_hyde = USE_HYDE

        if self.use_query_optimization:
            self.query_optimizer = QueryOptimizer(
                use_hyde=self.use_hyde,
                llm=self.chat_model if self.use_hyde else None
            )
            logger.info(f"✅ 查询优化器已启用 (HyDE={'开启' if self.use_hyde else '关闭'})")
        else:
            self.query_optimizer = None
            logger.info("查询优化器未启用")

        # 赛尔号Xin服攻略专用提示词
        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", """你是一个专业的赛尔号Xin服游戏攻略助手，专注于帮助新手玩家快速上手游戏。

【身份设定】
- 你是Xin服资深玩家，熟悉游戏机制和最新更新（攻略更新至5.13）
- 你的回答要热情、耐心，像在指导一个刚入坑的朋友
- 对游戏术语和梗要熟悉，但解释时要通俗易懂

【核心规则】
1. **必须严格基于提供的攻略文档回答**，不要编造攻略内容
2. 如果文档中没有相关信息，请说："这个在目前的攻略文档里还没有收录，建议去群里问问老玩家"
3. 回答要结构清晰，重要信息用**加粗**标注
4. 涉及具体数值（如血量、等级、概率）要准确引用攻略中的数据
5. 对于复杂的攻略，可以分步骤说明

【游戏特色提醒】
⚠️ **重要提醒**：Xin服是公益服，目前没有任何付费内容！如果有人找你众筹、收费，一定是骗子，千万不要相信！

🎮 **游戏机制特点**：
- 前4小时野怪才有掉落物，挑战获取双倍经验
- 电池时常为每日12小时，半夜可能重启服务器
- 超能nono可以解锁特殊场景和功能
- 融合、捕捉稀有精灵都有特殊机制

【常见问题回答框架】
📌 **精灵获取**：先说在哪里抓 → 捕捉技巧（血量、状态） → 培养建议
📌 **塔类攻略**：先分析怪物机制 → 推荐阵容 → 分步骤打法 → 注意事项
📌 **BOSS打法**：先分析BOSS机制 → 推荐精灵 → 具体打法步骤
📌 **游戏机制**：先解释是什么 → 怎么用 → 注意事项

【参考资料】
{context}

【对话历史】
"""),
                MessagesPlaceholder("history"),
                ("user", "【用户问题】\n{input}")
            ]
        )

        # 初始化大模型
        self.chat_model = ChatTongyi(
            model=chat_model_name,
            dashscope_api_key=DASHSCOPE_API_KEY
        )

        # 构建执行链
        self.chain = self._build_chain()
        logger.info("RagService 初始化完成")

    def _build_chain(self):
        """
        构建RAG执行链
        """
        def format_document(docs: List[Document]) -> str:
            """格式化文档为字符串"""
            logger.debug(f"检索到 {len(docs)} 个相关攻略文档")

            if not docs:
                logger.warning("未检索到相关攻略")
                return "【当前暂无相关攻略内容】"

            for i, doc in enumerate(docs):
                logger.debug(f"攻略 {i+1}: {doc.page_content[:100]}... 来源: {doc.metadata.get('source', '未知')}")

            formatted_str = "【以下是赛尔号Xin服攻略库中的相关内容】\n\n"
            for i, doc in enumerate(docs):
                # 提取文件名作为攻略名称
                source = doc.metadata.get('source', '未知攻略')
                if '\\' in source:
                    source = source.split('\\')[-1]
                elif '/' in source:
                    source = source.split('/')[-1]

                formatted_str += f"📖 **攻略 {i+1}：《{source}》**\n"
                formatted_str += f"```\n{doc.page_content}\n```\n"

                if 'rerank_score' in doc.metadata:
                    formatted_str += f"相关性：{doc.metadata['rerank_score']:.3f}\n"
                formatted_str += "\n---\n\n"

            return formatted_str

        def retrieve_and_rerank(value: Dict) -> List[Document]:
            """
            检索并重排序攻略文档
            :param value: 包含input的字典
            :return: 重排序后的文档列表
            """
            query = value["input"]

            # 1. 获取检索器
            retriever = self.vector_service.get_retriever()

            # 2. 检索攻略文档
            initial_k = RERANKER_INITIAL_K
            logger.debug(f"初始检索攻略数量: {initial_k}")

            # 兼容新旧版本 LangChain
            try:
                docs = retriever.invoke(query)
            except AttributeError:
                try:
                    docs = retriever.get_relevant_documents(query)
                except AttributeError:
                    if hasattr(retriever, '__call__'):
                        docs = retriever(query)
                    else:
                        docs = []

            logger.info(f"初始检索到 {len(docs)} 篇相关攻略")

            # 3. 重排序
            if self.reranker and docs:
                top_k = RERANKER_TOP_K
                docs = self.reranker.rerank(query, docs, top_k=top_k, return_scores=True)
                logger.info(f"重排序完成，精选 {len(docs)} 篇最相关攻略")

                # 打印重排序后的分数
                for i, doc in enumerate(docs):
                    score = doc.metadata.get('rerank_score', 0)
                    source = doc.metadata.get('source', '未知')
                    if '\\' in source:
                        source = source.split('\\')[-1]
                    elif '/' in source:
                        source = source.split('/')[-1]
                    logger.debug(f"攻略 {i+1}: {source} 相关性={score:.3f}")

            return docs

        def prepare_prompt_input(value: Dict) -> Dict:
            """准备提示词输入"""
            new_value = {
                "input": value["input"]["input"],
                "context": value["context"],
                "history": value["input"]["history"]
            }

            logger.info(f"玩家提问: {new_value['input']}")
            logger.debug(f"攻略上下文长度: {len(new_value['context'])} 字符")
            logger.debug(f"对话历史: {len(new_value['history'])} 条")

            return new_value

        # 构建链
        chain = (
            {
                "input": RunnablePassthrough(),
                "context": RunnableLambda(retrieve_and_rerank) | format_document
            }
            | RunnableLambda(prepare_prompt_input)
            | self.prompt_template
            | self.chat_model
            | StrOutputParser()
        )

        # 添加历史记录支持
        conversation_chain = RunnableWithMessageHistory(
            chain,
            get_history,
            input_messages_key="input",
            history_messages_key="history",
        )

        return conversation_chain

    def _get_cache_key(self, username: str, question: str) -> str:
        """生成缓存键"""
        key_str = f"{username}:{question}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _guess_question_type(self, question: str) -> str:
        """猜测问题类型（精灵/塔/BOSS/机制）"""
        question_lower = question.lower()

        keywords = {
            "精灵": ["精灵", "怎么抓", "捕捉", "获得", "培养", "性格", "学习力", "技能"],
            "塔": ["塔", "爬塔", "勇者之塔", "试炼之塔", "层"],
            "BOSS": ["boss", "spt", "怎么打", "击败", "攻略"],
            "机制": ["融合", "孵化", "特性", "异色", "闪光", "个体", "怎么玩"]
        }

        for qtype, words in keywords.items():
            if any(word in question_lower for word in words):
                return qtype
        return "综合"

    @with_query_optimization
    @log_performance("INFO")
    def chat(self, username: str, question: str, session_config: Dict) -> str:
        """
        聊天方法（带缓存和查询优化）
        :param username: 用户名
        :param question: 问题
        :param session_config: 会话配置
        :return: 攻略回答
        """
        start_time = time.time()

        # 猜测问题类型（这里已经是优化后的查询）
        q_type = self._guess_question_type(question)
        logger.info(f"玩家 {username} 提问 [{q_type}类型]: {question}")

        # 尝试从缓存获取
        cache_key = self._get_cache_key(username, question)
        cached_answer = cache_manager.cache.get(cache_key)

        if cached_answer:
            logger.info(f"✅ 攻略缓存命中: {username} - {question[:30]}...")
            duration = time.time() - start_time

            log_qa_interaction(
                username=username,
                question=question,
                answer=cached_answer,
                duration=duration,
                cached=True
            )
            return cached_answer

        logger.info(f"攻略缓存未命中，正在检索攻略库: {username} - {question[:30]}...")

        try:
            # 调用 RAG 链
            result = self.chain.invoke(
                {"input": question},
                session_config
            )

            duration = time.time() - start_time

            # 存入缓存（1小时）
            cache_manager.cache.set(cache_key, result, 3600)

            log_qa_interaction(
                username=username,
                question=question,
                answer=result,
                duration=duration,
                cached=False
            )

            logger.info(f"✅ 攻略回答完成，耗时: {duration:.2f}秒，已缓存")
            return result

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ 攻略回答失败: {e}, 耗时: {duration:.2f}秒")
            raise

    def clear_user_cache(self, username: str) -> int:
        """清除用户的缓存"""
        pattern = f"*{username}*"
        count = cache_manager.clear_cache(pattern)
        logger.info(f"已清除用户 {username} 的 {count} 个攻略缓存")
        return count


# ========== 测试代码 ==========
if __name__ == '__main__':
    # 测试配置
    test_session_config = {
        "configurable": {
            "session_id": "test_user_001",
        }
    }

    # 初始化服务
    service = RagService()

    # 测试攻略问答
    test_questions = [
        "雷伊怎么获得？",
        "85层紫毛怎么打？",
        "嘟咕噜王值得练吗？",
        "融合精灵怎么玩？",
        "新手推荐什么精灵？"
    ]

    for q in test_questions:
        print(f"\n{'='*50}")
        print(f"玩家提问: {q}")
        try:
            res = service.chat("test_user", q, test_session_config)
            print(f"攻略回答:\n{res}")
        except Exception as e:
            print(f"错误: {e}")