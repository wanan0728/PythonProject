"""
配置文件
"""
import os
from dotenv import load_dotenv
from pathlib import Path
from utils.logger import logger

# ========== 强制加载.env文件 ==========
project_root = Path(__file__).parent.parent
env_path = project_root / '.env'

load_dotenv(dotenv_path=env_path, override=True)

logger.info(f"加载.env文件: {env_path}")
logger.info(f"文件存在: {env_path.exists()}")

# ========== API配置 ==========
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
if not DASHSCOPE_API_KEY:
    logger.error("DASHSCOPE_API_KEY 未设置")
    raise ValueError("请在.env文件中设置DASHSCOPE_API_KEY")

# ========== 邮箱配置 ==========
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

logger.info(f"邮箱配置: {SENDER_EMAIL}, 服务器: {SMTP_SERVER}:{SMTP_PORT}")

if not SENDER_EMAIL or not SENDER_PASSWORD:
    logger.error("邮箱配置未设置")
    raise ValueError("请在.env文件中设置邮箱配置")

# ========== Redis 缓存配置 ==========
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# ========== 知识库配置（使用绝对路径）===========
# 确保使用正确的绝对路径
PROJECT_ROOT = str(Path(__file__).parent.parent)  # C:\Users\123\Desktop\编程\PythonProject
md5_path = os.path.join(PROJECT_ROOT, "data", "md5.text")
collection_name = "rag"
persist_directory = os.path.join(PROJECT_ROOT, "data", "chroma_db")  # 精准路径

# 打印确认路径
print(f"📁 知识库存储路径: {persist_directory}")
print(f"📁 MD5文件路径: {md5_path}")

# ========== 文本分割配置 ==========
chunk_size = 1000
chunk_overlap = 100
separators = ["\n\n", "\n", ".", "!", "?", "。", "！", "？", " ", ""]
max_split_char_number = 1000

# ========== 检索配置 ==========
similarity_threshold = 3

# ========== 模型配置 ==========
embedding_model_name = "text-embedding-v4"
chat_model_name = "qwen3-max"

# ========== 会话配置 ==========
session_config = {
    "configurable": {
        "session_id": "user_001",
    }
}

# ========== 重排序配置 ==========
USE_RERANKER = os.getenv("USE_RERANKER", "true").lower() == "true"  # 是否启用重排序
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-base")  # 重排序模型
RERANKER_TOP_K = int(os.getenv("RERANKER_TOP_K", 5))  # 最终返回的文档数量
RERANKER_INITIAL_K = int(os.getenv("RERANKER_INITIAL_K", 20))  # 初始检索数量

if USE_RERANKER:
    logger.info(f"重排序已启用，模型: {RERANKER_MODEL}，初始检索: {RERANKER_INITIAL_K}，最终返回: {RERANKER_TOP_K}")


# ========== 查询优化配置 ==========
USE_QUERY_OPTIMIZATION = os.getenv("USE_QUERY_OPTIMIZATION", "true").lower() == "true"  # 是否启用查询优化
USE_HYDE = os.getenv("USE_HYDE", "false").lower() == "true"  # 是否启用HyDE（需要LLM）
QUERY_EXPANSION_SIZE = int(os.getenv("QUERY_EXPANSION_SIZE", 3))  # 查询扩展数量

if USE_QUERY_OPTIMIZATION:
    logger.info(f"查询优化已启用 (HyDE={USE_HYDE})")