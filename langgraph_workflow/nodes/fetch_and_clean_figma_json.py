import requests
from typing import Any, Dict, Set
from fastapi import HTTPException
from utils.cache_manager import cache_result, cache_manager
from utils.figma_compressor import figma_compressor
from utils.intelligent_cache_manager import intelligent_cache_manager

@cache_result(prefix="figma_raw", ttl=7200)  # 原始Figma数据缓存2小时
def fetch_figma_json(access_token: str, file_key: str) -> Dict[str, Any]:
    """获取Figma JSON数据（带缓存）"""
    url = f"https://api.figma.com/v1/files/{file_key}"
    headers = {"X-Figma-Token": access_token}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Figma API error: {resp.text}")
    return resp.json()

@cache_result(prefix="figma_cleaned", ttl=3600)  # 清理后的数据缓存1小时
def clean_figma_json(figma_json: Dict[str, Any], keep_types: Set[str] = None) -> Dict[str, Any]:
    """清理Figma JSON数据（带缓存）"""
    if keep_types is None:
        keep_types = {"FRAME", "COMPONENT", "INSTANCE", "BUTTON", "TEXT", "RECTANGLE", "GROUP"}
    
    def filter_node(node):
        if node.get("type") not in keep_types:
            return None
        filtered = {k: v for k, v in node.items() if k in ("id", "name", "type", "children", "characters", "componentId", "text", "absoluteBoundingBox", "interaction")}
        if "children" in filtered:
            filtered["children"] = [c for c in (filter_node(child) for child in node.get("children", [])) if c]
        return filtered
    
    doc = figma_json.get("document", {})
    cleaned = filter_node(doc)
    return cleaned

def fetch_and_clean_figma_json(access_token: str, file_key: str, enable_compression: bool = True) -> Dict[str, Any]:
    """获取并清理Figma JSON数据（带缓存和压缩）"""
    # 使用智能缓存管理器
    cache_key = f"figma_processed_{file_key}_{enable_compression}"
    cached_result = intelligent_cache_manager.get_with_intelligence(cache_key)
    if cached_result is not None:
        return cached_result
    
    # 获取原始数据
    raw_json = fetch_figma_json(access_token, file_key)
    
    # 清理数据
    cleaned = clean_figma_json(raw_json)
    
    # 压缩数据（如果启用）
    if enable_compression:
        compressed = figma_compressor.compress_figma_data(cleaned)
        result = compressed
    else:
        result = cleaned
    
    # 缓存结果
    intelligent_cache_manager.set_with_intelligence(cache_key, result, ttl=7200)
    
    # 同时缓存到Redis
    cache_manager.cache_figma_data(file_key, result, ttl=7200)
    
    return result

# Frame级别的缓存
def get_frame_cache_key(file_key: str, frame_id: str) -> str:
    """生成Frame级别的缓存键"""
    return f"figma_frame_{file_key}_{frame_id}"

def cache_frame_data(file_key: str, frame_id: str, frame_data: Dict[str, Any], ttl: int = 1800):
    """缓存单个Frame数据"""
    cache_manager.cache_frame_data(file_key, frame_id, frame_data, ttl)

def get_cached_frame_data(file_key: str, frame_id: str) -> Dict[str, Any]:
    """获取缓存的Frame数据"""
    return cache_manager.get_frame_data(file_key, frame_id)

# 新增：批量Frame预加载
def preload_frames(file_key: str, frame_ids: List[str], access_token: str):
    """预加载多个Frame数据"""
    for frame_id in frame_ids:
        # 检查是否已缓存
        if get_cached_frame_data(file_key, frame_id) is None:
            try:
                # 获取单个Frame数据
                frame_data = fetch_single_frame(access_token, file_key, frame_id)
                if frame_data:
                    cache_frame_data(file_key, frame_id, frame_data)
            except Exception as e:
                print(f"预加载Frame {frame_id} 失败: {e}")

def fetch_single_frame(access_token: str, file_key: str, frame_id: str) -> Dict[str, Any]:
    """获取单个Frame数据"""
    url = f"https://api.figma.com/v1/files/{file_key}/nodes?ids={frame_id}"
    headers = {"X-Figma-Token": access_token}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("nodes", {}).get(frame_id, {})
    return None

# 新增：获取压缩统计信息
def get_compression_stats() -> Dict[str, Any]:
    """获取压缩统计信息"""
    return figma_compressor.get_compression_stats()

# 新增：获取缓存统计信息
def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计信息"""
    return intelligent_cache_manager.get_stats()