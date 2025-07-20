from typing import Dict, Any, List, Optional
import hashlib
from utils.difference_analyzer import DifferenceAnalyzer
from utils.intelligent_cache_manager import intelligent_cache_manager

def analyze_differences(figma_data: Dict[str, Any], historical_patterns: Dict[str, Any], cache_key_prefix: str = None) -> Dict[str, Any]:
    """分析Figma设计与历史测试模式的差异
    
    Args:
        figma_data: Figma设计数据
        historical_patterns: 历史测试模式
        cache_key_prefix: 缓存键前缀
        
    Returns:
        Dict[str, Any]: 包含分析结果的字典
    """
    try:
        # 分析差异
        difference_report = DifferenceAnalyzer.analyze_with_cache(figma_data, historical_patterns, cache_key_prefix)
        
        # 生成缓存ID
        if cache_key_prefix:
            cache_id = f"{cache_key_prefix}_differences"
        else:
            # 基于输入数据生成哈希
            input_str = str(len(figma_data)) + str(len(historical_patterns))
            input_hash = hashlib.md5(input_str.encode()).hexdigest()
            cache_id = f"differences_{input_hash}"
        
        # 统计信息
        metadata = difference_report.get('metadata', {})
        stats = {
            "figma_component_count": metadata.get('figma_component_count', 0),
            "historical_component_count": metadata.get('historical_component_count', 0),
            "new_component_count": metadata.get('new_component_count', 0),
            "modified_component_count": metadata.get('modified_component_count', 0),
            "removed_component_count": metadata.get('removed_component_count', 0)
        }
        
        return {
            "difference_report": difference_report,
            "cache_id": cache_id,
            "stats": stats
        }
        
    except Exception as e:
        raise ValueError(f"分析差异失败: {str(e)}")

def analyze_differences_node(state: Dict[str, Any], figma_data: Dict[str, Any] = None, figma_cache_id: str = None, historical_patterns: Dict[str, Any] = None, patterns_cache_id: str = None) -> Dict[str, Any]:
    """差异分析节点
    
    Args:
        state: 当前状态
        figma_data: Figma设计数据
        figma_cache_id: Figma数据缓存ID
        historical_patterns: 历史测试模式
        patterns_cache_id: 测试模式缓存ID
        
    Returns:
        Dict[str, Any]: 更新后的状态
    """
    # 获取Figma数据
    figma_to_process = None
    
    # 优先使用传入的Figma数据
    if figma_data:
        figma_to_process = figma_data
    # 其次尝试从缓存获取
    elif figma_cache_id:
        cached_figma = intelligent_cache_manager.get_with_intelligence(figma_cache_id)
        if cached_figma:
            figma_to_process = cached_figma
    # 最后尝试从状态获取
    elif 'figma_data' in state:
        figma_to_process = state['figma_data']
    
    # 如果没有Figma数据，抛出异常
    if not figma_to_process:
        raise ValueError("未提供Figma设计数据")
    
    # 获取历史测试模式
    patterns_to_process = None
    
    # 优先使用传入的历史测试模式
    if historical_patterns:
        patterns_to_process = historical_patterns
    # 其次尝试从缓存获取
    elif patterns_cache_id:
        cached_patterns = intelligent_cache_manager.get_with_intelligence(patterns_cache_id)
        if cached_patterns:
            patterns_to_process = cached_patterns
    # 最后尝试从状态获取
    elif 'historical_patterns' in state:
        patterns_to_process = state['historical_patterns']
    
    # 如果没有历史测试模式，抛出异常
    if not patterns_to_process:
        raise ValueError("未提供历史测试模式")
    
    # 分析差异
    result = analyze_differences(figma_to_process, patterns_to_process, patterns_cache_id)
    
    # 更新状态
    state['difference_report'] = result['difference_report']
    
    # 记录日志
    state = _log_analysis_result(state, result)
    
    return state

def _log_analysis_result(state: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """记录分析结果到日志"""
    if 'workflow_log' not in state:
        state['workflow_log'] = []
    
    stats = result.get('stats', {})
    difference_report = result.get('difference_report', {})
    
    log_message = f"差异分析: Figma组件 {stats.get('figma_component_count', 0)} 个, " \
                  f"历史组件 {stats.get('historical_component_count', 0)} 个, " \
                  f"新增 {stats.get('new_component_count', 0)} 个, " \
                  f"修改 {stats.get('modified_component_count', 0)} 个, " \
                  f"删除 {stats.get('removed_component_count', 0)} 个"
    
    # 添加新增组件详情
    new_components = difference_report.get('new_components', [])
    if new_components:
        new_component_types = {}
        for component in new_components:
            component_type = component.get('type', 'UNKNOWN')
            new_component_types[component_type] = new_component_types.get(component_type, 0) + 1
        
        if new_component_types:
            type_details = []
            for component_type, count in new_component_types.items():
                type_details.append(f"{component_type}: {count}个")
            
            log_message += f"\n新增组件类型: {', '.join(type_details[:5])}"
            if len(type_details) > 5:
                log_message += f" 等{len(type_details)}种类型"
    
    state['workflow_log'].append(log_message)
    
    return state 