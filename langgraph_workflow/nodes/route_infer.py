from typing import Dict, Any

def route_infer(page_structure: Dict[str, Any]) -> Dict[str, Any]:
    """
    分析页面跳转，构建流程链
    """
    routes = []
    for comp in page_structure.get('components', []):
        interaction = comp.get('interaction')
        if interaction and 'goto' in interaction:
            routes.append({
                'from': page_structure.get('page'),
                'component_id': comp['id'],
                'to': interaction['goto']
            })
    return {'routes': routes}
