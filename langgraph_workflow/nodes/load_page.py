from typing import Dict, Any, List, Optional, Tuple
import yaml
import json

def load_page(yaml_file_path: str) -> Dict[str, Any]:
    """
    解析页面结构YAML，返回页面结构对象
    """
    with open(yaml_file_path, 'r', encoding='utf-8') as f:
        page_structure = yaml.safe_load(f)
    return page_structure

def extract_pages_and_frames(figma_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """从Figma数据中提取所有Pages和Frames"""
    pages = []
    frames = []
    
    # 检查是否有document和children字段（标准Figma API格式）
    if "document" in figma_data and "children" in figma_data["document"]:
        # 处理标准Figma API格式
        for page_idx, page in enumerate(figma_data["document"]["children"]):
            if page.get("type") == "CANVAS":
                page_id = page.get("id", f"page_{page_idx}")
                page_name = page.get("name", f"Page {page_idx}")
                
                page_info = {
                    "id": page_id,
                    "name": page_name,
                    "type": "PAGE",
                    "children_count": len(page.get("children", [])),
                }
                pages.append(page_info)
                
                # 提取该页面中的所有Frame
                page_frames = extract_frames_from_node(page, page_name, page_id)
                frames.extend(page_frames)
    else:
        # 处理简化格式或自定义格式
        # 假设顶层是单个页面，或者直接是Frame列表
        root_name = figma_data.get("name", "Main Page")
        root_id = figma_data.get("id", "main_page")
        
        # 创建默认页面
        default_page = {
            "id": root_id,
            "name": root_name,
            "type": "PAGE",
            "children_count": len(figma_data.get("children", [])),
        }
        pages.append(default_page)
        
        # 提取Frame
        page_frames = extract_frames_from_node(figma_data, root_name, root_id)
        frames.extend(page_frames)
    
    return pages, frames

def extract_frames_from_node(node: Dict[str, Any], parent_path: str = "", page_id: str = None) -> List[Dict[str, Any]]:
    """从节点中递归提取所有Frame"""
    frames = []
    
    # 检查当前节点是否为Frame
    if node.get("type") == "FRAME" or node.get("type") == "COMPONENT" or node.get("type") == "COMPONENT_SET":
        current_name = node.get("name", "未命名")
        current_path = f"{parent_path}/{current_name}" if parent_path else current_name
        
        frames.append({
            "id": node.get("id", ""),
            "name": current_name,
            "type": node.get("type", ""),
            "path": current_path,
            "page_id": page_id,  # 记录所属页面ID
            "children_count": len(node.get("children", [])),
            "has_interactive": has_interactive_children(node)
        })
    
    # 递归处理子节点
    if "children" in node:
        current_name = node.get("name", "")
        current_path = f"{parent_path}/{current_name}" if parent_path else current_name
        
        for child in node["children"]:
            child_frames = extract_frames_from_node(child, current_path, page_id)
            frames.extend(child_frames)
    
    return frames

def extract_frames(figma_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从Figma数据中提取所有Frame（保留原有函数，调用新函数实现）"""
    _, frames = extract_pages_and_frames(figma_data)
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
    # 提取页面和Frame信息
    pages, all_frames = extract_pages_and_frames(figma_data)
    
    # 如果指定了selected_frames，过滤frames
    if selected_frames:
        frames = [frame for frame in all_frames if frame["id"] in selected_frames]
    else:
        frames = all_frames
    
    processed_data = {"pages": pages, "frames": frames, "components": [], "relationships": {}, "component_categories": {}}
    
    # 提取组件
    components = []
    component_categories = {}
    
    def traverse_for_components(node, parent_path="", parent_id=None, frame_id=None, page_id=None):
        current_id = node.get("id", "")
        current_name = node.get("name", "")
        current_path = f"{parent_path}/{current_name}" if parent_path else current_name
        
        # 如果是Frame，更新当前frame_id
        if node.get("type") == "FRAME" or node.get("type") == "COMPONENT" or node.get("type") == "COMPONENT_SET":
            frame_id = current_id
            
            # 如果指定了selected_frames且当前Frame不在其中，则跳过
            if selected_frames and frame_id not in selected_frames:
                return
        
        # 处理组件
        if is_component(node):
            component_info = {
                "id": current_id,
                "name": current_name,
                "type": node.get("type", ""),
                "path": current_path,
                "parent_id": parent_id,
                "frame_id": frame_id,
                "page_id": page_id,
                "properties": extract_essential_props(node)
            }
            components.append(component_info)
            
            # 按组件类型分类
            component_type = node.get("type", "UNKNOWN")
            if component_type not in component_categories:
                component_categories[component_type] = []
            component_categories[component_type].append(current_id)
            
            # 按组件特性分类
            categorize_component_by_features(node, current_id, component_categories)
        
        # 递归处理子节点
        if "children" in node:
            for child in node["children"]:
                traverse_for_components(child, current_path, current_id, frame_id, page_id)
    
    # 遍历Figma数据提取组件
    if "document" in figma_data:
        # 标准Figma API格式
        for page in figma_data["document"].get("children", []):
            page_id = page.get("id")
            traverse_for_components(page, "", None, None, page_id)
    else:
        # 简化格式
        traverse_for_components(figma_data)
    
    # 构建组件关系
    relationships = build_component_relationships(components)
    
    # 组装结果
    processed_data["components"] = components
    processed_data["relationships"] = relationships
    processed_data["component_categories"] = component_categories
    
    return processed_data

def categorize_component_by_features(node: Dict[str, Any], component_id: str, categories: Dict[str, List[str]]) -> None:
    """根据组件特性进行分类"""
    # 检查是否是可交互组件
    if has_interactive_property(node):
        if "INTERACTIVE" not in categories:
            categories["INTERACTIVE"] = []
        categories["INTERACTIVE"].append(component_id)
    
    # 检查是否是表单元素
    if node.get("type") in ["INPUT", "BUTTON", "CHECKBOX", "RADIO", "SELECT", "TEXTAREA"]:
        if "FORM_ELEMENT" not in categories:
            categories["FORM_ELEMENT"] = []
        categories["FORM_ELEMENT"].append(component_id)
    
    # 检查是否是文本组件
    if node.get("type") == "TEXT":
        if "TEXT" not in categories:
            categories["TEXT"] = []
        categories["TEXT"].append(component_id)
        
        # 进一步分类文本组件
        if "style" in node:
            font_size = node.get("style", {}).get("fontSize", 0)
            if font_size >= 24:
                if "HEADING" not in categories:
                    categories["HEADING"] = []
                categories["HEADING"].append(component_id)
            elif font_size <= 12:
                if "SMALL_TEXT" not in categories:
                    categories["SMALL_TEXT"] = []
                categories["SMALL_TEXT"].append(component_id)
    
    # 检查是否是容器
    if "children" in node and len(node.get("children", [])) > 0:
        if "CONTAINER" not in categories:
            categories["CONTAINER"] = []
        categories["CONTAINER"].append(component_id)
    
    # 检查是否是图像
    if node.get("type") in ["IMAGE", "VECTOR"] or "fills" in node and any(fill.get("type") == "IMAGE" for fill in node.get("fills", [])):
        if "IMAGE" not in categories:
            categories["IMAGE"] = []
        categories["IMAGE"].append(component_id)

def is_component(node: Dict[str, Any]) -> bool:
    """判断节点是否为可测试组件"""
    testable_types = [
        "INSTANCE", "COMPONENT", "BUTTON", "INPUT", "TEXT", "VECTOR", 
        "RECTANGLE", "GROUP", "BOOLEAN_OPERATION", "CHECKBOX", "RADIO",
        "SELECT", "TEXTAREA", "IMAGE", "ELLIPSE", "POLYGON"
    ]
    return node.get("type") in testable_types or has_interactive_property(node)

def has_interactive_property(node: Dict[str, Any]) -> bool:
    """检查节点是否有交互属性"""
    # 检查是否有onClick、href等交互属性
    interactive_props = ["onClick", "href", "interactions", "reaction", "actions", "hyperlink"]
    return any(prop in node for prop in interactive_props)

def extract_essential_props(node: Dict[str, Any]) -> Dict[str, Any]:
    """提取组件的关键属性"""
    essential = {}
    key_props = [
        "id", "type", "name", "text", "value", "placeholder", "visible", "enabled", 
        "onClick", "href", "interactions", "reaction", "actions", "opacity", "blendMode",
        "effectStyleId", "strokeStyleId", "fillStyleId", "textStyleId"
    ]
    
    for key in key_props:
        if key in node:
            essential[key] = node[key]
    
    # 提取特定类型组件的特殊属性
    if node.get("type") == "TEXT":
        if "style" in node:
            essential["style"] = {
                k: v for k, v in node["style"].items() 
                if k in ["fontFamily", "fontSize", "fontWeight", "textAlignHorizontal", "textAlignVertical", "letterSpacing", "lineHeight"]
            }
    
    # 提取填充属性
    if "fills" in node:
        essential["fills"] = []
        for fill in node.get("fills", []):
            if fill.get("visible", True) != False:  # 只保留可见的填充
                essential["fills"].append({
                    "type": fill.get("type"),
                    "color": fill.get("color") if fill.get("type") == "SOLID" else None,
                    "imageRef": fill.get("imageRef") if fill.get("type") == "IMAGE" else None
                })
    
    # 提取描边属性
    if "strokes" in node:
        essential["strokes"] = []
        for stroke in node.get("strokes", []):
            if stroke.get("visible", True) != False:  # 只保留可见的描边
                essential["strokes"].append({
                    "type": stroke.get("type"),
                    "color": stroke.get("color") if stroke.get("type") == "SOLID" else None,
                    "weight": node.get("strokeWeight")
                })
    
    # 提取布局约束
    if "constraints" in node:
        essential["constraints"] = node["constraints"]
    
    # 提取自动布局属性
    if "layoutMode" in node:
        essential["layout"] = {
            "mode": node.get("layoutMode"),
            "padding": node.get("padding"),
            "spacing": node.get("itemSpacing")
        }
    
    return essential

def build_component_relationships(components: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """构建组件之间的关系"""
    relationships = {}
    
    # 创建ID到组件的映射
    id_to_component = {comp["id"]: comp for comp in components if "id" in comp}
    
    # 按Frame和Page组织组件
    frame_components = {}
    page_components = {}
    
    for comp in components:
        if "id" not in comp:
            continue
            
        comp_id = comp["id"]
        parent_id = comp.get("parent_id")
        frame_id = comp.get("frame_id")
        page_id = comp.get("page_id")
        
        # 初始化关系结构
        if comp_id not in relationships:
            relationships[comp_id] = {
                "children": [], 
                "parent": None,
                "frame_id": frame_id,
                "page_id": page_id,
                "siblings": []
            }
        else:
            # 更新Frame和Page信息
            relationships[comp_id]["frame_id"] = frame_id
            relationships[comp_id]["page_id"] = page_id
        
        # 按Frame组织
        if frame_id:
            if frame_id not in frame_components:
                frame_components[frame_id] = []
            frame_components[frame_id].append(comp_id)
        
        # 按Page组织
        if page_id:
            if page_id not in page_components:
                page_components[page_id] = []
            page_components[page_id].append(comp_id)
        
        # 建立父子关系
        if parent_id:
            relationships[comp_id]["parent"] = parent_id
            
            if parent_id not in relationships:
                relationships[parent_id] = {
                    "children": [], 
                    "parent": None,
                    "frame_id": frame_id,
                    "page_id": page_id,
                    "siblings": []
                }
                
            if comp_id not in relationships[parent_id]["children"]:
                relationships[parent_id]["children"].append(comp_id)
    
    # 添加兄弟关系
    for comp_id, rel in relationships.items():
        parent_id = rel["parent"]
        if parent_id and parent_id in relationships:
            # 获取所有兄弟（同一父节点的其他子节点）
            siblings = [
                child_id for child_id in relationships[parent_id]["children"]
                if child_id != comp_id
            ]
            relationships[comp_id]["siblings"] = siblings
    
    # 添加Frame和Page索引到关系数据中
    relationships["_frame_index"] = frame_components
    relationships["_page_index"] = page_components
    
    return relationships
