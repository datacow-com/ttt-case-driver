from typing import Dict, Any, List, Optional, Tuple
import requests
import json
from ..utils.cache_manager import cache_result, cache_manager
from ..utils.figma_compressor import figma_compressor
from ..utils.intelligent_cache_manager import intelligent_cache_manager
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 从load_page.py复制的函数
def extract_pages_and_frames(figma_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    从Figma数据中提取页面和Frame信息
    
    Args:
        figma_data: Figma JSON数据
        
    Returns:
        (pages, frames): 页面列表和Frame列表
    """
    pages = []
    frames = []
    
    # 获取文档数据
    document = figma_data.get("document", {})
    
    # 处理页面
    for page in document.get("children", []):
        if page.get("type") == "CANVAS":
            page_id = page.get("id")
            page_name = page.get("name")
            
            # 添加页面信息
            pages.append({
                "id": page_id,
                "name": page_name,
                "type": "PAGE",
                "children_count": len(page.get("children", []))
            })
            
            # 提取页面中的Frame
            extract_frames_from_node(page, frames, page_id=page_id, page_name=page_name)
    
    return pages, frames

def extract_frames_from_node(node: Dict[str, Any], frames: List[Dict[str, Any]], page_id: str = None, page_name: str = None, parent_path: str = "", parent_id: str = None):
    """
    递归提取节点中的Frame
    
    Args:
        node: 节点数据
        frames: Frame列表（会被修改）
        page_id: 页面ID
        page_name: 页面名称
        parent_path: 父节点路径
        parent_id: 父节点ID
    """
    node_type = node.get("type")
    node_id = node.get("id")
    node_name = node.get("name", "")
    
    # 构建当前节点路径
    current_path = f"{parent_path}/{node_name}" if parent_path else node_name
    
    # 检查是否为Frame或Component
    if node_type in ["FRAME", "COMPONENT", "COMPONENT_SET", "INSTANCE"]:
        # 检查是否有交互元素
        has_interactive = False
        if "children" in node:
            for child in node["children"]:
                if child.get("type") in ["INSTANCE", "COMPONENT"] or "reactions" in child:
                    has_interactive = True
                    break
        
        # 添加Frame信息
        frames.append({
            "id": node_id,
            "name": node_name,
            "type": node_type,
            "path": current_path,
            "page_id": page_id,
            "page_name": page_name,
            "parent_id": parent_id,
            "children_count": len(node.get("children", [])),
            "has_interactive": has_interactive
        })
    
    # 递归处理子节点
    for child in node.get("children", []):
        extract_frames_from_node(
            child, frames, page_id, page_name, current_path, node_id
        )

def process_figma_data(figma_data: Dict[str, Any], selected_frames: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    处理Figma数据，提取组件和关系
    
    Args:
        figma_data: Figma JSON数据
        selected_frames: 选定的Frame ID列表（如果提供，只处理这些Frame）
        
    Returns:
        处理后的数据，包含页面、Frame、组件和关系
    """
    # 提取页面和Frame
    pages, frames = extract_pages_and_frames(figma_data)
    
    # 如果提供了选定Frame，过滤Frame列表
    if selected_frames:
        frames = [f for f in frames if f.get("id") in selected_frames]
    
    # 提取组件
    components = []
    component_categories = {}
    
    # 处理每个Frame
    for frame in frames:
        frame_id = frame.get("id")
        
        # 在原始数据中找到对应的Frame节点
        frame_node = find_node_by_id(figma_data.get("document", {}), frame_id)
        if not frame_node:
            continue
        
        # 提取Frame中的组件
        extract_components_from_node(
            frame_node, 
            components, 
            component_categories,
            frame_id=frame_id,
            page_id=frame.get("page_id"),
            parent_path=frame.get("path", ""),
            parent_id=frame_id
        )
    
    # 构建组件间关系
    relationships = build_relationships(components)
    
    # 返回处理后的数据
    return {
        "pages": pages,
        "frames": frames,
        "components": components,
        "component_categories": component_categories,
        "relationships": relationships
    }

def find_node_by_id(node: Dict[str, Any], node_id: str) -> Optional[Dict[str, Any]]:
    """
    在节点树中查找指定ID的节点
    
    Args:
        node: 当前节点
        node_id: 要查找的节点ID
        
    Returns:
        找到的节点，如果未找到则返回None
    """
    # 检查当前节点
    if node.get("id") == node_id:
        return node
    
    # 递归查找子节点
    for child in node.get("children", []):
        found = find_node_by_id(child, node_id)
        if found:
            return found
    
    return None

def extract_components_from_node(
    node: Dict[str, Any], 
    components: List[Dict[str, Any]], 
    component_categories: Dict[str, List[str]],
    frame_id: str = None,
    page_id: str = None,
    parent_path: str = "",
    parent_id: str = None
):
    """
    递归提取节点中的组件
    
    Args:
        node: 节点数据
        components: 组件列表（会被修改）
        component_categories: 组件分类（会被修改）
        frame_id: Frame ID
        page_id: 页面ID
        parent_path: 父节点路径
        parent_id: 父节点ID
    """
    node_type = node.get("type")
    node_id = node.get("id")
    node_name = node.get("name", "")
    
    # 构建当前节点路径
    current_path = f"{parent_path}/{node_name}" if parent_path else node_name
    
    # 提取组件属性
    properties = extract_component_properties(node)
    
    # 检查是否为交互组件
    is_interactive = (
        "reactions" in node or 
        node_type in ["INSTANCE", "COMPONENT"] or
        properties.get("has_link") or
        properties.get("has_action")
    )
    
    # 如果是有意义的组件，添加到列表
    if node_type not in ["DOCUMENT", "CANVAS", "FRAME"] and node_id:
        # 创建组件对象
        component = {
            "id": node_id,
            "name": node_name,
            "type": node_type,
            "path": current_path,
            "parent_id": parent_id,
            "frame_id": frame_id,
            "page_id": page_id,
            "properties": properties
        }
        
        # 添加到组件列表
        components.append(component)
        
        # 添加到分类
        add_to_category(component_categories, node_type, node_id)
        if is_interactive:
            add_to_category(component_categories, "INTERACTIVE", node_id)
    
    # 递归处理子节点
    for child in node.get("children", []):
        extract_components_from_node(
            child, components, component_categories,
            frame_id, page_id, current_path, node_id
        )

def extract_component_properties(node: Dict[str, Any]) -> Dict[str, Any]:
    """
    提取组件的属性
    
    Args:
        node: 组件节点
        
    Returns:
        组件属性字典
    """
    properties = {}
    
    # 提取文本内容
    if "characters" in node:
        properties["text"] = node["characters"]
    
    # 提取填充颜色
    if "fills" in node and node["fills"]:
        fills = []
        for fill in node["fills"]:
            if fill.get("visible", True) and fill.get("type") == "SOLID":
                color = fill.get("color", {})
                fills.append({
                    "r": int(color.get("r", 0) * 255),
                    "g": int(color.get("g", 0) * 255),
                    "b": int(color.get("b", 0) * 255),
                    "a": color.get("a", 1)
                })
        if fills:
            properties["fills"] = fills
    
    # 提取交互信息
    if "reactions" in node:
        interactions = []
        for reaction in node["reactions"]:
            action = reaction.get("action", {})
            interactions.append({
                "type": reaction.get("trigger", "CLICK"),
                "action": action.get("type"),
                "target": action.get("destinationId") if "destinationId" in action else None
            })
        if interactions:
            properties["interactions"] = interactions
    
    return properties

def add_to_category(categories: Dict[str, List[str]], category: str, component_id: str):
    """
    将组件添加到分类
    
    Args:
        categories: 分类字典
        category: 分类名称
        component_id: 组件ID
    """
    if category not in categories:
        categories[category] = []
    categories[category].append(component_id)

def build_relationships(components: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    构建组件间的关系
    
    Args:
        components: 组件列表
        
    Returns:
        关系字典
    """
    relationships = {}
    
    # 构建父子关系和兄弟关系
    for component in components:
        component_id = component.get("id")
        parent_id = component.get("parent_id")
        
        # 初始化关系对象
        if component_id not in relationships:
            relationships[component_id] = {
                "children": [],
                "parent": None,
                "siblings": []
            }
        
        # 设置父节点
        if parent_id:
            relationships[component_id]["parent"] = parent_id
            
            # 更新父节点的子节点列表
            if parent_id not in relationships:
                relationships[parent_id] = {
                    "children": [component_id],
                    "parent": None,
                    "siblings": []
                }
            else:
                relationships[parent_id]["children"].append(component_id)
    
    # 构建兄弟关系
    for component_id, relation in relationships.items():
        parent_id = relation.get("parent")
        if parent_id and parent_id in relationships:
            # 获取所有具有相同父节点的组件
            siblings = [
                sibling_id for sibling_id in relationships[parent_id]["children"]
                if sibling_id != component_id
            ]
            relation["siblings"] = siblings
    
    return relationships

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
        
        # 处理Figma数据
        logging.info("处理Figma数据")
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
        raise

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