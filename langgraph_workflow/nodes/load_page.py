from typing import Dict, Any, List, Optional
import yaml
import json

def load_page(yaml_file_path: str) -> Dict[str, Any]:
    """
    解析页面结构YAML，返回页面结构对象
    """
    with open(yaml_file_path, 'r', encoding='utf-8') as f:
        page_structure = yaml.safe_load(f)
    return page_structure

def extract_frames(figma_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从Figma数据中提取所有Frame"""
    frames = []
    
    def traverse(node, parent_path=""):
        # 检查是否为Frame类型
        if node.get("type") == "FRAME" or node.get("type") == "COMPONENT":
            # 计算完整路径
            current_name = node.get("name", "未命名")
            current_path = f"{parent_path}/{current_name}" if parent_path else current_name
            
            frames.append({
                "id": node.get("id", ""),
                "name": current_name,
                "type": node.get("type", ""),
                "path": current_path,
                "children_count": len(node.get("children", [])),
                "has_interactive": has_interactive_children(node)
            })
        
        # 递归处理子节点
        if "children" in node:
            current_name = node.get("name", "")
            current_path = f"{parent_path}/{current_name}" if parent_path else current_name
            for child in node["children"]:
                traverse(child, current_path)
    
    # 开始遍历
    traverse(figma_data)
    return frames

def has_interactive_children(node: Dict[str, Any]) -> bool:
    """检查节点是否包含交互式组件"""
    interactive_types = ["INSTANCE", "COMPONENT", "BUTTON", "INPUT", "VECTOR"]
    
    if node.get("type") in interactive_types:
        return True
    
    if "children" in node:
        for child in node["children"]:
            if has_interactive_children(child):
                return True
    
    return False

def process_figma_data(figma_data: Dict[str, Any], selected_frames: Optional[List[str]] = None) -> Dict[str, Any]:
    """处理Figma数据，可选择性地只处理选定的Frame"""
    processed_data = {"components": [], "frames": [], "relationships": {}}
    
    # 提取组件和Frame
    components = []
    frames = []
    
    def traverse(node, parent_path="", parent_id=None):
        current_id = node.get("id", "")
        current_name = node.get("name", "")
        current_path = f"{parent_path}/{current_name}" if parent_path else current_name
        
        # 如果指定了selected_frames，只处理选定的Frame
        is_selected_frame = node.get("type") == "FRAME" and (
            selected_frames is None or current_id in selected_frames
        )
        
        # 处理Frame
        if node.get("type") == "FRAME":
            frame_info = {
                "id": current_id,
                "name": current_name,
                "path": current_path,
                "parent_id": parent_id,
                "selected": is_selected_frame
            }
            frames.append(frame_info)
            
            # 如果不是选定的Frame且指定了selected_frames，则跳过其子节点
            if selected_frames is not None and not is_selected_frame:
                return
        
        # 处理组件
        if is_component(node):
            component_info = {
                "id": current_id,
                "name": current_name,
                "type": node.get("type", ""),
                "path": current_path,
                "parent_id": parent_id,
                "properties": extract_essential_props(node)
            }
            components.append(component_info)
        
        # 递归处理子节点
        if "children" in node:
            for child in node["children"]:
                traverse(child, current_path, current_id)
    
    # 开始遍历
    traverse(figma_data)
    
    # 构建组件关系
    relationships = build_component_relationships(components)
    
    # 组装结果
    processed_data["components"] = components
    processed_data["frames"] = frames
    processed_data["relationships"] = relationships
    
    return processed_data

def is_component(node: Dict[str, Any]) -> bool:
    """判断节点是否为可测试组件"""
    testable_types = ["INSTANCE", "COMPONENT", "BUTTON", "INPUT", "TEXT", "VECTOR", "RECTANGLE"]
    return node.get("type") in testable_types or has_interactive_property(node)

def has_interactive_property(node: Dict[str, Any]) -> bool:
    """检查节点是否有交互属性"""
    # 检查是否有onClick、href等交互属性
    return any(prop in node for prop in ["onClick", "href", "interactions"])

def extract_essential_props(node: Dict[str, Any]) -> Dict[str, Any]:
    """提取组件的关键属性"""
    essential = {}
    key_props = ["id", "type", "name", "text", "value", "placeholder", "visible", "enabled", "onClick", "href"]
    
    for key in key_props:
        if key in node:
            essential[key] = node[key]
    
    return essential

def build_component_relationships(components: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """构建组件之间的关系"""
    relationships = {}
    
    # 创建ID到组件的映射
    id_to_component = {comp["id"]: comp for comp in components if "id" in comp}
    
    # 构建父子关系
    for comp in components:
        if "id" not in comp:
            continue
            
        comp_id = comp["id"]
        parent_id = comp.get("parent_id")
        
        if comp_id not in relationships:
            relationships[comp_id] = {"children": [], "parent": None}
        
        if parent_id:
            relationships[comp_id]["parent"] = parent_id
            
            if parent_id not in relationships:
                relationships[parent_id] = {"children": [], "parent": None}
                
            if comp_id not in relationships[parent_id]["children"]:
                relationships[parent_id]["children"].append(comp_id)
    
    return relationships
