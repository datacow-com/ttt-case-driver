from typing import Dict, Any, List, Optional
import hashlib
from utils.test_pattern_extractor import TestPatternExtractor
from utils.intelligent_cache_manager import intelligent_cache_manager

def extract_test_patterns(historical_cases: Dict[str, Any], cache_key_prefix: str = None) -> Dict[str, Any]:
    """从历史测试用例中提取测试模式
    
    Args:
        historical_cases: 历史测试用例
        cache_key_prefix: 缓存键前缀
        
    Returns:
        Dict[str, Any]: 包含提取结果的字典
    """
    try:
        # 提取测试模式
        pattern_library = TestPatternExtractor.extract_with_cache(historical_cases, cache_key_prefix)
        
        # 生成缓存ID
        if cache_key_prefix:
            cache_id = f"{cache_key_prefix}_patterns"
        else:
            cases_str = str(sorted(historical_cases.keys()))
            cases_hash = hashlib.md5(cases_str.encode()).hexdigest()
            cache_id = f"test_patterns_{cases_hash}"
        
        # 统计信息
        stats = {
            "component_pattern_count": len(pattern_library.get('component_patterns', {})),
            "general_pattern_count": len(pattern_library.get('general_patterns', [])),
            "total_patterns": pattern_library.get('metadata', {}).get('total_patterns', 0)
        }
        
        return {
            "pattern_library": pattern_library,
            "cache_id": cache_id,
            "stats": stats
        }
        
    except Exception as e:
        raise ValueError(f"提取测试模式失败: {str(e)}")

def extract_test_patterns_node(state: Dict[str, Any], historical_cases: Dict[str, Any] = None, historical_cases_cache_id: str = None) -> Dict[str, Any]:
    """测试模式提取节点
    
    Args:
        state: 当前状态
        historical_cases: 历史测试用例
        historical_cases_cache_id: 历史测试用例缓存ID
        
    Returns:
        Dict[str, Any]: 更新后的状态
    """
    # 获取历史测试用例
    cases_to_process = None
    
    # 优先使用传入的历史测试用例
    if historical_cases:
        cases_to_process = historical_cases
    # 其次尝试从缓存获取
    elif historical_cases_cache_id:
        cached_cases = intelligent_cache_manager.get_with_intelligence(historical_cases_cache_id)
        if cached_cases:
            cases_to_process = cached_cases
    # 最后尝试从状态获取
    elif 'historical_cases' in state:
        cases_to_process = state['historical_cases']
    
    # 如果没有可处理的用例，抛出异常
    if not cases_to_process:
        raise ValueError("未提供历史测试用例")
    
    # 提取测试模式
    result = extract_test_patterns(cases_to_process, historical_cases_cache_id)
    
    # 更新状态
    state['historical_patterns'] = result['pattern_library']
    
    # 记录日志
    state = _log_extraction_result(state, result)
    
    return state

def _log_extraction_result(state: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """记录提取结果到日志"""
    if 'workflow_log' not in state:
        state['workflow_log'] = []
    
    stats = result.get('stats', {})
    pattern_library = result.get('pattern_library', {})
    component_patterns = pattern_library.get('component_patterns', {})
    
    log_message = f"提取测试模式: 共 {stats.get('total_patterns', 0)} 个模式, " \
                  f"{stats.get('component_pattern_count', 0)} 种组件模式, " \
                  f"{stats.get('general_pattern_count', 0)} 种通用模式"
    
    # 添加组件模式详情
    if component_patterns:
        component_details = []
        for component_type, patterns in component_patterns.items():
            component_details.append(f"{component_type}: {len(patterns)}个模式")
        
        if component_details:
            log_message += f"\n组件模式详情: {', '.join(component_details[:5])}"
            if len(component_details) > 5:
                log_message += f" 等{len(component_details)}种组件"
    
    state['workflow_log'].append(log_message)
    
    return state 