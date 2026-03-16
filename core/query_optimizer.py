"""
查询优化器
功能：对用户问题进行改写、拆分、扩展，提高检索效果
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import re
import hashlib
from typing import List, Dict, Any, Optional, Tuple
import nltk
from nltk.tokenize import sent_tokenize

from utils.logger import logger

# 下载必要的NLTK数据
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')


class QueryOptimizer:
    """
    查询优化器
    功能：
    1. 问题改写（Query Rewrite）：将口语化问题转为标准形式
    2. 子查询拆分（Query Decomposition）：复杂问题拆分成多个子问题
    3. 假设性文档嵌入（HyDE）：生成假答案用于检索
    """

    def __init__(self, use_hyde: bool = False, llm=None):
        """
        初始化查询优化器
        :param use_hyde: 是否使用HyDE（需要传入llm）
        :param llm: 大语言模型实例（用于HyDE）
        """
        self.use_hyde = use_hyde
        self.llm = llm

        # 赛尔号Xin服关键词库
        self.game_keywords = {
            "精灵": ["雷伊", "盖亚", "哈莫雷特", "嘟咕噜王", "丽莎布布", "魔焰猩猩", "鲁斯王"],
            "地点": ["赫尔卡星", "海洋星", "火山星", "云霄星", "克洛斯星", "双子阿尔法星"],
            "机制": ["融合", "捕捉", "孵化", "个体", "性格", "学习力", "特性", "异色"],
            "塔类": ["勇者之塔", "试炼之塔", "爬塔"],
            "BOSS": ["spt", "尤纳斯", "魔狮迪露", "哈莫雷特", "盖亚", "雷伊"]
        }

        # 口语化映射表
        self.slang_map = {
            "咋整": "怎么获得",
            "咋弄": "怎么获得",
            "咋得": "怎么获得",
            "咋抓": "怎么捕捉",
            "咋打": "怎么击败",
            "咋过": "怎么通关",
            "咋玩": "怎么玩",
            "好不好": "值得练吗",
            "行不行": "值得练吗",
            "强不强": "强度如何",
            "有啥用": "有什么用",
            "啥性格": "推荐什么性格",
            "刷啥": "刷什么学习力"
        }

        logger.info("✅ 查询优化器初始化完成")

    def optimize(self, query: str) -> Dict[str, Any]:
        """
        主优化方法：对查询进行全面优化
        :param query: 原始查询
        :return: 优化后的查询信息
        """
        original = query.strip()

        # 1. 问题改写
        rewritten = self.rewrite_query(original)

        # 2. 问题类型识别
        query_type = self._identify_query_type(original)

        # 3. 关键词提取
        keywords = self._extract_keywords(original)

        # 4. 子查询拆分（如果是复杂问题）
        sub_queries = self.decompose_query(original) if self._is_complex_query(original) else []

        # 5. HyDE（如果启用）
        hyde_doc = None
        if self.use_hyde and self.llm:
            hyde_doc = self.generate_hyde(original)

        result = {
            "original": original,
            "rewritten": rewritten,
            "query_type": query_type,
            "keywords": keywords,
            "sub_queries": sub_queries,
            "hyde_doc": hyde_doc,
            "is_complex": len(sub_queries) > 0
        }

        logger.debug(f"查询优化结果: 类型={query_type}, 改写='{rewritten}', 子查询={len(sub_queries)}个")
        return result

    def rewrite_query(self, query: str) -> str:
        """
        问题改写：将口语化问题转为标准形式
        """
        rewritten = query

        # 1. 替换口语化表达
        for slang, standard in self.slang_map.items():
            if slang in rewritten:
                rewritten = rewritten.replace(slang, standard)

        # 2. 去除多余语气词
        tone_words = ["啊", "呀", "哦", "呢", "吧", "吗", "哈", "嘿"]
        for word in tone_words:
            rewritten = rewritten.replace(word, "")

        # 3. 补全缺失的主语
        if rewritten.startswith("怎么") and not any(kw in rewritten for kw in ["精灵", "BOSS", "塔"]):
            # 尝试从关键词中推断主语
            for category, keywords in self.game_keywords.items():
                for kw in keywords:
                    if kw in query:
                        rewritten = rewritten.replace("怎么", f"{kw}怎么")
                        break

        # 4. 规范化标点
        rewritten = re.sub(r'[？?]+$', '', rewritten)  # 去掉末尾问号
        rewritten = re.sub(r'\s+', ' ', rewritten)  # 合并多余空格

        return rewritten.strip()

    def decompose_query(self, query: str) -> List[str]:
        """
        子查询拆分：将复杂问题拆分成多个简单子问题
        """
        sub_queries = []

        # 1. 按连接词拆分
        conjunctions = ["和", "与", "及", "并", "以及", "、", ",", "，"]
        for conj in conjunctions:
            if conj in query:
                parts = query.split(conj)
                if len(parts) > 1:
                    for part in parts:
                        cleaned = part.strip()
                        if cleaned and len(cleaned) > 2:
                            # 确保每个部分都形成完整的问题
                            if not any(q in cleaned for q in ["怎么", "如何", "什么", "多少"]):
                                cleaned = f"{cleaned}怎么获得"
                            sub_queries.append(cleaned)
                    break

        # 2. 如果没有连接词，但包含多个疑问词
        if not sub_queries:
            question_words = ["怎么", "如何", "什么", "多少", "哪里", "哪个"]
            found_words = [w for w in question_words if w in query]
            if len(found_words) > 1:
                # 按句子拆分
                sentences = sent_tokenize(query)
                if len(sentences) > 1:
                    sub_queries = sentences

        return sub_queries

    def generate_hyde(self, query: str) -> str:
        """
        生成假设性文档（HyDE）
        先让LLM生成一个假答案，用假答案去检索
        """
        if not self.llm:
            return None

        hyde_prompt = f"""
        你是一个赛尔号Xin服游戏攻略专家。请基于你对游戏的了解，针对以下问题生成一个可能的攻略回答。
        这个回答不需要完全准确，只需要包含可能的关键词和相关信息，用于检索真实攻略。

        问题：{query}

        请生成一个假设性的攻略回答（50-100字）：
        """

        try:
            # 这里调用LLM生成假答案
            # 实际使用时需要接入具体的LLM
            hyde_answer = f"关于{query}的攻略信息，包括相关精灵、地点、机制等。"
            logger.debug(f"HyDE生成: {hyde_answer[:50]}...")
            return hyde_answer
        except Exception as e:
            logger.error(f"HyDE生成失败: {e}")
            return None

    def _identify_query_type(self, query: str) -> str:
        """识别问题类型"""
        for qtype, keywords in self.game_keywords.items():
            for kw in keywords:
                if kw in query:
                    return qtype

        # 根据疑问词判断
        if any(w in query for w in ["怎么", "如何", "怎样"]):
            if "抓" in query or "捕捉" in query:
                return "捕捉"
            elif "打" in query or "击败" in query:
                return "战斗"
            elif "得" in query or "获得" in query:
                return "获取"
            elif "刷" in query:
                return "培养"

        return "综合"

    def _extract_keywords(self, query: str) -> List[str]:
        """提取关键词"""
        keywords = []

        # 从游戏关键词库中提取
        for category, kw_list in self.game_keywords.items():
            for kw in kw_list:
                if kw in query:
                    keywords.append(kw)

        # 提取数字（层数、等级等）
        numbers = re.findall(r'\d+', query)
        keywords.extend([f"第{num}层" for num in numbers])

        return list(set(keywords))

    def _is_complex_query(self, query: str) -> bool:
        """判断是否是复杂问题"""
        # 包含多个连接词
        conjunctions = ["和", "与", "及", "并", "以及"]
        if sum(1 for conj in conjunctions if conj in query) > 1:
            return True

        # 包含多个疑问词
        question_words = ["怎么", "如何", "什么", "多少", "哪里"]
        if sum(1 for qw in question_words if qw in query) > 1:
            return True

        # 长度超过20个字
        if len(query) > 20:
            return True

        return False


# ========== 查询优化装饰器 ==========
def with_query_optimization(func):
    """
    查询优化装饰器
    自动对输入查询进行优化
    """

    def wrapper(self, username: str, question: str, session_config: Dict, *args, **kwargs):
        # 初始化优化器（如果没有的话）
        if not hasattr(self, 'query_optimizer'):
            self.query_optimizer = QueryOptimizer(
                use_hyde=getattr(self, 'use_hyde', False),
                llm=getattr(self, 'chat_model', None)
            )

        # 优化查询
        optimized = self.query_optimizer.optimize(question)

        # 记录优化信息
        logger.info(f"查询优化: '{question}' -> '{optimized['rewritten']}'")
        if optimized['sub_queries']:
            logger.info(f"子查询拆分: {optimized['sub_queries']}")

        # 调用原函数，传入优化后的查询
        return func(self, username, optimized['rewritten'], session_config, *args, **kwargs)

    return wrapper