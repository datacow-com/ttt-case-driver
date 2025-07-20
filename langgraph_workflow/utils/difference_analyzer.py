from typing import Dict, Any, List, Set, Tuple, Optional
import hashlib
from utils.intelligent_cache_manager import intelligent_cache_manager

class DifferenceAnalyzer:
    """差异分析器 - 比较Figma设计与历史测试模式"""
    
    @staticmethod
    def analyze_differences(figma_data: Dict[str, Any], historical_patterns: Dict[str, Any]) -> Dict[str, Any]:
        """分析Figma设计与历史测试模式的差异"""
        # 1. 提取Figma组件
        figma_components = DifferenceAnalyzer._extract_figma_components(figma_data)
        
        # 2. 提取历史测试模式中的组件
        historical_components = DifferenceAnalyzer._extract_historical_components(historical_patterns)
        
        # 3. 识别新增组件
        new_components = DifferenceAnalyzer._identify_new_components(figma_components, historical_components)
        
        # 4. 识别修改的组件
        modified_components = DifferenceAnalyzer._identify_modified_components(figma_components, historical_components)
        
        # 5. 识别删除的组件
        removed_components = DifferenceAnalyzer._identify_removed_components(figma_components, historical_components)
        
        # 6. 生成差异报告
        difference_report = {
            "new_components": new_components,
            "modified_components": modified_components,
            "removed_components": removed_components,
            "metadata": {
                "figma_component_count": len(figma_components),
                "historical_component_count": len(historical_components),
                "new_component_count": len(new_components),
                "modified_component_count": len(modified_components),
                "removed_component_count": len(removed_components)
            }
        }
        
        return difference_report
    
    @staticmethod
    def _extract_figma_components(figma_data: Dict[str, Any]) -> Dict[str, Any]:
        """从Figma数据中提取组件信息"""
        components = {}
        
        # 检查是否有document结构
        if 'document' in figma_data:
            figma_data = figma_data['document']
        
        # 处理页面
        pages = figma_data.get('children', [])
        for page in pages:
            page_name = page.get('name', '')
            page_id = page.get('id', '')
            
            # 处理页面中的框架
            frames = page.get('children', [])
            for frame in frames:
                frame_name = frame.get('name', '')
                frame_id = frame.get('id', '')
                
                # 处理框架中的组件
                DifferenceAnalyzer._process_frame_components(frame, components, page_name, frame_name)
        
        return components
    
    @staticmethod
    def _process_frame_components(frame: Dict[str, Any], components: Dict[str, Any], page_name: str, frame_name: str):
        """处理框架中的组件"""
        if 'children' not in frame:
            return
            
        for node in frame['children']:
            # 检查是否是组件
            if 'type' in node:
                component_type = DifferenceAnalyzer._map_figma_type_to_component_type(node['type'])
                if component_type:
                    component_id = node.get('id', '')
                    component_name = node.get('name', '')
                    
                    # 添加到组件字典
                    components[component_id] = {
                        "id": component_id,
                        "name": component_name,
                        "type": component_type,
                        "page_name": page_name,
                        "frame_name": frame_name,
                        "properties": DifferenceAnalyzer._extract_component_properties(node)
                    }
            
            # 递归处理子节点
            if 'children' in node:
                DifferenceAnalyzer._process_frame_components(node, components, page_name, frame_name)
    
    @staticmethod
    def _map_figma_type_to_component_type(figma_type: str) -> Optional[str]:
        """将Figma类型映射到标准组件类型"""
        mapping = {
            "RECTANGLE": "GENERAL",
            "TEXT": "TEXT",
            "VECTOR": "GENERAL",
            "INSTANCE": "COMPONENT",
            "COMPONENT": "COMPONENT",
            "FRAME": "CONTAINER",
            "GROUP": "CONTAINER",
            "ELLIPSE": "GENERAL",
            "STAR": "GENERAL",
            "LINE": "GENERAL",
            "REGULAR_POLYGON": "GENERAL",
            "BOOLEAN_OPERATION": "GENERAL",
            "SLICE": "GENERAL"
        }
        
        return mapping.get(figma_type, None)
    
    @staticmethod
    def _extract_component_properties(node: Dict[str, Any]) -> Dict[str, Any]:
        """提取组件属性"""
        properties = {}
        
        # 提取常见属性
        for prop in ['visible', 'opacity', 'blendMode', 'effects', 'fills', 'strokes']:
            if prop in node:
                properties[prop] = node[prop]
        
        # 提取文本特有属性
        if node.get('type') == 'TEXT' and 'characters' in node:
            properties['text'] = node['characters']
        
        # 提取尺寸和位置
        if 'absoluteBoundingBox' in node:
            bbox = node['absoluteBoundingBox']
            properties['position'] = {
                'x': bbox.get('x', 0),
                'y': bbox.get('y', 0)
            }
            properties['size'] = {
                'width': bbox.get('width', 0),
                'height': bbox.get('height', 0)
            }
        
        return properties
    
    @staticmethod
    def _extract_historical_components(historical_patterns: Dict[str, Any]) -> Dict[str, Any]:
        """从历史测试模式中提取组件信息"""
        components = {}
        
        # 提取组件模式
        component_patterns = historical_patterns.get('component_patterns', {})
        
        for component_type, patterns in component_patterns.items():
            # 为每种组件类型创建一个通用组件
            component_id = f"historical_{component_type.lower()}"
            components[component_id] = {
                "id": component_id,
                "name": f"Historical {component_type}",
                "type": component_type,
                "patterns": patterns,
                "is_historical": True
            }
        
        return components
    
    @staticmethod
    def _identify_new_components(figma_components: Dict[str, Any], historical_components: Dict[str, Any]) -> List[Dict[str, Any]]:
        """识别新增的组件"""
        new_components = []
        
        # 获取历史组件类型集合
        historical_component_types = {comp['type'] for comp in historical_components.values()}
        
        # 检查每个Figma组件
        for component_id, component in figma_components.items():
            component_type = component.get('type')
            
            # 如果组件类型在历史组件中不存在，则为新增组件
            if component_type not in historical_component_types:
                new_component = {
                    "id": component_id,
                    "name": component.get('name', ''),
                    "type": component_type,
                    "page_name": component.get('page_name', ''),
                    "frame_name": component.get('frame_name', ''),
                    "reason": "新组件类型"
                }
                new_components.append(new_component)
                continue
            
            # 检查组件名称是否包含"new"或"新"关键词
            component_name = component.get('name', '').lower()
            if 'new' in component_name or '新' in component_name:
                new_component = {
                    "id": component_id,
                    "name": component.get('name', ''),
                    "type": component_type,
                    "page_name": component.get('page_name', ''),
                    "frame_name": component.get('frame_name', ''),
                    "reason": "名称包含'new'或'新'"
                }
                new_components.append(new_component)
        
        return new_components
    
    @staticmethod
    def _identify_modified_components(figma_components: Dict[str, Any], historical_components: Dict[str, Any]) -> List[Dict[str, Any]]:
        """识别修改的组件"""
        modified_components = []
        
        # 获取历史组件类型映射
        historical_component_by_type = {}
        for comp_id, comp in historical_components.items():
            comp_type = comp.get('type')
            if comp_type:
                historical_component_by_type[comp_type] = comp
        
        # 检查每个Figma组件
        for component_id, component in figma_components.items():
            component_type = component.get('type')
            
            # 跳过新组件类型
            if component_type not in historical_component_by_type:
                continue
            
            # 检查组件名称是否包含"update"、"修改"、"改"等关键词
            component_name = component.get('name', '').lower()
            if any(kw in component_name for kw in ['update', 'modified', 'changed', '修改', '更新', '改']):
                modified_component = {
                    "id": component_id,
                    "name": component.get('name', ''),
                    "type": component_type,
                    "page_name": component.get('page_name', ''),
                    "frame_name": component.get('frame_name', ''),
                    "reason": "名称包含修改相关关键词"
                }
                modified_components.append(modified_component)
                continue
            
            # 检查组件属性是否与历史模式有显著差异
            # 这里简化处理，实际可能需要更复杂的比较
            properties = component.get('properties', {})
            if 'text' in properties:
                text = properties['text'].lower()
                if any(kw in text for kw in ['new', 'update', '新', '更新']):
                    modified_component = {
                        "id": component_id,
                        "name": component.get('name', ''),
                        "type": component_type,
                        "page_name": component.get('page_name', ''),
                        "frame_name": component.get('frame_name', ''),
                        "reason": "文本内容包含更新相关关键词"
                    }
                    modified_components.append(modified_component)
        
        return modified_components
    
    @staticmethod
    def _identify_removed_components(figma_components: Dict[str, Any], historical_components: Dict[str, Any]) -> List[Dict[str, Any]]:
        """识别删除的组件（在历史中有但在Figma中没有）"""
        removed_components = []
        
        # 获取Figma组件类型集合
        figma_component_types = {comp['type'] for comp in figma_components.values()}
        
        # 检查每个历史组件
        for component_id, component in historical_components.items():
            component_type = component.get('type')
            
            # 如果历史组件类型在Figma组件中不存在，则为删除的组件
            if component_type not in figma_component_types:
                removed_component = {
                    "id": component_id,
                    "name": component.get('name', ''),
                    "type": component_type,
                    "reason": "组件类型已删除"
                }
                removed_components.append(removed_component)
        
        return removed_components
    
    @staticmethod
    def analyze_with_cache(figma_data: Dict[str, Any], historical_patterns: Dict[str, Any], cache_key_prefix: str = None) -> Dict[str, Any]:
        """带缓存的差异分析"""
        # 生成缓存键
        if cache_key_prefix:
            cache_key = f"{cache_key_prefix}_differences"
        else:
            # 基于输入数据生成哈希
            input_str = str(len(figma_data)) + str(len(historical_patterns))
            input_hash = hashlib.md5(input_str.encode()).hexdigest()
            cache_key = f"differences_{input_hash}"
        
        # 检查缓存
        cached_differences = intelligent_cache_manager.get_with_intelligence(cache_key)
        if cached_differences is not None:
            return cached_differences
        
        # 分析差异
        differences = DifferenceAnalyzer.analyze_differences(figma_data, historical_patterns)
        
        # 缓存结果
        intelligent_cache_manager.set_with_intelligence(cache_key, differences, ttl=3600)
        
        return differences 