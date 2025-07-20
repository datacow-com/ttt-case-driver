from typing import Any, Dict, Optional, List
from utils.cache_manager import cache_manager
import time
import threading
from collections import OrderedDict

class IntelligentCacheManager:
    """智能缓存管理器 - 支持热点缓存和智能预加载"""
    
    def __init__(self, hot_cache_size: int = 100, access_threshold: int = 3):
        self.hot_cache = OrderedDict()  # 热点缓存（LRU）
        self.access_count = {}  # 访问计数
        self.access_threshold = access_threshold  # 提升阈值
        self.hot_cache_size = hot_cache_size  # 热点缓存大小
        self.lock = threading.Lock()  # 线程锁
        
        # 缓存统计
        self.stats = {
            "hot_cache_hits": 0,
            "redis_cache_hits": 0,
            "cache_misses": 0,
            "promotions": 0,
            "evictions": 0
        }
    
    def get_with_intelligence(self, key: str, default: Any = None) -> Any:
        """智能获取缓存"""
        with self.lock:
            # 1. 检查热点缓存
            if key in self.hot_cache:
                self.stats["hot_cache_hits"] += 1
                # 移动到末尾（LRU）
                value = self.hot_cache.pop(key)
                self.hot_cache[key] = value
                self.access_count[key] = self.access_count.get(key, 0) + 1
                return value
            
            # 2. 检查Redis缓存
            result = cache_manager.get(key, default)
            if result is not None:
                self.stats["redis_cache_hits"] += 1
                # 提升到热点缓存
                self.promote_to_hot_cache(key, result)
                return result
            
            # 3. 缓存未命中
            self.stats["cache_misses"] += 1
            return default
    
    def set_with_intelligence(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """智能设置缓存"""
        with self.lock:
            # 同时设置Redis缓存和热点缓存
            redis_success = cache_manager.set(key, value, ttl)
            if redis_success:
                self.promote_to_hot_cache(key, value)
            return redis_success
    
    def promote_to_hot_cache(self, key: str, value: Any):
        """提升到热点缓存"""
        # 检查访问次数是否达到阈值
        access_count = self.access_count.get(key, 0) + 1
        self.access_count[key] = access_count
        
        if access_count >= self.access_threshold:
            # 检查热点缓存大小
            if len(self.hot_cache) >= self.hot_cache_size:
                # 移除最少访问的项
                least_accessed = min(self.access_count.items(), key=lambda x: x[1])
                del self.hot_cache[least_accessed[0]]
                del self.access_count[least_accessed[0]]
                self.stats["evictions"] += 1
            
            # 添加到热点缓存
            self.hot_cache[key] = value
            self.stats["promotions"] += 1
    
    def preload_cache(self, keys: List[str], data_provider_func):
        """缓存预热"""
        for key in keys:
            if key not in self.hot_cache and cache_manager.get(key) is None:
                try:
                    data = data_provider_func(key)
                    if data is not None:
                        self.set_with_intelligence(key, data, ttl=7200)
                except Exception as e:
                    print(f"预加载缓存失败 {key}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_requests = self.stats["hot_cache_hits"] + self.stats["redis_cache_hits"] + self.stats["cache_misses"]
        hit_rate = (self.stats["hot_cache_hits"] + self.stats["redis_cache_hits"]) / total_requests if total_requests > 0 else 0
        
        return {
            **self.stats,
            "total_requests": total_requests,
            "hit_rate": f"{hit_rate:.2%}",
            "hot_cache_size": len(self.hot_cache),
            "access_threshold": self.access_threshold
        }
    
    def clear_hot_cache(self):
        """清空热点缓存"""
        with self.lock:
            self.hot_cache.clear()
            self.access_count.clear()
    
    def get_hot_cache_keys(self) -> List[str]:
        """获取热点缓存键列表"""
        return list(self.hot_cache.keys())

# 全局智能缓存管理器实例
intelligent_cache_manager = IntelligentCacheManager()