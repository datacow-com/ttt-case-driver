from typing import List, Dict, Any
from utils.prompt_loader import PromptManager
from utils.cache_manager import cache_llm_call, cache_manager
import hashlib
import json

def build_prompt(system_prompt: str, few_shot_examples: list, current_input: str) -> str:
    prompt = system_prompt + '\n'
    for ex in few_shot_examples:
        prompt += f"示例输入:\n{ex['input']}\n示例输出:\n{ex['output']}\n"
    prompt += f"当前输入:\n{current_input}\n请生成输出："
    return prompt

def generate_cache_key(routes: Dict, testcases: List, prompt_template: str, few_shot_examples: list) -> str:
    """生成缓存键"""
    content = {
        "routes": routes,
        "testcases": testcases,
        "prompt_template": prompt_template,
        "few_shot_examples": few_shot_examples
    }
    return hashlib.md5(json.dumps(content, sort_keys=True).encode()).hexdigest()

@cache_llm_call(ttl=3600)  # 缓存LLM调用结果1小时
def generate_cross_page_case(routes: Dict[str, Any], testcases: List[Dict[str, Any]], llm_client, prompt_template: str = None, few_shot_examples: list = None) -> List[Dict[str, Any]]:
    """
    生成跨页面流程测试用例，支持prompt anchoring（带缓存）
    """
    # 生成缓存键
    cache_key = generate_cache_key(routes, testcases, prompt_template, few_shot_examples)
    
    # 检查缓存
    cached_result = cache_manager.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    prompt_manager = PromptManager()
    node_prompt = prompt_manager.get_prompt('generate_cross_page_case')
    system_prompt = prompt_template or node_prompt.get('system_prompt', '')
    few_shot = few_shot_examples or node_prompt.get('few_shot_examples', [])
    cross_page_cases = []
    for route in routes.get('routes', []):
        current_input = f"路由: {route}\n用例: {testcases}"
        prompt = build_prompt(system_prompt, few_shot, current_input)
        result = llm_client.generate(prompt)
        cross_page_cases.append({
            'route': route,
            'cross_page_case': result
        })
    
    # 缓存结果
    cache_manager.set(cache_key, cross_page_cases, ttl=3600)
    return cross_page_cases