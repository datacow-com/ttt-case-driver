from typing import Dict, Any, List
# 这里假设有一个 LLMClient 工具

def generate_testcases(component_viewpoints: Dict[str, Any], llm_client) -> List[Dict[str, Any]]:
    """
    调用LLM为每个组件-观点生成测试用例
    """
    testcases = []
    for comp_id, data in component_viewpoints.items():
        comp = data['component']
        for viewpoint in data['viewpoints']:
            prompt = f"组件: {comp['type']}\n名称: {comp.get('text', comp_id)}\n测试观点: {viewpoint}\n请生成测试用例步骤和预期结果。"
            result = llm_client.generate(prompt)
            testcases.append({
                'component_id': comp_id,
                'component': comp,
                'viewpoint': viewpoint,
                'testcase': result
            })
    return testcases
