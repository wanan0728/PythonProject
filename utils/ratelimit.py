"""
限流与防护模块
功能：控制API请求频率，防止滥用
"""
import time
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict
import streamlit as st
from utils.logger import logger
from utils.cache import cache_manager

# ========== 配置 ==========
# 不同操作的限流规则
RATE_LIMITS = {
    "login": {"max_attempts": 5, "window": 300},        # 登录：5次/5分钟（300秒）
    "register": {"max_attempts": 3, "window": 3600},    # 注册：3次/小时
    "send_code": {"max_attempts": 3, "window": 600},    # 验证码：3次/10分钟
    "chat": {"max_attempts": 30, "window": 60},         # 聊天：30次/分钟
    "upload": {"max_attempts": 10, "window": 3600},     # 上传：10次/小时
    "admin": {"max_attempts": 20, "window": 60},        # 管理员操作：20次/分钟
}
# IP黑名单（手动添加）
IP_BLACKLIST = set()

# 用户黑名单
USER_BLACKLIST = set()


# ========== 内存存储（备选）==========
class MemoryRateLimitStore:
    def __init__(self):
        self.records = defaultdict(list)
        self.blocked_until = {}
        logger.info("✅ 内存限流存储初始化成功")

    def add_attempt(self, key: str, action: str):
        """记录一次尝试"""
        record_key = f"{key}:{action}"
        now = time.time()
        self.records[record_key].append(now)
        # 清理旧记录
        limit = RATE_LIMITS.get(action, {"window": 60})["window"]
        self.records[record_key] = [t for t in self.records[record_key] if now - t < limit]

    def get_attempt_count(self, key: str, action: str) -> int:
        """获取尝试次数"""
        record_key = f"{key}:{action}"
        now = time.time()
        limit = RATE_LIMITS.get(action, {"window": 60})["window"]
        return len([t for t in self.records[record_key] if now - t < limit])

    def is_blocked(self, key: str) -> bool:
        """检查是否被临时封禁"""
        if key in self.blocked_until:
            if time.time() > self.blocked_until[key]:
                del self.blocked_until[key]
                return False
            return True
        return False

    def block(self, key: str, duration: int = 300):
        """临时封禁"""
        self.blocked_until[key] = time.time() + duration
        logger.warning(f"⛔ 临时封禁: {key}，时长: {duration}秒")


# ========== Redis存储（如果可用）==========
try:
    import redis
    from redis.exceptions import RedisError


    class RedisRateLimitStore:
        def __init__(self, host='localhost', port=6379, db=1):
            try:
                self.client = redis.Redis(
                    host=host,
                    port=port,
                    db=db,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=3
                )
                self.client.ping()
                self.available = True
                logger.info(f"✅ Redis限流存储连接成功: {host}:{port}")
            except Exception as e:
                self.available = False
                logger.warning(f"⚠️ Redis限流存储连接失败，使用内存存储: {e}")

        def add_attempt(self, key: str, action: str):
            if not self.available:
                return
            try:
                redis_key = f"ratelimit:{key}:{action}"
                self.client.rpush(redis_key, time.time())
                self.client.expire(redis_key, RATE_LIMITS.get(action, {"window": 60})["window"])
            except Exception as e:
                logger.error(f"Redis添加尝试失败: {e}")

        def get_attempt_count(self, key: str, action: str) -> int:
            if not self.available:
                return 0
            try:
                redis_key = f"ratelimit:{key}:{action}"
                now = time.time()
                window = RATE_LIMITS.get(action, {"window": 60})["window"]
                # 清理过期记录
                self.client.ltrim(redis_key, -window * 2, -1)
                return self.client.llen(redis_key)
            except Exception as e:
                logger.error(f"Redis获取尝试次数失败: {e}")
                return 0

        def is_blocked(self, key: str) -> bool:
            if not self.available:
                return False
            try:
                redis_key = f"blocked:{key}"
                return self.client.exists(redis_key) > 0
            except Exception as e:
                logger.error(f"Redis检查封禁失败: {e}")
                return False

        def block(self, key: str, duration: int = 300):
            if not self.available:
                return
            try:
                redis_key = f"blocked:{key}"
                self.client.setex(redis_key, duration, "1")
                logger.warning(f"⛔ Redis封禁: {key}，时长: {duration}秒")
            except Exception as e:
                logger.error(f"Redis封禁失败: {e}")

except ImportError:
    RedisRateLimitStore = None


# ========== 限流管理器 ==========
class RateLimitManager:
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=1):
        """初始化限流管理器"""
        # 尝试使用Redis
        if RedisRateLimitStore:
            self.store = RedisRateLimitStore(redis_host, redis_port, redis_db)
            if hasattr(self.store, 'available') and self.store.available:
                self.store_type = "redis"
            else:
                self.store = MemoryRateLimitStore()
                self.store_type = "memory"
        else:
            self.store = MemoryRateLimitStore()
            self.store_type = "memory"

        logger.info(f"✅ 限流管理器初始化完成，类型: {self.store_type}")

    def _get_key(self, identifier: str, ip: str = None) -> str:
        """生成限流键"""
        if ip:
            return f"{identifier}:{ip}"
        return identifier

    def check_rate_limit(self, identifier: str, action: str, ip: str = None) -> tuple:
        """
        检查是否超过限流
        :return: (是否允许, 剩余次数, 重置时间(秒))
        """
        key = self._get_key(identifier, ip)

        # 检查黑名单
        if identifier in USER_BLACKLIST:
            logger.warning(f"⛔ 用户 {identifier} 在黑名单中")
            return False, 0, 0

        if ip and ip in IP_BLACKLIST:
            logger.warning(f"⛔ IP {ip} 在黑名单中")
            return False, 0, 0

        # 检查临时封禁
        if self.store.is_blocked(key):
            logger.warning(f"⛔ {identifier} 被临时封禁")
            return False, 0, 0

        # 获取限流规则
        rule = RATE_LIMITS.get(action, {"max_attempts": 10, "window": 60})
        max_attempts = rule["max_attempts"]
        window = rule["window"]

        # 获取当前尝试次数
        current = self.store.get_attempt_count(key, action)

        if current >= max_attempts:
            logger.warning(f"⚠️ 超过限流: {identifier} - {action} ({current}/{max_attempts})")

            # 如果超过次数太多，临时封禁
            if current >= max_attempts * 2:
                self.store.block(key, window * 2)

            return False, 0, window

        remaining = max_attempts - current
        return True, remaining, window

    def add_attempt(self, identifier: str, action: str, ip: str = None):
        """记录一次尝试"""
        key = self._get_key(identifier, ip)
        self.store.add_attempt(key, action)

        # 记录日志
        current = self.store.get_attempt_count(key, action)
        rule = RATE_LIMITS.get(action, {"max_attempts": 10})
        logger.debug(f"📊 限流记录: {identifier} - {action} ({current}/{rule['max_attempts']})")

    def get_remaining(self, identifier: str, action: str, ip: str = None) -> int:
        """获取剩余次数"""
        key = self._get_key(identifier, ip)
        current = self.store.get_attempt_count(key, action)
        rule = RATE_LIMITS.get(action, {"max_attempts": 10})
        return max(0, rule["max_attempts"] - current)

    def block_user(self, identifier: str, duration: int = 3600):
        """手动封禁用户"""
        USER_BLACKLIST.add(identifier)
        logger.warning(f"⛔ 手动封禁用户: {identifier}，时长: {duration}秒")

    def unblock_user(self, identifier: str):
        """解封用户"""
        USER_BLACKLIST.discard(identifier)
        logger.info(f"✅ 用户已解封: {identifier}")

    def block_ip(self, ip: str, duration: int = 3600):
        """手动封禁IP"""
        IP_BLACKLIST.add(ip)
        logger.warning(f"⛔ 手动封禁IP: {ip}，时长: {duration}秒")

    def unblock_ip(self, ip: str):
        """解封IP"""
        IP_BLACKLIST.discard(ip)
        logger.info(f"✅ IP已解封: {ip}")


# ========== 获取客户端IP ==========
def get_client_ip() -> str:
    """获取客户端IP地址（Streamlit环境下）"""
    try:
        # 尝试从请求头获取
        headers = st.context.headers
        if headers:
            # 检查常见的IP头
            for header in ['X-Forwarded-For', 'X-Real-IP', 'Remote-Addr']:
                if header in headers:
                    ip = headers[header]
                    if ip:
                        # 如果是代理链，取第一个
                        return ip.split(',')[0].strip()
        # 默认返回本地IP
        return "127.0.0.1"
    except:
        return "127.0.0.1"


# ========== 限流装饰器 ==========
def rate_limit(action: str, identifier_func=None):
    """
    限流装饰器
    :param action: 操作类型 (login/register/send_code/chat/upload/admin)
    :param identifier_func: 获取标识符的函数，默认使用用户名
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            # 获取标识符
            if identifier_func:
                identifier = identifier_func(*args, **kwargs)
            else:
                # 默认使用当前登录用户或IP
                identifier = st.session_state.get('username', 'anonymous')

            ip = get_client_ip()

            # 检查限流
            allowed, remaining, reset_time = rate_limit_manager.check_rate_limit(
                identifier, action, ip
            )

            if not allowed:
                if remaining == 0:
                    logger.warning(f"⛔ 请求被限流: {identifier} - {action}")
                    st.error(f"操作太频繁，请稍后再试")
                else:
                    st.warning(f"今日剩余尝试次数: {remaining}")
                return None

            # 执行函数
            result = func(*args, **kwargs)

            # 记录尝试
            rate_limit_manager.add_attempt(identifier, action, ip)

            return result

        return wrapper

    return decorator


# ========== 全局限流管理器实例 ==========
from config.config_data import REDIS_HOST, REDIS_PORT

rate_limit_manager = RateLimitManager(
    redis_host=REDIS_HOST,
    redis_port=REDIS_PORT,
    redis_db=1  # 使用不同的数据库
)