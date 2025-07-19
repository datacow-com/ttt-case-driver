from typing import Dict, Any, List
# 这里假设有一个 LLMClient 工具

def generate_testcases(component_viewpoints: Dict[str, Any], llm_client) -> List[Dict[str, Any]]:
    """
    调用LLM为每个组件-观点生成测试用例，输入为结构化JSON
    """
    testcases = []
    for item in component_viewpoints.get('component_viewpoints', []):
        comp = item['component']
        for viewpoint in item['viewpoints']:
            prompt = f"组件: {comp['type']}\n名称: {comp.get('name', comp.get('id', ''))}\n测试观点: {viewpoint}\n请生成测试用例步骤和预期结果。"
            result = llm_client.generate(prompt)
            testcases.append({
                'component_id': comp.get('id', ''),
                'component': comp,
                'viewpoint': viewpoint,
                'testcase': result
            })
    return testcases
