from typing import Dict, Any
from utils.prompt_loader import PromptManager

def build_prompt(system_prompt: str, few_shot_examples: list, current_input: str) -> str:
    prompt = system_prompt + '\n'
    for ex in few_shot_examples:
        prompt += f"示例输入:\n{ex['input']}\n示例输出:\n{ex['output']}\n"
    prompt += f"当前输入:\n{current_input}\n请生成输出："
    return prompt

def match_viewpoints(clean_json: Dict[str, Any], viewpoints_db: Dict[str, Any], llm_client=None, prompt_template: str = None, few_shot_examples: list = None) -> Dict[str, Any]:
    """
    为每个组件匹配测试观点，支持LLM智能匹配
    """
    if llm_client:
        # 使用LLM智能匹配
        prompt_manager = PromptManager()
        node_prompt = prompt_manager.get_prompt('match_viewpoints')
        system_prompt = prompt_template or node_prompt.get('system_prompt', '')
        few_shot = few_shot_examples or node_prompt.get('few_shot_examples', [])
        
        results = []
        def traverse(node):
            if not node:
                return
            comp_type = node.get('type')
            comp_name = node.get('name', node.get('id', ''))
            available_viewpoints = viewpoints_db.get(comp_type, [])
            
            if available_viewpoints:
                current_input = f"组件类型: {comp_type}\n组件名称: {comp_name}\n组件属性: {node}\n观点库: {available_viewpoints}"
                prompt = build_prompt(system_prompt, few_shot, current_input)
                llm_result = llm_client.generate(prompt)
                # 解析LLM返回的JSON数组
                try:
                    matched_viewpoints = eval(llm_result.get('steps', '[]'))
                    if matched_viewpoints:
                        results.append({
                            'component': node,
                            'viewpoints': matched_viewpoints
                        })
                    else:
                        # 如果LLM返回空数组，使用默认匹配
                        results.append({
                            'component': node,
                            'viewpoints': available_viewpoints
                        })
                except:
                    # 如果LLM解析失败，使用默认匹配
                    results.append({
                        'component': node,
                        'viewpoints': available_viewpoints
                    })
            
            for child in node.get('children', []):
                traverse(child)
        
        traverse(clean_json)
        return {'component_viewpoints': results}
    else:
        # 原有的规则匹配逻辑
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