from typing import Dict, Any, List
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

def build_batch_prompt(components: List[Dict], system_prompt: str, few_shot_examples: list) -> str:
    """构建批量处理prompt"""
    prompt = system_prompt + '\n'
    
    # 添加few-shot示例
    for ex in few_shot_examples:
        prompt += f"示例输入:\n{ex['input']}\n示例输出:\n{ex['output']}\n"
    
    # 添加批量输入
    prompt += "当前输入（批量处理）:\n"
    for i, item in enumerate(components):
        comp = item['component']
        viewpoints = item['viewpoints']
        for j, viewpoint in enumerate(viewpoints):
            prompt += f"组件{i+1}-观点{j+1}: 组件类型={comp['type']}, 名称={comp.get('name', comp.get('id', ''))}, 测试观点={viewpoint}\n"
    
    prompt += "\n请为每个组件-观点组合生成测试用例，以JSON数组格式输出："
    return prompt

def parse_batch_result(batch_result: str, components: List[Dict]) -> List[Dict[str, Any]]:
    """解析批量结果"""
    try:
        # 尝试解析JSON结果
        if isinstance(batch_result, str):
            parsed_results = json.loads(batch_result)
        else:
            parsed_results = batch_result
        
        # 将结果映射回组件
        testcases = []
        result_index = 0
        
        for item in components:
            comp = item['component']
            viewpoints = item['viewpoints']
            
            for viewpoint in viewpoints:
                if result_index < len(parsed_results):
                    testcase = parsed_results[result_index]
                    testcases.append({
                        'component_id': comp.get('id', ''),
                        'component': comp,
                        'viewpoint': viewpoint,
                        'testcase': testcase
                    })
                    result_index += 1
                else:
                    # 如果结果不足，创建默认测试用例
                    testcases.append({
                        'component_id': comp.get('id', ''),
                        'component': comp,
                        'viewpoint': viewpoint,
                        'testcase': f"默认测试用例: {viewpoint}"
                    })
        
        return testcases
    except Exception as e:
        # 解析失败，回退到逐个处理
        return individual_process_components(components, None, None, None)

def individual_process_components(components: List[Dict], llm_client, prompt_template: str, few_shot_examples: list) -> List[Dict[str, Any]]:
    """逐个处理组件（原有逻辑）"""
    prompt_manager = PromptManager()
    node_prompt = prompt_manager.get_prompt('generate_testcases')
    system_prompt = prompt_template or node_prompt.get('system_prompt', '')
    few_shot = few_shot_examples or node_prompt.get('few_shot_examples', [])
    
    testcases = []
    for item in components:
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

def generate_cache_key(component_viewpoints: Dict, prompt_template: str, few_shot_examples: list) -> str:
    """生成缓存键"""
    content = {
        "component_viewpoints": component_viewpoints,
        "prompt_template": prompt_template,
        "few_shot_examples": few_shot_examples
    }
    return hashlib.md5(json.dumps(content, sort_keys=True).encode()).hexdigest()

@cache_llm_call(ttl=3600)  # 缓存LLM调用结果1小时
def generate_testcases(component_viewpoints: Dict[str, Any], llm_client, prompt_template: str = None, few_shot_examples: list = None) -> List[Dict[str, Any]]:
    """
    优化的测试用例生成，支持批量处理和缓存
    """
    # 生成缓存键
    cache_key = generate_cache_key(component_viewpoints, prompt_template, few_shot_examples)
    
    # 检查缓存
    cached_result = cache_manager.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    components = component_viewpoints.get('component_viewpoints', [])
    
    # 根据数据量选择处理策略
    if len(components) > 5:
        # 大数据量：批量处理
        result = batch_process_components(components, llm_client, prompt_template, few_shot_examples)
    else:
        # 小数据量：逐个处理
        result = individual_process_components(components, llm_client, prompt_template, few_shot_examples)
    
    # 缓存结果
    cache_manager.set(cache_key, result, ttl=3600)
    return result

def batch_process_components(components: List[Dict], llm_client, prompt_template: str, few_shot_examples: list) -> List[Dict[str, Any]]:
    """批量处理组件，减少API调用次数"""
    prompt_manager = PromptManager()
    node_prompt = prompt_manager.get_prompt('generate_testcases')
    system_prompt = prompt_template or node_prompt.get('system_prompt', '')
    few_shot = few_shot_examples or node_prompt.get('few_shot_examples', [])
    
    # 构建批量prompt
    batch_prompt = build_batch_prompt(components, system_prompt, few_shot)
    
    # 单次LLM调用生成所有测试用例
    batch_result = llm_client.generate(batch_prompt)
    
    # 解析批量结果
    return parse_batch_result(batch_result, components)