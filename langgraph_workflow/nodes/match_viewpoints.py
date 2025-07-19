from typing import Dict, Any
import yaml

def match_viewpoints(page_structure: Dict[str, Any], viewpoints_db_path: str) -> Dict[str, Any]:
    """
    为每个组件匹配测试观点
    """
    with open(viewpoints_db_path, 'r', encoding='utf-8') as f:
        viewpoints_db = yaml.safe_load(f)
    # 简单示例：按组件类型匹配观点
    component_viewpoints = {}
    for comp in page_structure.get('components', []):
        comp_type = comp.get('type')
        viewpoints = viewpoints_db.get(comp_type, [])
        component_viewpoints[comp['id']] = {
            'component': comp,
            'viewpoints': viewpoints
        }
    return component_viewpoints
