from typing import List, Dict, Any
# 这里假设有一个 LLMClient 工具

def generate_cross_page_case(routes: Dict[str, Any], testcases: List[Dict[str, Any]], llm_client) -> List[Dict[str, Any]]:
    """
    生成跨页面流程测试用例
    """
    cross_page_cases = []
    # 简单示例：每条路由链生成一个跨页用例
    for route in routes.get('routes', []):
        prompt = f"请基于以下页面跳转链和已有用例，生成完整的跨页面流程测试用例：\n路由: {route}\n用例: {testcases}"
        result = llm_client.generate(prompt)
        cross_page_cases.append({
            'route': route,
            'cross_page_case': result
        })
    return cross_page_cases
