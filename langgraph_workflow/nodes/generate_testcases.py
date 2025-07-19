from typing import Dict, Any, List
from utils.prompt_loader import PromptManager

def build_prompt(system_prompt: str, few_shot_examples: list, current_input: str) -> str:
    prompt = system_prompt + '\n'
    for ex in few_shot_examples:
        prompt += f"示例输入:\n{ex['input']}\n示例输出:\n{ex['output']}\n"
    prompt += f"当前输入:\n{current_input}\n请生成输出："
    return prompt

def generate_testcases(component_viewpoints: Dict[str, Any], llm_client, prompt_template: str = None, few_shot_examples: list = None) -> List[Dict[str, Any]]:
    """
    调用LLM为每个组件-观点生成测试用例，支持prompt anchoring
    """
    prompt_manager = PromptManager()
    node_prompt = prompt_manager.get_prompt('generate_testcases')
    system_prompt = prompt_template or node_prompt.get('system_prompt', '')
    few_shot = few_shot_examples or node_prompt.get('few_shot_examples', [])
    testcases = []
    for item in component_viewpoints.get('component_viewpoints', []):
        comp = item['component']
        for viewpoint in item['viewpoints']:
            current_input = f"组件: {comp['type']}\n名称: {comp.get('name', comp.get('id', ''))}\n测试观点: {viewpoint}"
            prompt = build_prompt(system_prompt, few_shot, current_input)
            result = llm_client.generate(prompt)
            testcases.append({
                'component_id': comp.get('id', ''),
                'component': comp,
                'viewpoint': viewpoint,
                'testcase': result
            })
    return testcases
