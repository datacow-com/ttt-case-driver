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

@cache_llm_call(ttl=3600)
def generate_testcases(component_viewpoints: Dict[str, Any], llm_client=None, 
                      prompt_template: str = None, few_shot_examples: list = None,
                      agent_name: str = "generate_testcases",
                      incremental: bool = False,
                      changed_component_ids: List[str] = None,
                      parallel: bool = True,
                      max_workers: int = 4) -> List[Dict[str, Any]]:
    """
    优化的测试用例生成，支持智能批处理、高效缓存和并行处理
    
    Args:
        component_viewpoints: 组件和观点的映射
        llm_client: LLM客户端（未指定时创建）
        prompt_template: 自定义提示模板
        few_shot_examples: Few-shot学习示例
        agent_name: 代理名称（用于从配置加载）
        incremental: 是否启用增量处理
        changed_component_ids: 变更的组件ID列表，用于增量处理
        parallel: 是否启用并行处理
        max_workers: 最大并行工作线程数
        
    Returns:
        生成的测试用例列表
    """
    # 生成缓存键
    cache_key = generate_cache_key(component_viewpoints, agent_name)
    
    # 检查缓存（非增量处理时）
    if not incremental:
        cached_result = cache_manager.get(cache_key)
        if cached_result is not None:
            return cached_result
    
    # 准备LLM客户端
    if llm_client is None:
        llm_client = SmartLLMClient(agent_name)
    
    components = component_viewpoints.get('component_viewpoints', [])
    
    # 增量处理：过滤组件
    if incremental and changed_component_ids:
        original_count = len(components)
        components = filter_components(components, changed_component_ids)
        filtered_count = len(components)
        print(f"增量处理：从{original_count}个组件中过滤出{filtered_count}个组件")
    
    # 使用智能批处理策略（支持并行处理）
    result = smart_batch_processing(
        components, 
        llm_client, 
        prompt_template, 
        few_shot_examples, 
        agent_name,
        max_workers=max_workers,
        parallel=parallel
    )
    
    # 增量处理：合并结果
    if incremental and changed_component_ids:
        # 获取之前的结果
        previous_result = cache_manager.get(cache_key)
        if previous_result:
            # 创建组件ID到测试用例的映射
            result_map = {item['component_id']: item for item in result}
            
            # 合并结果
            merged_result = []
            for item in previous_result:
                comp_id = item['component_id']
                if comp_id in result_map:
                    # 使用新结果替换
                    merged_result.append(result_map[comp_id])
                    # 从结果映射中移除，以便后续添加未匹配的新结果
                    del result_map[comp_id]
                else:
                    # 保留原结果
                    merged_result.append(item)
            
            # 添加未匹配的新结果
            for item in result_map.values():
                merged_result.append(item)
            
            result = merged_result
    
    # 动态设置缓存TTL（根据数据量和复杂度）
    complexity = len(components) * sum(len(item['viewpoints']) for item in components)
    dynamic_ttl = min(7200, max(1800, 3600 + (complexity // 10) * 100))  # 基础3600秒，根据复杂度调整
    
    # 缓存结果
    cache_manager.set(cache_key, result, ttl=dynamic_ttl)
    
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