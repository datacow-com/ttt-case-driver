from typing import Dict, Any, List, Tuple, Optional
from utils.prompt_loader import PromptManager
from utils.cache_manager import cache_llm_call, cache_manager
from utils.llm_client_factory import SmartLLMClient
import hashlib
import json
import time
import re
from functools import lru_cache
import concurrent.futures
from collections import defaultdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==================== 1. 智能批处理策略 ====================

def estimate_tokens(component: Dict) -> int:
    """估算组件需要的token数量"""
    # 简单估算：组件类型和名称的长度 + 属性数量 * 10
    base_tokens = len(str(component.get('type', ''))) + len(str(component.get('name', component.get('id', ''))))
    props_tokens = len(component.keys()) * 10
    return base_tokens + props_tokens

def group_components_by_type(components: List[Dict]) -> Dict[str, List[Dict]]:
    """按组件类型分组，便于批处理
    
    Args:
        components: 组件列表
        
    Returns:
        按组件类型分组的字典
    """
    groups = defaultdict(list)
    for item in components:
        comp_type = item['component'].get('type', 'unknown')
        groups[comp_type].append(item)
    return dict(groups)

def smart_batch_processing(components: List[Dict], llm_client, prompt_template: str = None, 
                         few_shot_examples: list = None, agent_name: str = "generate_testcases",
                         max_workers: int = 4, parallel: bool = True) -> List[Dict[str, Any]]:
    """智能批处理策略，支持并行处理
    
    Args:
        components: 组件列表
        llm_client: LLM客户端
        prompt_template: 自定义提示模板
        few_shot_examples: Few-shot学习示例
        agent_name: 代理名称
        max_workers: 最大并行工作线程数
        parallel: 是否启用并行处理
        
    Returns:
        生成的测试用例列表
    """
    # 如果组件数量很少，不使用并行处理
    if len(components) <= 2 or not parallel:
        return _sequential_batch_processing(components, llm_client, prompt_template, few_shot_examples, agent_name)
    
    # 按组件类型分组，便于批处理
    component_groups = group_components_by_type(components)
    
    # 估算每个组件的token数量
    group_tokens = {}
    for group_type, group_components in component_groups.items():
        total_tokens = 0
        for item in group_components:
            comp = item['component']
            viewpoints = item['viewpoints']
            # 每个观点的估算token数
            for _ in viewpoints:
                total_tokens += estimate_tokens(comp)
        group_tokens[group_type] = total_tokens
    
    # 动态调整批大小
    batch_sizes = {}
    for group_type, tokens in group_tokens.items():
        avg_tokens = tokens / len(component_groups[group_type])
        # 目标保持在4000 tokens以内
        target_tokens = 4000
        batch_sizes[group_type] = max(1, min(20, int(target_tokens / avg_tokens)))
    
    # 准备并行处理任务
    all_batches = []
    for group_type, group_components in component_groups.items():
        batch_size = batch_sizes.get(group_type, 5)  # 默认批大小为5
        
        # 分批
        for i in range(0, len(group_components), batch_size):
            batch = group_components[i:i+batch_size]
            all_batches.append(batch)
    
    # 并行处理各批次
    all_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交任务
        future_to_batch = {
            executor.submit(
                batch_process_components, 
                batch, 
                llm_client, 
                prompt_template, 
                few_shot_examples, 
                agent_name
            ): batch for batch in all_batches
        }
        
        # 收集结果
        for future in concurrent.futures.as_completed(future_to_batch):
            batch = future_to_batch[future]
            try:
                batch_results = future.result()
                all_results.extend(batch_results)
            except Exception as e:
                print(f"批处理失败，降级到单个处理: {str(e)}")
                # 批处理失败时降级到单个处理
                for item in batch:
                    try:
                        individual_results = individual_process_components([item], llm_client, prompt_template, few_shot_examples, agent_name)
                        all_results.extend(individual_results)
                    except Exception as inner_e:
                        print(f"单个处理失败: {str(inner_e)}")
                        # 创建默认结果
                        comp = item['component']
                        for viewpoint in item['viewpoints']:
                            all_results.append({
                                'component_id': comp.get('id', ''),
                                'component': comp,
                                'viewpoint': viewpoint,
                                'testcase': f"Default test case for {viewpoint} (处理失败: {str(inner_e)})"
                            })
    
    return all_results

def _sequential_batch_processing(components: List[Dict], llm_client, prompt_template: str = None, 
                              few_shot_examples: list = None, agent_name: str = "generate_testcases") -> List[Dict[str, Any]]:
    """顺序批处理（原始实现）"""
    # 估算每个组件的token数量
    component_tokens = []
    for item in components:
        comp = item['component']
        viewpoints = item['viewpoints']
        # 每个观点的估算token数
        for _ in viewpoints:
            component_tokens.append(estimate_tokens(comp))
    
    # 计算平均每个组件-观点对的token数
    avg_tokens_per_item = sum(component_tokens) / len(component_tokens) if component_tokens else 100
    
    # 动态计算最佳批大小 (目标保持在4000 tokens以内)
    target_tokens = 4000
    optimal_batch_size = max(1, min(20, int(target_tokens / avg_tokens_per_item)))
    
    # 分批处理
    all_results = []
    for i in range(0, len(components), optimal_batch_size):
        batch = components[i:i+optimal_batch_size]
        try:
            # 尝试批处理
            batch_results = batch_process_components(batch, llm_client, prompt_template, few_shot_examples, agent_name)
            all_results.extend(batch_results)
        except Exception as e:
            print(f"批处理失败，降级到单个处理: {str(e)}")
            # 批处理失败时降级到单个处理
            for item in batch:
                try:
                    individual_results = individual_process_components([item], llm_client, prompt_template, few_shot_examples, agent_name)
                    all_results.extend(individual_results)
                except Exception as inner_e:
                    print(f"单个处理失败: {str(inner_e)}")
                    # 创建默认结果
                    comp = item['component']
                    for viewpoint in item['viewpoints']:
                        all_results.append({
                            'component_id': comp.get('id', ''),
                            'component': comp,
                            'viewpoint': viewpoint,
                            'testcase': f"Default test case for {viewpoint} (处理失败: {str(inner_e)})"
                        })
    
    return all_results

# ==================== 2. 增强缓存机制 ====================

def extract_core_content(prompt: str) -> str:
    """提取提示中的核心内容"""
    # 移除系统提示和few-shot示例部分
    if "Current Input" in prompt:
        parts = prompt.split("Current Input")
        if len(parts) > 1:
            return "Current Input" + parts[1]
    return prompt

def normalize_content(text: str) -> str:
    """规范化内容以提高缓存命中率"""
    # 移除多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    # 移除标点符号
    text = re.sub(r'[,.;:!?(){}[\]<>]', '', text)
    # 转为小写
    text = text.lower()
    return text

def enhanced_cache_key_generation(prompt: str, component_viewpoints: Dict = None, agent_name: str = None) -> str:
    """增强的缓存键生成"""
    # 提取核心内容
    core_content = extract_core_content(prompt)
    
    # 规范化内容
    normalized_content = normalize_content(core_content)
    
    # 基本键
    base_hash = hashlib.md5(normalized_content.encode()).hexdigest()
    
    # 如果有组件和观点信息，添加上下文标识
    if component_viewpoints:
        # 提取组件类型和观点类型作为上下文
        context = []
        for item in component_viewpoints.get('component_viewpoints', []):
            comp_type = item['component'].get('type', '')
            viewpoint_types = [v.split(':')[0] if ':' in v else v for v in item['viewpoints']]
            context.append(f"{comp_type}:{','.join(viewpoint_types)}")
        
        if context:
            context_str = "_".join(context)
            context_hash = hashlib.md5(context_str.encode()).hexdigest()[:8]
            return f"cache_{agent_name}_{context_hash}_{base_hash}"
    
    return f"cache_{agent_name}_{base_hash}"

# ==================== 3. 健壮的错误处理 ====================

def robust_llm_call(llm_client, prompt: str, max_retries: int = 3, backoff_factor: int = 2) -> Dict[str, Any]:
    """健壮的LLM调用，支持重试和降级"""
    retry_count = 0
    last_error = None
    
    while retry_count < max_retries:
        try:
            return llm_client.generate_sync(prompt)
        except Exception as e:
            last_error = e
            retry_count += 1
            # 指数退避
            wait_time = backoff_factor ** retry_count
            print(f"LLM调用失败，第{retry_count}次重试，等待{wait_time}秒: {str(e)}")
            time.sleep(wait_time)
    
    # 所有重试失败后，尝试使用备用模型
    try:
        print("尝试使用备用模型...")
        # 获取备用客户端
        fallback_client = get_fallback_client(llm_client)
        if fallback_client:
            return fallback_client.generate_sync(prompt)
    except Exception as e:
        print(f"备用模型也失败: {str(e)}")
    
    # 最终失败处理
    return {
        "error": str(last_error),
        "content": "无法生成内容，请稍后重试。"
    }

def get_fallback_client(primary_client):
    """获取备用LLM客户端"""
    try:
        # 尝试创建不同模型的客户端
        if hasattr(primary_client, 'agent_name'):
            # 如果原始客户端是SmartLLMClient，创建一个使用不同模型的新实例
            return SmartLLMClient(primary_client.agent_name, use_fallback=True)
        return None
    except:
        return None

# ==================== 4. Token优化策略 ====================

def extract_essential_props(component: Dict) -> Dict:
    """提取组件的关键属性"""
    essential = {}
    # 保留关键属性
    key_props = ['id', 'type', 'name', 'text', 'value', 'placeholder', 'visible', 'enabled']
    for key in key_props:
        if key in component:
            essential[key] = component[key]
    return essential

def optimize_prompt_for_tokens(system_prompt: str, few_shot_examples: list, component: Dict, viewpoint: str) -> str:
    """优化提示以减少token使用"""
    # 移除不必要的空白和格式
    cleaned_system = system_prompt.strip()
    
    # 只使用一个few-shot示例
    optimized_few_shot = []
    if few_shot_examples and len(few_shot_examples) > 0:
        optimized_few_shot = [few_shot_examples[0]]
    
    # 压缩组件信息，只保留关键属性
    essential_component = {
        "type": component.get("type"),
        "name": component.get("name", component.get("id", "")),
        "essential_props": extract_essential_props(component)
    }
    
    # 构建精简提示
    prompt = cleaned_system + '\n'
    
    # 添加精简的few-shot示例
    for ex in optimized_few_shot:
        prompt += f"Example Input:\n{ex['input']}\nExample Output:\n{ex['output']}\n"
    
    # 添加当前输入
    prompt += f"Current Input:\nComponent: {essential_component['type']}\nName: {essential_component['name']}\n"
    if essential_component['essential_props']:
        prompt += f"Properties: {json.dumps(essential_component['essential_props'], ensure_ascii=False)}\n"
    prompt += f"Test Viewpoint: {viewpoint}\nOutput:"
    
    return prompt

def optimize_batch_prompt_for_tokens(components: List[Dict], system_prompt: str, few_shot_examples: list) -> str:
    """优化批处理提示以减少token使用"""
    # 移除不必要的空白和格式
    cleaned_system = system_prompt.strip()
    
    # 只使用一个few-shot示例
    optimized_few_shot = []
    if few_shot_examples and len(few_shot_examples) > 0:
        optimized_few_shot = [few_shot_examples[0]]
    
    # 构建精简提示
    prompt = cleaned_system + '\n'
    
    # 添加精简的few-shot示例
    for ex in optimized_few_shot:
        prompt += f"Example Input:\n{ex['input']}\nExample Output:\n{ex['output']}\n"
    
    # 批量添加组件和观点
    prompt += "Current Input (Batch Processing):\n"
    for i, item in enumerate(components):
        comp = item['component']
        viewpoints = item['viewpoints']
        # 提取关键属性
        essential_props = extract_essential_props(comp)
        
        for j, viewpoint in enumerate(viewpoints):
            prompt += f"Item{i+1}-{j+1}: Type={comp['type']}, Name={comp.get('name', comp.get('id', ''))}, "
            if essential_props:
                key_props_str = ", ".join([f"{k}={v}" for k, v in essential_props.items() if k not in ['type', 'name', 'id']])
                if key_props_str:
                    prompt += f"Props={{{key_props_str}}}, "
            prompt += f"TestViewpoint={viewpoint}\n"
    
    prompt += "\nPlease generate test cases for each item, output as JSON array:"
    return prompt

# ==================== 5. 高效数据传递 ====================

def efficient_state_update(current_state: Dict, testcases: List[Dict], node_name: str = "generate_testcases") -> Dict:
    """高效状态更新"""
    # 只更新必要的状态字段
    updated_state = current_state.copy()
    
    # 添加测试用例结果
    updated_state[f"{node_name}_results"] = testcases
    
    # 清理不再需要的中间数据
    if "component_viewpoints" in updated_state:
        # 保留组件和观点的摘要信息
        component_summary = []
        for item in updated_state["component_viewpoints"].get("component_viewpoints", []):
            component_summary.append({
                "component_type": item["component"].get("type", ""),
                "component_id": item["component"].get("id", ""),
                "viewpoint_count": len(item["viewpoints"])
            })
        
        # 替换详细数据为摘要
        updated_state["component_viewpoints_summary"] = component_summary
        del updated_state["component_viewpoints"]
    
    return updated_state

# ==================== 修改现有函数 ====================

def build_prompt(system_prompt: str, few_shot_examples: list, current_input: str) -> str:
    """构建提示（优化版）"""
    # 使用Token优化策略
    cleaned_system = system_prompt.strip()
    
    # 只使用一个few-shot示例
    optimized_few_shot = []
    if few_shot_examples and len(few_shot_examples) > 0:
        optimized_few_shot = [few_shot_examples[0]]
    
    prompt = cleaned_system + '\n'
    for ex in optimized_few_shot:
        prompt += f"Example Input:\n{ex['input']}\nExample Output:\n{ex['output']}\n"
    prompt += f"Current Input:\n{current_input}\nOutput:"
    return prompt

def build_batch_prompt(components: List[Dict], system_prompt: str, few_shot_examples: list) -> str:
    """构建批处理提示（优化版）"""
    # 使用Token优化的批处理提示
    return optimize_batch_prompt_for_tokens(components, system_prompt, few_shot_examples)

def parse_batch_result(batch_result: str, components: List[Dict]) -> List[Dict[str, Any]]:
    """解析批处理结果（增强健壮性）"""
    try:
        # 尝试多种方式解析JSON结果
        parsed_results = None
        
        # 如果是字符串，尝试解析JSON
        if isinstance(batch_result, str):
            try:
                parsed_results = json.loads(batch_result)
            except json.JSONDecodeError:
                # 尝试从文本中提取JSON部分
                json_match = re.search(r'\[.*\]', batch_result, re.DOTALL)
                if json_match:
                    try:
                        parsed_results = json.loads(json_match.group(0))
                    except:
                        pass
        
        # 如果是字典且包含content键
        elif isinstance(batch_result, dict) and "content" in batch_result:
            try:
                if isinstance(batch_result["content"], str):
                    parsed_results = json.loads(batch_result["content"])
                else:
                    parsed_results = batch_result["content"]
            except:
                pass
        
        # 如果已经是列表
        elif isinstance(batch_result, list):
            parsed_results = batch_result
            
        # 如果无法解析，抛出异常
        if parsed_results is None:
            raise ValueError("无法解析批处理结果")
        
        # 结果映射到组件
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
                    # 结果不足时创建默认测试用例
                    testcases.append({
                        'component_id': comp.get('id', ''),
                        'component': comp,
                        'viewpoint': viewpoint,
                        'testcase': f"Default test case: {viewpoint}"
                    })
        
        return testcases
    except Exception as e:
        print(f"批处理结果解析失败: {str(e)}")
        # 解析失败时降级到单个处理
        return individual_process_components(components, None, None, None, "generate_testcases")

def individual_process_components(components: List[Dict], llm_client=None, prompt_template: str = None, 
                                 few_shot_examples: list = None, agent_name: str = "generate_testcases") -> List[Dict[str, Any]]:
    """单个处理组件（增强健壮性和Token优化）"""
    # 准备LLM客户端
    if llm_client is None:
        llm_client = SmartLLMClient(agent_name)
        
    prompt_manager = PromptManager()
    node_prompt = prompt_manager.get_prompt('generate_testcases')
    system_prompt = prompt_template or node_prompt.get('system_prompt', '')
    few_shot = few_shot_examples or node_prompt.get('few_shot_examples', [])
    
    testcases = []
    for item in components:
        comp = item['component']
        for viewpoint in item['viewpoints']:
            try:
                # 使用Token优化的提示
                optimized_prompt = optimize_prompt_for_tokens(system_prompt, few_shot, comp, viewpoint)
                
                # 使用健壮的LLM调用
                result = robust_llm_call(llm_client, optimized_prompt)
                
                content = result.get("content", "") if isinstance(result, dict) else result
                
                testcases.append({
                    'component_id': comp.get('id', ''),
                    'component': comp,
                    'viewpoint': viewpoint,
                    'testcase': content
                })
            except Exception as e:
                print(f"处理组件失败: {str(e)}")
                # 添加默认测试用例
                testcases.append({
                    'component_id': comp.get('id', ''),
                    'component': comp,
                    'viewpoint': viewpoint,
                    'testcase': f"Default test case: {viewpoint} (处理失败: {str(e)})"
                })
    return testcases

def generate_cache_key(component_viewpoints: Dict, agent_name: str) -> str:
    """生成缓存键（增强版）"""
    # 使用增强的缓存键生成
    return enhanced_cache_key_generation("", component_viewpoints, agent_name)

def filter_components(components: List[Dict], changed_component_ids: List[str] = None) -> List[Dict]:
    """根据变更的组件ID过滤组件列表
    
    Args:
        components: 组件列表
        changed_component_ids: 变更的组件ID列表，如果为None则返回所有组件
        
    Returns:
        过滤后的组件列表
    """
    if not changed_component_ids:
        return components
    
    filtered_components = []
    for item in components:
        comp = item['component']
        comp_id = comp.get('id', '')
        
        # 如果组件ID在变更列表中，或者是容器组件（可能包含变更的子组件）
        if comp_id in changed_component_ids or comp.get('type', '') in ['frame', 'group', 'section']:
            filtered_components.append(item)
    
    return filtered_components

def generate_testcases(component_viewpoints: Dict[str, Any], llm_client=None, prompt_template: str = None, 
                     few_shot_examples: list = None, agent_name: str = "generate_testcases", 
                     incremental: bool = False, changed_component_ids: List[str] = None,
                     parallel: bool = True, max_workers: int = 4) -> Dict[str, Any]:
    """
    生成测试用例
    
    Args:
        component_viewpoints: 组件和测试观点的映射
        llm_client: LLM客户端
        prompt_template: 自定义提示模板
        few_shot_examples: Few-shot学习示例
        agent_name: 代理名称（用于从配置中加载）
        incremental: 是否增量生成
        changed_component_ids: 变更的组件ID列表
        parallel: 是否并行处理
        max_workers: 最大工作线程数
        
    Returns:
        生成的测试用例
    """
    # 检查是否有优先级和分类信息
    has_priority_info = False
    has_classification_info = False
    
    # 提取组件和观点数据
    components_data = component_viewpoints.get("components", [])
    viewpoints_data = component_viewpoints.get("viewpoints", {})
    
    # 检查是否包含元数据
    metadata = component_viewpoints.get("metadata", {})
    if metadata and "viewpoints_analysis" in metadata:
        has_priority_info = "priority_stats" in metadata["viewpoints_analysis"]
        has_classification_info = "classification_stats" in metadata["viewpoints_analysis"]
    
    # 准备LLM客户端
    if llm_client is None:
        llm_client = SmartLLMClient(agent_name)
    
    # 获取提示模板
    prompt_manager = PromptManager()
    node_prompt = prompt_manager.get_prompt('generate_testcases')
    system_prompt = prompt_template or node_prompt.get('system_prompt', '')
    few_shot = few_shot_examples or node_prompt.get('few_shot_examples', [])
    
    # 增量处理逻辑
    if incremental and changed_component_ids:
        # 过滤只处理变更的组件
        filtered_components = [c for c in components_data if c.get("id") in changed_component_ids]
        components_data = filtered_components
    
    # 根据优先级对组件进行排序
    if has_priority_info and components_data:
        # 为每个组件计算优先级分数
        for component in components_data:
            component_id = component.get("id", "")
            if "viewpoints" in component:
                # 计算平均优先级分数
                priority_score = 0
                total_viewpoints = 0
                
                for vp in component["viewpoints"]:
                    if isinstance(vp, dict) and "priority" in vp:
                        priority = vp["priority"]
                        if priority == "HIGH":
                            priority_score += 3
                        elif priority == "MEDIUM":
                            priority_score += 2
                        elif priority == "LOW":
                            priority_score += 1
                        total_viewpoints += 1
                
                if total_viewpoints > 0:
                    component["priority_score"] = priority_score / total_viewpoints
                else:
                    component["priority_score"] = 1  # 默认中等优先级
            else:
                component["priority_score"] = 1  # 默认中等优先级
        
        # 按优先级分数排序，高分优先
        components_data.sort(key=lambda x: x.get("priority_score", 1), reverse=True)
    
    # 并行处理逻辑
    if parallel and len(components_data) > 1:
        # 创建线程池
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交任务
            future_to_component = {
                executor.submit(
                    generate_component_testcase, 
                    component, 
                    llm_client, 
                    system_prompt, 
                    few_shot
                ): component for component in components_data
            }
            
            # 收集结果
            testcases = []
            for future in as_completed(future_to_component):
                component = future_to_component[future]
                try:
                    testcase = future.result()
                    if testcase:
                        testcases.append(testcase)
                except Exception as e:
                    print(f"组件 {component.get('id')} 生成测试用例时出错: {str(e)}")
    else:
        # 串行处理
        testcases = []
        for component in components_data:
            testcase = generate_component_testcase(component, llm_client, system_prompt, few_shot)
            if testcase:
                testcases.append(testcase)
    
    # 添加元数据
    result = {
        "testcases": testcases,
        "metadata": {
            "total_testcases": len(testcases),
            "generation_time": datetime.now().isoformat()
        }
    }
    
    # 如果有优先级和分类信息，添加到结果中
    if has_priority_info or has_classification_info:
        result["metadata"]["viewpoints_analysis"] = metadata.get("viewpoints_analysis", {})
    
    return result

def batch_process_components(components: List[Dict], llm_client=None, prompt_template: str = None, 
                            few_shot_examples: list = None, agent_name: str = "generate_testcases") -> List[Dict[str, Any]]:
    """批处理组件（增强健壮性和Token优化）"""
    # 准备LLM客户端
    if llm_client is None:
        llm_client = SmartLLMClient(agent_name)
        
    prompt_manager = PromptManager()
    node_prompt = prompt_manager.get_prompt('generate_testcases')
    system_prompt = prompt_template or node_prompt.get('system_prompt', '')
    few_shot = few_shot_examples or node_prompt.get('few_shot_examples', [])
    
    # 构建优化的批处理提示
    batch_prompt = build_batch_prompt(components, system_prompt, few_shot)
    
    # 使用健壮的LLM调用
    batch_result = robust_llm_call(llm_client, batch_prompt)
    
    # 解析批处理结果
    return parse_batch_result(batch_result, components)

def generate_component_testcase(component: Dict[str, Any], llm_client, system_prompt: str, few_shot_examples: list) -> Dict[str, Any]:
    """
    为单个组件生成测试用例
    
    Args:
        component: 组件数据
        llm_client: LLM客户端
        system_prompt: 系统提示
        few_shot_examples: Few-shot学习示例
        
    Returns:
        组件的测试用例
    """
    try:
        # 提取组件信息
        component_id = component.get("id", "")
        component_name = component.get("name", "")
        component_type = component.get("type", "")
        viewpoints = component.get("viewpoints", [])
        
        # 如果没有测试观点，跳过
        if not viewpoints:
            return None
        
        # 构建提示
        prompt = f"{system_prompt}\n\n"
        
        # 添加Few-shot示例
        for ex in few_shot_examples:
            prompt += f"Example Input:\n{ex.get('input', '')}\nExample Output:\n{ex.get('output', '')}\n\n"
        
        # 构建当前输入
        current_input = {
            "component": {
                "id": component_id,
                "name": component_name,
                "type": component_type,
                "properties": component.get("properties", {})
            },
            "viewpoints": viewpoints
        }
        
        # 添加优先级信息（如果有）
        if "priority_score" in component:
            current_input["priority_score"] = component["priority_score"]
        
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
                
            # 确保结果包含必要字段
            if not isinstance(parsed_result, dict):
                parsed_result = {"testcases": parsed_result}
            
            # 添加组件信息
            parsed_result["component_id"] = component_id
            parsed_result["component_name"] = component_name
            parsed_result["component_type"] = component_type
            
            return parsed_result
        except Exception as e:
            print(f"解析组件 {component_id} 的测试用例结果时出错: {str(e)}")
            # 返回基本结果
            return {
                "component_id": component_id,
                "component_name": component_name,
                "component_type": component_type,
                "error": str(e),
                "raw_result": result if isinstance(result, str) else str(result)
            }
    except Exception as e:
        print(f"为组件 {component.get('id', 'unknown')} 生成测试用例时出错: {str(e)}")
        return None