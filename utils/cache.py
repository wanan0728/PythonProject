"""
缓存模块
功能：提供 Redis 缓存支持，备选内存缓存
"""
import json
import hashlib
import time
from typing import Any, Optional, Callable
import streamlit as st
from utils.logger import logger

# ========== 配置 ==========
CACHE_TTL = 3600  # 默认缓存时间 1小时
CACHE_PREFIX = "rag_cache:"

# ========== Redis 客户端（如果可用）==========
try:
    import redis


    class RedisCache:
        def __init__(self, host='localhost', port=6379, db=0, password=None):
            """初始化 Redis 连接"""
            try:
                self.client = redis.Redis(
                    host=host,
                    port=port,
                    db=db,
                    password=password,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=3
                )
                # 测试连接
                self.client.ping()
                self.available = True
                logger.info(f"✅ Redis 缓存连接成功: {host}:{port}")
            except Exception as e:
                self.available = False
                logger.warning(f"⚠️ Redis 连接失败，使用内存缓存: {e}")

        def get(self, key: str) -> Optional[str]:
            """获取缓存"""
            if not self.available:
                return None
            try:
                return self.client.get(f"{CACHE_PREFIX}{key}")
            except Exception as e:
                logger.error(f"Redis get 失败: {e}")
                return None

        def set(self, key: str, value: str, ttl: int = CACHE_TTL):
            """设置缓存"""
            if not self.available:
                return False
            try:
                return self.client.setex(f"{CACHE_PREFIX}{key}", ttl, value)
            except Exception as e:
                logger.error(f"Redis set 失败: {e}")
                return False

        def delete(self, key: str):
            """删除缓存"""
            if not self.available:
                return False
            try:
                return self.client.delete(f"{CACHE_PREFIX}{key}")
            except Exception as e:
                logger.error(f"Redis delete 失败: {e}")
                return False

        def clear_pattern(self, pattern: str):
            """按模式清除缓存"""
            if not self.available:
                return 0
            try:
                keys = self.client.keys(f"{CACHE_PREFIX}{pattern}")
                if keys:
                    return self.client.delete(*keys)
                return 0
            except Exception as e:
                logger.error(f"Redis clear_pattern 失败: {e}")
                return 0

except ImportError:
    logger.warning("redis 模块未安装，使用内存缓存")
    RedisCache = None


# ========== 内存缓存（备选）==========
class MemoryCache:
    def __init__(self):
        self.cache = {}
        self.expire_times = {}
        logger.info("✅ 内存缓存初始化成功")

    def get(self, key: str) -> Optional[str]:
        """获取缓存"""
        full_key = f"{CACHE_PREFIX}{key}"

        # 检查是否存在且未过期
        if full_key in self.cache:
            if full_key in self.expire_times:
                if time.time() > self.expire_times[full_key]:
                    # 已过期
                    del self.cache[full_key]
                    del self.expire_times[full_key]
                    return None
            return self.cache[full_key]
        return None

    def set(self, key: str, value: str, ttl: int = CACHE_TTL):
        """设置缓存"""
        full_key = f"{CACHE_PREFIX}{key}"
        self.cache[full_key] = value
        if ttl > 0:
            self.expire_times[full_key] = time.time() + ttl
        return True

    def delete(self, key: str):
        """删除缓存"""
        full_key = f"{CACHE_PREFIX}{key}"
        if full_key in self.cache:
            del self.cache[full_key]
        if full_key in self.expire_times:
            del self.expire_times[full_key]
        return True

    def clear_pattern(self, pattern: str):
        """按模式清除缓存"""
        count = 0
        pattern_full = f"{CACHE_PREFIX}{pattern}"
        keys_to_delete = [k for k in self.cache.keys() if k.startswith(pattern_full.replace('*', ''))]
        for key in keys_to_delete:
            del self.cache[key]
            if key in self.expire_times:
                del self.expire_times[key]
            count += 1
        return count


# ========== 缓存管理器 ==========
class CacheManager:
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0, redis_password=None):
        """初始化缓存管理器"""
        # 尝试使用 Redis
        if RedisCache:
            self.cache = RedisCache(redis_host, redis_port, redis_db, redis_password)
            if self.cache.available:
                self.cache_type = "redis"
            else:
                self.cache = MemoryCache()
                self.cache_type = "memory"
        else:
            self.cache = MemoryCache()
            self.cache_type = "memory"

        logger.info(f"✅ 缓存管理器初始化完成，类型: {self.cache_type}")

    def _make_key(self, *args, **kwargs) -> str:
        """生成缓存键"""
        # 将参数组合成字符串
        key_parts = []
        for arg in args:
            key_parts.append(str(arg))
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")

        key_str = ":".join(key_parts)
        # 如果太长，用 MD5 缩短
        if len(key_str) > 200:
            return hashlib.md5(key_str.encode()).hexdigest()
        return key_str

    def get_or_set(self, key_prefix: str, func: Callable, ttl: int = CACHE_TTL, *args, **kwargs):
        """
        获取缓存，如果没有则执行函数并缓存
        :param key_prefix: 缓存键前缀
        :param func: 要执行的函数
        :param ttl: 缓存时间（秒）
        :param args: 函数参数
        :param kwargs: 函数关键字参数
        :return: 函数执行结果
        """
        # 生成完整缓存键
        cache_key = self._make_key(key_prefix, *args, **kwargs)

        # 尝试从缓存获取
        cached_value = self.cache.get(cache_key)
        if cached_value is not None:
            try:
                result = json.loads(cached_value)
                logger.debug(f"缓存命中: {key_prefix} - {cache_key[:20]}...")
                return result
            except:
                logger.warning(f"缓存数据损坏: {cache_key[:20]}...")

        # 执行函数
        logger.debug(f"缓存未命中，执行函数: {key_prefix}")
        result = func(*args, **kwargs)

        # 存入缓存
        try:
            self.cache.set(cache_key, json.dumps(result, ensure_ascii=False), ttl)
            logger.debug(f"缓存已设置: {key_prefix}, TTL={ttl}s")
        except Exception as e:
            logger.error(f"缓存设置失败: {e}")

        return result

    def clear_cache(self, pattern: str = "*"):
        """清除缓存"""
        count = self.cache.clear_pattern(pattern)
        logger.info(f"已清除 {count} 个缓存项，模式: {pattern}")
        return count


# ========== 全局缓存实例 ==========
from config.config_data import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD

cache_manager = CacheManager(
    redis_host=REDIS_HOST,
    redis_port=REDIS_PORT,
    redis_db=REDIS_DB,
    redis_password=REDIS_PASSWORD
)


# ========== 缓存装饰器 ==========
def cached(ttl: int = CACHE_TTL, key_prefix: str = None):
    """
    缓存装饰器
    :param ttl: 缓存时间（秒）
    :param key_prefix: 缓存键前缀，默认使用函数名
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            prefix = key_prefix or func.__name__
            return cache_manager.get_or_set(prefix, func, ttl, *args, **kwargs)

        return wrapper

    return decorator