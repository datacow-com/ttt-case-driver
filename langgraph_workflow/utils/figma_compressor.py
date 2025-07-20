from typing import Dict, Any, List, Set
import json
import hashlib
from collections import defaultdict

class FigmaCompressor:
    """Figma数据压缩工具 - 减少TOKEN使用"""
    
    def __init__(self):
        self.component_refs = {}  # 组件引用映射
        self.text_cache = {}  # 文本缓存
        self.attribute_cache = {}  # 属性缓存
    
    def compress_figma_data(self, figma_json: Dict[str, Any]) -> Dict[str, Any]:
        """压缩Figma数据，减少TOKEN使用"""
        # 重置缓存
        self.component_refs = {}
        self.text_cache = {}
        self.attribute_cache = {}
        
        # 深度复制避免修改原数据
        compressed = json.loads(json.dumps(figma_json))
        
        # 1. 移除不必要的属性
        compressed = self._remove_unnecessary_attributes(compressed)
        
        # 2. 压缩文本内容
        compressed = self._compress_text_content(compressed)
        
        # 3. 合并相似组件
        compressed = self._merge_similar_components(compressed)
        
        # 4. 使用引用而非重复数据
        compressed = self._use_references(compressed)
        
        # 5. 压缩坐标和尺寸信息
        compressed = self._compress_coordinates(compressed)
        
        return compressed
    
    def _remove_unnecessary_attributes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """移除不必要的属性"""
        # 定义需要保留的属性
        essential_attrs = {
            "id", "name", "type", "children", "characters", "componentId", 
            "text", "absoluteBoundingBox", "interaction", "fills", "strokes",
            "cornerRadius", "paddingLeft", "paddingRight", "paddingTop", "paddingBottom"
        }
        
        def clean_node(node):
            if not isinstance(node, dict):
                return node
            
            # 保留必要属性
            cleaned = {k: v for k, v in node.items() if k in essential_attrs}
            
            # 递归处理子节点
            if "children" in cleaned:
                cleaned["children"] = [clean_node(child) for child in cleaned["children"]]
            
            return cleaned
        
        return clean_node(data)
    
    def _compress_text_content(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """压缩文本内容"""
        def compress_text(node):
            if not isinstance(node, dict):
                return node
            
            # 压缩文本内容
            if "characters" in node and node["characters"]:
                text = node["characters"]
                if len(text) > 50:  # 长文本截断
                    text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
                    node["characters"] = text[:50] + f"...[{text_hash}]"
                    self.text_cache[text_hash] = text
            
            # 递归处理子节点
            if "children" in node:
                node["children"] = [compress_text(child) for child in node["children"]]
            
            return node
        
        return compress_text(data)
    
    def _merge_similar_components(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """合并相似组件"""
        component_groups = defaultdict(list)
        
        def collect_components(node, path=""):
            if not isinstance(node, dict):
                return
            
            if node.get("type") in ["COMPONENT", "INSTANCE"]:
                # 创建组件特征
                component_key = self._create_component_key(node)
                component_groups[component_key].append((node, path))
            
            if "children" in node:
                for i, child in enumerate(node["children"]):
                    collect_components(child, f"{path}.children[{i}]")
        
        collect_components(data)
        
        # 合并相似组件
        for component_key, components in component_groups.items():
            if len(components) > 1:
                # 保留第一个，其他使用引用
                reference_id = components[0][0]["id"]
                for node, path in components[1:]:
                    node["type"] = "REFERENCE"
                    node["referenceId"] = reference_id
                    # 移除重复属性
                    for attr in ["children", "fills", "strokes"]:
                        if attr in node:
                            del node[attr]
        
        return data
    
    def _create_component_key(self, node: Dict[str, Any]) -> str:
        """创建组件特征键"""
        key_parts = [
            node.get("type", ""),
            node.get("name", ""),
            str(node.get("cornerRadius", 0)),
            str(node.get("paddingLeft", 0)),
            str(node.get("paddingRight", 0)),
            str(node.get("paddingTop", 0)),
            str(node.get("paddingBottom", 0))
        ]
        return hashlib.md5("|".join(key_parts).encode()).hexdigest()
    
    def _use_references(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """使用引用而非重复数据"""
        attribute_refs = {}
        
        def create_references(node):
            if not isinstance(node, dict):
                return node
            
            # 创建属性引用
            if "fills" in node and node["fills"]:
                fills_key = hashlib.md5(json.dumps(node["fills"], sort_keys=True).encode()).hexdigest()[:8]
                if fills_key not in attribute_refs:
                    attribute_refs[fills_key] = node["fills"]
                node["fills"] = f"ref:{fills_key}"
            
            if "strokes" in node and node["strokes"]:
                strokes_key = hashlib.md5(json.dumps(node["strokes"], sort_keys=True).encode()).hexdigest()[:8]
                if strokes_key not in attribute_refs:
                    attribute_refs[strokes_key] = node["strokes"]
                node["strokes"] = f"ref:{strokes_key}"
            
            # 递归处理子节点
            if "children" in node:
                node["children"] = [create_references(child) for child in node["children"]]
            
            return node
        
        compressed = create_references(data)
        
        # 添加引用表
        if attribute_refs:
            compressed["_refs"] = attribute_refs
        
        return compressed
    
    def _compress_coordinates(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """压缩坐标和尺寸信息"""
        def compress_coords(node):
            if not isinstance(node, dict):
                return node
            
            # 压缩边界框
            if "absoluteBoundingBox" in node:
                bbox = node["absoluteBoundingBox"]
                if isinstance(bbox, dict):
                    # 四舍五入到整数
                    compressed_bbox = {
                        "x": round(bbox.get("x", 0)),
                        "y": round(bbox.get("y", 0)),
                        "width": round(bbox.get("width", 0)),
                        "height": round(bbox.get("height", 0))
                    }
                    node["absoluteBoundingBox"] = compressed_bbox
            
            # 递归处理子节点
            if "children" in node:
                node["children"] = [compress_coords(child) for child in node["children"]]
            
            return node
        
        return compress_coords(data)
    
    def decompress_figma_data(self, compressed_data: Dict[str, Any]) -> Dict[str, Any]:
        """解压缩Figma数据"""
        # 深度复制
        decompressed = json.loads(json.dumps(compressed_data))
        
        # 1. 恢复引用
        decompressed = self._restore_references(decompressed)
        
        # 2. 恢复文本内容
        decompressed = self._restore_text_content(decompressed)
        
        # 3. 恢复组件引用
        decompressed = self._restore_component_references(decompressed)
        
        return decompressed
    
    def _restore_references(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """恢复引用"""
        refs = data.get("_refs", {})
        
        def restore_refs(node):
            if not isinstance(node, dict):
                return node
            
            # 恢复属性引用
            if "fills" in node and isinstance(node["fills"], str) and node["fills"].startswith("ref:"):
                ref_key = node["fills"][4:]
                if ref_key in refs:
                    node["fills"] = refs[ref_key]
            
            if "strokes" in node and isinstance(node["strokes"], str) and node["strokes"].startswith("ref:"):
                ref_key = node["strokes"][4:]
                if ref_key in refs:
                    node["strokes"] = refs[ref_key]
            
            # 递归处理子节点
            if "children" in node:
                node["children"] = [restore_refs(child) for child in node["children"]]
            
            return node
        
        decompressed = restore_refs(data)
        
        # 移除引用表
        if "_refs" in decompressed:
            del decompressed["_refs"]
        
        return decompressed
    
    def _restore_text_content(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """恢复文本内容"""
        def restore_text(node):
            if not isinstance(node, dict):
                return node
            
            # 恢复文本内容
            if "characters" in node and isinstance(node["characters"], str):
                if "..." in node["characters"] and "[" in node["characters"]:
                    # 提取哈希并恢复完整文本
                    text_hash = node["characters"].split("[")[-1].split("]")[0]
                    if text_hash in self.text_cache:
                        node["characters"] = self.text_cache[text_hash]
            
            # 递归处理子节点
            if "children" in node:
                node["children"] = [restore_text(child) for child in node["children"]]
            
            return node
        
        return restore_text(data)
    
    def _restore_component_references(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """恢复组件引用"""
        # 这里可以实现组件引用的恢复逻辑
        # 由于复杂性较高，暂时返回原数据
        return data
    
    def get_compression_stats(self) -> Dict[str, Any]:
        """获取压缩统计信息"""
        return {
            "text_cache_size": len(self.text_cache),
            "attribute_cache_size": len(self.attribute_cache),
            "component_refs_size": len(self.component_refs)
        }

# 全局Figma压缩器实例
figma_compressor = FigmaCompressor()