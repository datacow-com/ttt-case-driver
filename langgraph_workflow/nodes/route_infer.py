from typing import Dict, Any
from utils.prompt_loader import PromptManager

def build_prompt(system_prompt: str, few_shot_examples: list, current_input: str) -> str:
    prompt = system_prompt + '\n'
    for ex in few_shot_examples:
        prompt += f"示例输入:\n{ex['input']}\n示例输出:\n{ex['output']}\n"
    prompt += f"当前输入:\n{current_input}\n请生成输出："
    return prompt

def route_infer(clean_json: Dict[str, Any], llm_client=None, prompt_template: str = None, few_shot_examples: list = None) -> Dict[str, Any]:
    """
    分析页面跳转，构建流程链，支持LLM智能分析
    """
    if llm_client:
        # 使用LLM智能分析
        prompt_manager = PromptManager()
        node_prompt = prompt_manager.get_prompt('route_infer')
        system_prompt = prompt_template or node_prompt.get('system_prompt', '')
        few_shot = few_shot_examples or node_prompt.get('few_shot_examples', [])
        
        current_input = f"页面结构: {clean_json}"
        prompt = build_prompt(system_prompt, few_shot, current_input)
        llm_result = llm_client.generate(prompt)
        
        try:
            routes = eval(llm_result.get('steps', '[]'))
            if routes:
                return {'routes': routes}
            # 如果LLM返回空数组，使用原有逻辑
        except:
            # 如果LLM解析失败，使用原有逻辑
            pass
    
    # 原有的规则分析逻辑
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
    
    if clean_json.get('type') == 'DOCUMENT' and 'children' in clean_json:
        for page in clean_json['children']:
            page_name = page.get('name', '')
            traverse(page, page_name)
    else:
        traverse(clean_json, clean_json.get('name', ''))
    
    return {'routes': routes}