"""
配置文件
"""
import os
from dotenv import load_dotenv
from pathlib import Path

# ========== 强制加载.env文件 ==========
# 方法1：使用绝对路径
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# 方法2：如果上面不行，试试直接指定路径（取消下面两行的注释试试）
# env_path = r"C:\Users\123\Desktop\编程\PythonProject\.env"
# load_dotenv(dotenv_path=env_path, override=True)

print(f"✅ 尝试加载.env文件: {env_path}")
print(f"✅ 文件是否存在: {env_path.exists()}")

# ========== API配置 ==========
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
if not DASHSCOPE_API_KEY:
    raise ValueError("请在.env文件中设置DASHSCOPE_API_KEY")

# ========== 邮箱配置 ==========
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

# 打印调试信息
print(f"📧 SENDER_EMAIL: {SENDER_EMAIL}")
print(f"📧 SENDER_PASSWORD: {'已设置' if SENDER_PASSWORD else '未设置'}")

if not SENDER_EMAIL or not SENDER_PASSWORD:
    raise ValueError("请在.env文件中设置邮箱配置")

# ========== 知识库配置 ==========
md5_path = "./md5.text"
collection_name = "rag"
persist_directory = "./chroma_db"

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