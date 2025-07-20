from typing import List, Dict, Any
from utils.prompt_loader import PromptManager
from utils.cache_manager import cache_llm_call, cache_manager
import hashlib
import json
from datetime import datetime
from utils.llm_client import SmartLLMClient

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
def generate_cross_page_case(routes: Dict[str, Any], testcases: Dict[str, Any], llm_client=None, 
                        prompt_template: str = None, few_shot_examples: list = None,
                        agent_name: str = "generate_cross_page_case") -> Dict[str, Any]:
    """
    生成跨页面测试用例
    
    Args:
        routes: 路由信息
        testcases: 组件级测试用例
        llm_client: LLM客户端
        prompt_template: 自定义提示模板
        few_shot_examples: Few-shot学习示例
        agent_name: 代理名称
        
    Returns:
        跨页面测试用例
    """
    # 提取测试用例列表
    testcase_list = []
    if isinstance(testcases, dict) and "testcases" in testcases:
        testcase_list = testcases["testcases"]
    else:
        testcase_list = testcases
    
    # 检查是否有优先级信息
    has_priority_info = False
    metadata = {}
    
    if isinstance(testcases, dict) and "metadata" in testcases:
        metadata = testcases["metadata"]
        if "viewpoints_analysis" in metadata and "priority_stats" in metadata["viewpoints_analysis"]:
            has_priority_info = True
    
    # 准备LLM客户端
    if llm_client is None:
        llm_client = SmartLLMClient(agent_name)
    
    # 获取提示模板
    prompt_manager = PromptManager()
    node_prompt = prompt_manager.get_prompt('generate_cross_page_case')
    system_prompt = prompt_template or node_prompt.get('system_prompt', '')
    few_shot = few_shot_examples or node_prompt.get('few_shot_examples', [])
    
    # 构建提示
    prompt = f"{system_prompt}\n\n"
    
    # 添加Few-shot示例
    for ex in few_shot:
        prompt += f"Example Input:\n{ex.get('input', '')}\nExample Output:\n{ex.get('output', '')}\n\n"
    
    # 构建当前输入
    current_input = {
        "routes": routes,
        "testcases": testcase_list
    }
    
    # 添加优先级信息（如果有）
    if has_priority_info:
        current_input["priority_info"] = metadata["viewpoints_analysis"]["priority_stats"]
    
    prompt += f"Current Input:\n{json.dumps(current_input, ensure_ascii=False)}\nOutput:"
    
    # 调用LLM
    result = llm_client.generate_sync(prompt)
    
    # 解析结果
    try:
        if isinstance(result, dict) and "content" in result:
            content = result["content"]
            parsed_result = json.loads(content)
        else:
            parsed_result = json.loads(result)
        
        # 添加元数据
        if isinstance(parsed_result, dict):
            if "metadata" not in parsed_result:
                parsed_result["metadata"] = {
                    "generation_time": datetime.now().isoformat(),
                    "source": "cross_page_generator"
                }
            
            # 如果有优先级信息，添加到结果中
            if has_priority_info:
                parsed_result["metadata"]["viewpoints_analysis"] = metadata.get("viewpoints_analysis", {})
        else:
            # 如果结果不是字典，包装成字典
            parsed_result = {
                "content": parsed_result,
                "metadata": {
                    "generation_time": datetime.now().isoformat(),
                    "source": "cross_page_generator"
                }
            }
        
        return parsed_result
    except Exception as e:
        print(f"解析跨页面测试用例结果时出错: {str(e)}")
        return {
            "content": result if isinstance(result, str) else str(result),
            "error": str(e),
            "metadata": {
                "generation_time": datetime.now().isoformat(),
                "source": "cross_page_generator",
                "status": "error"
            }
        }