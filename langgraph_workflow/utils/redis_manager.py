import redis
import json
import uuid
import pickle
from typing import Any, Dict, Optional, List, Union
from datetime import datetime, timedelta
import os
from enum import Enum

class DataType(Enum):
    """数据类型枚举"""
    SESSION = "session"
    NODE_RESULT = "node_result"
    FEEDBACK = "feedback"
    CACHE = "cache"
    WORKFLOW_STATE = "workflow_state"
    FIGMA_DATA = "figma_data"
    VIEWPOINTS = "viewpoints"
    LLM_CALL = "llm_call"

class RedisManager:
    """Redis统一管理器 - 替代PostgreSQL和文件缓存"""
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379")
        self.client = redis.from_url(self.redis_url, decode_responses=False)
        
        # 测试连接
        try:
            self.client.ping()
        except Exception as e:
            raise ConnectionError(f"Redis连接失败: {e}")
    
    def _generate_key(self, data_type: DataType, identifier: str, sub_key: str = None) -> str:
        """生成Redis键"""
        if sub_key:
            return f"{data_type.value}:{identifier}:{sub_key}"
        return f"{data_type.value}:{identifier}"
    
    def _serialize_data(self, data: Any) -> bytes:
        """序列化数据"""
        if isinstance(data, (dict, list, str, int, float, bool)):
            return pickle.dumps(data)
        return pickle.dumps(data)
    
    def _deserialize_data(self, data: bytes) -> Any:
        """反序列化数据"""
        if data is None:
            return None
        return pickle.loads(data)
    
    # ==================== Session管理 ====================
    def create_session(self, input_data: Dict[str, Any], config: Dict[str, Any]) -> str:
        """创建新session"""
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "input": input_data,
            "config": config,
            "created_at": datetime.now().isoformat(),
            "status": "active"
        }
        
        key = self._generate_key(DataType.SESSION, session_id)
        self.client.setex(key, 86400, self._serialize_data(session_data))  # 24小时过期
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取session信息"""
        key = self._generate_key(DataType.SESSION, session_id)
        data = self.client.get(key)
        return self._deserialize_data(data)
    
    def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """更新session信息"""
        session_data = self.get_session(session_id)
        if session_data:
            session_data.update(updates)
            session_data["updated_at"] = datetime.now().isoformat()
            key = self._generate_key(DataType.SESSION, session_id)
            return self.client.setex(key, 86400, self._serialize_data(session_data))
        return False
    
    # ==================== 节点结果管理 ====================
    def save_node_result(self, session_id: str, node_name: str, 
                        input_data: Dict[str, Any], output_data: Dict[str, Any]) -> bool:
        """保存节点结果"""
        result_data = {
            "session_id": session_id,
            "node_name": node_name,
            "input": input_data,
            "output": output_data,
            "created_at": datetime.now().isoformat()
        }
        
        # 保存最新结果
        latest_key = self._generate_key(DataType.NODE_RESULT, session_id, f"{node_name}:latest")
        self.client.setex(latest_key, 86400, self._serialize_data(result_data))
        
        # 保存历史记录（使用列表）
        history_key = self._generate_key(DataType.NODE_RESULT, session_id, f"{node_name}:history")
        history = self.client.lrange(history_key, 0, -1)
        history_data = [self._deserialize_data(item) for item in history]
        history_data.append(result_data)
        
        # 只保留最近10条记录
        if len(history_data) > 10:
            history_data = history_data[-10:]
        
        # 重新保存历史记录
        self.client.delete(history_key)
        for item in history_data:
            self.client.rpush(history_key, self._serialize_data(item))
        self.client.expire(history_key, 86400)
        
        return True
    
    def get_node_result(self, session_id: str, node_name: str, 
                       get_latest: bool = True) -> Optional[Dict[str, Any]]:
        """获取节点结果"""
        if get_latest:
            key = self._generate_key(DataType.NODE_RESULT, session_id, f"{node_name}:latest")
            data = self.client.get(key)
            return self._deserialize_data(data)
        else:
            # 获取历史记录
            key = self._generate_key(DataType.NODE_RESULT, session_id, f"{node_name}:history")
            history = self.client.lrange(key, 0, -1)
            return [self._deserialize_data(item) for item in history]
    
    def get_all_node_results(self, session_id: str) -> Dict[str, Any]:
        """获取session的所有节点结果"""
        pattern = self._generate_key(DataType.NODE_RESULT, session_id, "*:latest")
        keys = self.client.keys(pattern)
        
        results = {}
        for key in keys:
            node_name = key.decode().split(":")[-2]  # 提取节点名
            data = self.client.get(key)
            if data:
                results[node_name] = self._deserialize_data(data)
        
        return results
    
    # ==================== 反馈管理 ====================
    def save_feedback(self, session_id: str, node_name: str, feedback: Dict[str, Any]) -> bool:
        """保存反馈"""
        feedback_data = {
            "session_id": session_id,
            "node_name": node_name,
            "feedback": feedback,
            "created_at": datetime.now().isoformat()
        }
        
        key = self._generate_key(DataType.FEEDBACK, session_id, node_name)
        return self.client.setex(key, 86400, self._serialize_data(feedback_data))
    
    def get_feedback(self, session_id: str, node_name: str) -> Optional[Dict[str, Any]]:
        """获取反馈"""
        key = self._generate_key(DataType.FEEDBACK, session_id, node_name)
        data = self.client.get(key)
        return self._deserialize_data(data)
    
    # ==================== 缓存管理 ====================
    def set_cache(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """设置缓存"""
        cache_key = self._generate_key(DataType.CACHE, key)
        return self.client.setex(cache_key, ttl, self._serialize_data(value))
    
    def get_cache(self, key: str) -> Any:
        """获取缓存"""
        cache_key = self._generate_key(DataType.CACHE, key)
        data = self.client.get(cache_key)
        return self._deserialize_data(data)
    
    def delete_cache(self, key: str) -> bool:
        """删除缓存"""
        cache_key = self._generate_key(DataType.CACHE, key)
        return bool(self.client.delete(cache_key))
    
    def clear_cache_by_pattern(self, pattern: str) -> int:
        """按模式清除缓存"""
        cache_pattern = self._generate_key(DataType.CACHE, pattern)
        keys = self.client.keys(cache_pattern)
        if keys:
            return self.client.delete(*keys)
        return 0
    
    # ==================== 工作流状态管理 ====================
    def save_workflow_state(self, workflow_id: str, state: Dict[str, Any], ttl: int = 7200) -> bool:
        """保存工作流状态"""
        state_data = {
            "workflow_id": workflow_id,
            "state": state,
            "updated_at": datetime.now().isoformat()
        }
        key = self._generate_key(DataType.WORKFLOW_STATE, workflow_id)
        return self.client.setex(key, ttl, self._serialize_data(state_data))
    
    def get_workflow_state(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """获取工作流状态"""
        key = self._generate_key(DataType.WORKFLOW_STATE, workflow_id)
        data = self.client.get(key)
        result = self._deserialize_data(data)
        return result["state"] if result else None
    
    # ==================== Figma数据管理 ====================
    def cache_figma_data(self, file_key: str, data: Dict[str, Any], ttl: int = 7200) -> bool:
        """缓存Figma数据"""
        key = self._generate_key(DataType.FIGMA_DATA, file_key)
        return self.client.setex(key, ttl, self._serialize_data(data))
    
    def get_figma_data(self, file_key: str) -> Optional[Dict[str, Any]]:
        """获取Figma数据"""
        key = self._generate_key(DataType.FIGMA_DATA, file_key)
        data = self.client.get(key)
        return self._deserialize_data(data)
    
    def cache_frame_data(self, file_key: str, frame_id: str, frame_data: Dict[str, Any], ttl: int = 1800) -> bool:
        """缓存Frame数据"""
        key = self._generate_key(DataType.FIGMA_DATA, f"{file_key}:frame:{frame_id}")
        return self.client.setex(key, ttl, self._serialize_data(frame_data))
    
    def get_frame_data(self, file_key: str, frame_id: str) -> Optional[Dict[str, Any]]:
        """获取Frame数据"""
        key = self._generate_key(DataType.FIGMA_DATA, f"{file_key}:frame:{frame_id}")
        data = self.client.get(key)
        return self._deserialize_data(data)
    
    # ==================== 测试观点管理 ====================
    def cache_viewpoints(self, file_hash: str, viewpoints: Dict[str, Any], ttl: int = 7200) -> bool:
        """缓存测试观点"""
        key = self._generate_key(DataType.VIEWPOINTS, file_hash)
        return self.client.setex(key, ttl, self._serialize_data(viewpoints))
    
    def get_viewpoints(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """获取测试观点"""
        key = self._generate_key(DataType.VIEWPOINTS, file_hash)
        data = self.client.get(key)
        return self._deserialize_data(data)
    
    # ==================== LLM调用缓存 ====================
    def cache_llm_call(self, call_hash: str, response: str, ttl: int = 3600) -> bool:
        """缓存LLM调用"""
        key = self._generate_key(DataType.LLM_CALL, call_hash)
        return self.client.setex(key, ttl, self._serialize_data(response))
    
    def get_llm_call(self, call_hash: str) -> Optional[str]:
        """获取LLM调用缓存"""
        key = self._generate_key(DataType.LLM_CALL, call_hash)
        data = self.client.get(key)
        return self._deserialize_data(data)
    
    # ==================== 统计和监控 ====================
    def get_stats(self) -> Dict[str, Any]:
        """获取Redis统计信息"""
        info = self.client.info()
        return {
            "total_keys": info.get("db0", {}).get("keys", 0),
            "memory_usage": info.get("used_memory_human", "N/A"),
            "connected_clients": info.get("connected_clients", 0),
            "uptime": info.get("uptime_in_seconds", 0)
        }
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """获取session统计信息"""
        session = self.get_session(session_id)
        node_results = self.get_all_node_results(session_id)
        
        return {
            "session_id": session_id,
            "created_at": session.get("created_at") if session else None,
            "node_count": len(node_results),
            "nodes": list(node_results.keys()),
            "status": session.get("status") if session else None
        }
    
    # ==================== 清理和过期管理 ====================
    def cleanup_expired_sessions(self) -> int:
        """清理过期session"""
        pattern = f"{DataType.SESSION.value}:*"
        keys = self.client.keys(pattern)
        expired_count = 0
        
        for key in keys:
            if not self.client.exists(key):  # 检查是否已过期
                expired_count += 1
        
        return expired_count
    
    def set_session_expiry(self, session_id: str, ttl: int = 86400) -> bool:
        """设置session过期时间"""
        key = self._generate_key(DataType.SESSION, session_id)
        return bool(self.client.expire(key, ttl))

# 全局Redis管理器实例
redis_manager = RedisManager() 