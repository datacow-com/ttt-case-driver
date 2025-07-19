from typing import Dict, Any

def route_infer(clean_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    分析页面跳转，构建流程链，输入为结构化简化后的JSON
    """
    routes = []
    def traverse(node, page_name):
        if not node:
            return
        interaction = node.get('interaction')
        if interaction and 'goto' in interaction:
            routes.append({
                'from': page_name,
                'component_id': node.get('id'),
                'to': interaction['goto']
            })
        for child in node.get('children', []):
            traverse(child, page_name)
    # 假设顶层是页面
    if clean_json.get('type') == 'DOCUMENT' and 'children' in clean_json:
        for page in clean_json['children']:
            page_name = page.get('name', '')
            traverse(page, page_name)
    else:
        traverse(clean_json, clean_json.get('name', ''))
    return {'routes': routes}
