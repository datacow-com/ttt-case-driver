from typing import Dict, Any, List, Optional, Tuple
import requests
import json
from ..utils.cache_manager import cache_result, cache_manager
from ..utils.figma_compressor import figma_compressor
from ..utils.intelligent_cache_manager import intelligent_cache_manager
from .load_page import extract_pages_and_frames, process_figma_data
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

@cache_result(prefix="figma_raw", ttl=7200)  # 原始Figma数据缓存2小时
def fetch_figma_json(access_token: str, file_key: str) -> Dict[str, Any]:
    """获取Figma JSON数据（带缓存）"""
    url = f"https://api.figma.com/v1/files/{file_key}"
    headers = {"X-Figma-Token": access_token}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise Exception(f"Figma API error: {resp.text}")
    return resp.json()

def fetch_figma_data(figma_access_token: str, figma_file_key: str, extract_frames_only: bool = False) -> Dict[str, Any]:
    """
    从Figma API获取数据，并处理为系统所需格式
    
    Args:
        figma_access_token: Figma API访问令牌
        figma_file_key: Figma文件ID
        extract_frames_only: 是否只提取Frame信息
        
    Returns:
        处理后的Figma数据
    """
    try:
        logging.info(f"开始获取Figma数据，文件ID: {figma_file_key}")
        
        # 使用智能缓存管理器
        cache_key = f"figma_processed_{figma_file_key}"
        cached_result = intelligent_cache_manager.get_with_intelligence(cache_key)
        if cached_result is not None:
            logging.info(f"找到缓存的Figma数据: {cache_key}")
            # 如果有缓存，直接返回或处理缓存数据
            if extract_frames_only:
                pages, frames = extract_pages_and_frames(cached_result)
                logging.info(f"从缓存中提取Frame信息: {len(frames)}个Frame，{len(pages)}个页面")
                
                # 构建Frame选择列表
                available_frames = []
                for page in pages:
                    page_frames = [f for f in frames if f.get("page_id") == page.get("id")]
                    if page_frames:
                        available_frames.append({
                            "label": f"{page.get('name')} ({len(page_frames)}个Frame)",
                            "options": [{"label": f"{frame.get('name')} ({frame.get('type')})", "value": frame.get('id')} for frame in page_frames]
                        })
                return {
                    "cache_id": cache_key,
                    "available_frames": available_frames,
                    "frames_count": len(frames),
                    "pages": pages
                }
            return {
                "cache_id": cache_key,
                "data": cached_result
            }
        
        # 获取原始数据
        logging.info(f"从Figma API获取数据: {figma_file_key}")
        figma_json = fetch_figma_json(figma_access_token, figma_file_key)
        
        # 缓存原始数据
        raw_cache_key = f"figma_raw_{figma_file_key}"
        intelligent_cache_manager.set_with_intelligence(raw_cache_key, figma_json, ttl=7200)
        logging.info(f"缓存原始Figma数据: {raw_cache_key}")
        
        if extract_frames_only:
            # 如果只需要提取Frame信息
            logging.info("提取Frame信息")
            pages, frames = extract_pages_and_frames(figma_json)
            logging.info(f"提取了{len(frames)}个Frame，{len(pages)}个页面")
            
            # 构建Frame选择列表
            available_frames = []
            for page in pages:
                page_frames = [f for f in frames if f.get("page_id") == page.get("id")]
                if page_frames:
                    available_frames.append({
                        "label": f"{page.get('name')} ({len(page_frames)}个Frame)",
                        "options": [{"label": f"{frame.get('name')} ({frame.get('type')})", "value": frame.get('id')} for frame in page_frames]
                    })
            
            # 缓存处理后的完整数据
            intelligent_cache_manager.set_with_intelligence(cache_key, figma_json, ttl=7200)
            cache_manager.cache_figma_data(figma_file_key, figma_json, ttl=7200)
            logging.info(f"缓存处理后的Figma数据: {cache_key}")
            
            return {
                "cache_id": cache_key,
                "available_frames": available_frames,
                "frames_count": len(frames),
                "pages": pages
            }
        else:
            # 处理完整数据
            logging.info("处理完整Figma数据")
            processed_data = process_figma_data(figma_json)
            
            # 缓存处理后的数据
            intelligent_cache_manager.set_with_intelligence(cache_key, figma_json, ttl=7200)
            cache_manager.cache_figma_data(figma_file_key, figma_json, ttl=7200)
            logging.info(f"缓存处理后的Figma数据: {cache_key}")
            
            return {
                "cache_id": cache_key,
                "data": processed_data
            }
    except Exception as e:
        logging.error(f"获取Figma数据失败: {str(e)}", exc_info=True)
        raise Exception(f"获取Figma数据失败: {str(e)}")

# 用于获取单个Frame数据
def fetch_single_frame(access_token: str, file_key: str, frame_id: str) -> Dict[str, Any]:
    """获取单个Frame数据"""
    url = f"https://api.figma.com/v1/files/{file_key}/nodes?ids={frame_id}"
    headers = {"X-Figma-Token": access_token}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("nodes", {}).get(frame_id, {})
    return None 