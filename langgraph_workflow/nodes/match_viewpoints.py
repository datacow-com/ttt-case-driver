from typing import Dict, Any
import json

def match_viewpoints(clean_json: Dict[str, Any], viewpoints_db: Dict[str, Any]) -> Dict[str, Any]:
    """
    为每个组件匹配测试观点，输入为结构化简化后的JSON和观点库（JSON/YAML均可）
    """
    def traverse(node, results):
        if not node:
            return
        comp_type = node.get('type')
        viewpoints = viewpoints_db.get(comp_type, [])
        if viewpoints:
            results.append({
                'component': node,
                'viewpoints': viewpoints
            })
        for child in node.get('children', []):
            traverse(child, results)
    results = []
    traverse(clean_json, results)
    return {'component_viewpoints': results}
