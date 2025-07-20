from utils.redis_manager import redis_manager
from functools import wraps
import hashlib
import json
from typing import Any, Dict, Optional

class CacheManager:
    """缓存管理器 - 基于Redis"""
    
    def __init__(self):
        self.redis_manager = redis_manager
    
    def _generate_cache_key(self, data: Any, prefix: str = "") -> str:
        """生成缓存键"""
        if isinstance(data, dict):
            content = json.dumps(data, sort_keys=True)
        elif isinstance(data, bytes):
            content = data.hex()
        else:
            content = str(data)
        
        hash_value = hashlib.md5(f"{prefix}:{content}".encode()).hexdigest()
        return f"{prefix}_{hash_value}"
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值"""
        return self.redis_manager.get_cache(key) or default
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """设置缓存值"""
        return self.redis_manager.set_cache(key, value, ttl)
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        return self.redis_manager.delete_cache(key)
    
    def clear_by_pattern(self, pattern: str) -> int:
        """按模式清除缓存"""
        return self.redis_manager.clear_cache_by_pattern(pattern)
    
    def cache_figma_data(self, file_key: str, data: Dict[str, Any], ttl: int = 7200) -> bool:
        """缓存Figma数据"""
        return self.redis_manager.cache_figma_data(file_key, data, ttl)
    
    def get_figma_data(self, file_key: str) -> Optional[Dict[str, Any]]:
        """获取Figma数据"""
        return self.redis_manager.get_figma_data(file_key)
    
    def cache_frame_data(self, file_key: str, frame_id: str, frame_data: Dict[str, Any], ttl: int = 1800) -> bool:
        """缓存Frame数据"""
        return self.redis_manager.cache_frame_data(file_key, frame_id, frame_data, ttl)
    
    def get_frame_data(self, file_key: str, frame_id: str) -> Optional[Dict[str, Any]]:
        """获取Frame数据"""
        return self.redis_manager.get_frame_data(file_key, frame_id)
    
    def cache_viewpoints(self, file_hash: str, viewpoints: Dict[str, Any], ttl: int = 7200) -> bool:
        """缓存测试观点"""
        return self.redis_manager.cache_viewpoints(file_hash, viewpoints, ttl)
    
    def get_viewpoints(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """获取测试观点"""
        return self.redis_manager.get_viewpoints(file_hash)
    
    def cache_llm_call(self, call_hash: str, response: str, ttl: int = 3600) -> bool:
        """缓存LLM调用"""
        return self.redis_manager.cache_llm_call(call_hash, response, ttl)
    
    def get_llm_call(self, call_hash: str) -> Optional[str]:
        """获取LLM调用缓存"""
        return self.redis_manager.get_llm_call(call_hash)

# 全局缓存管理器实例
cache_manager = CacheManager()

def cache_result(prefix: str = "", ttl: int = 3600):
    """缓存装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = cache_manager._generate_cache_key(
                {"args": args, "kwargs": kwargs}, 
                prefix=f"{prefix}_{func.__name__}"
            )
            
            # 尝试从缓存获取
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator

def cache_llm_call(ttl: int = 3600):
    """LLM调用缓存装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # 提取LLM相关参数
            prompt = kwargs.get('prompt', '')
            model = kwargs.get('model', 'gpt-4o')
            temperature = kwargs.get('temperature', 0.2)
            max_tokens = kwargs.get('max_tokens')
            
            # 生成缓存键
            cache_data = {
                "prompt": prompt,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            content = json.dumps(cache_data, sort_keys=True)
            call_hash = hashlib.md5(content.encode()).hexdigest()
            
            # 尝试从缓存获取
            cached_response = cache_manager.get_llm_call(call_hash)
            if cached_response is not None:
                return cached_response
            
            # 执行LLM调用
            response = func(*args, **kwargs)
            
            # 缓存响应
            cache_manager.cache_llm_call(call_hash, response, ttl)
            return response
        return wrapper
    return decorator 