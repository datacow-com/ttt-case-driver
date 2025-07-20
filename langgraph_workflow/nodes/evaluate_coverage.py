from typing import Dict, Any, List, Optional
import hashlib
from utils.coverage_evaluator import CoverageEvaluator
from utils.intelligent_cache_manager import intelligent_cache_manager

def evaluate_coverage(viewpoints: Dict[str, Any], difference_report: Dict[str, Any], pattern_library: Dict[str, Any], cache_key_prefix: str = None) -> Dict[str, Any]:
    """评估测试观点覆盖率
    
    Args:
        viewpoints: 测试观点
        difference_report: 差异报告
        pattern_library: 测试模式库
        cache_key_prefix: 缓存键前缀
        
    Returns:
        Dict[str, Any]: 包含评估结果的字典
    """
    try:
        # 评估覆盖率
        coverage_report = CoverageEvaluator.evaluate_with_cache(viewpoints, difference_report, pattern_library, cache_key_prefix)
        
        # 生成缓存ID
        if cache_key_prefix:
            cache_id = f"{cache_key_prefix}_coverage"
        else:
            # 基于输入数据生成哈希
            input_str = str(len(viewpoints)) + str(len(difference_report)) + str(len(pattern_library))
            input_hash = hashlib.md5(input_str.encode()).hexdigest()
            cache_id = f"coverage_{input_hash}"
        
        # 统计信息
        metadata = coverage_report.get('metadata', {})
        stats = {
            "overall_coverage_score": metadata.get('overall_coverage_score', 0.0),
            "gap_count": metadata.get('gap_count', 0),
            "recommendation_count": metadata.get('recommendation_count', 0)
        }
        
        return {
            "coverage_report": coverage_report,
            "cache_id": cache_id,
            "stats": stats
        }
        
    except Exception as e:
        raise ValueError(f"评估覆盖率失败: {str(e)}")

def evaluate_coverage_node(state: Dict[str, Any], viewpoints: Dict[str, Any] = None, viewpoints_cache_id: str = None, 
                          difference_report: Dict[str, Any] = None, difference_cache_id: str = None,
                          pattern_library: Dict[str, Any] = None, patterns_cache_id: str = None) -> Dict[str, Any]:
    """覆盖率评估节点
    
    Args:
        state: 当前状态
        viewpoints: 测试观点
        viewpoints_cache_id: 测试观点缓存ID
        difference_report: 差异报告
        difference_cache_id: 差异报告缓存ID
        pattern_library: 测试模式库
        patterns_cache_id: 测试模式库缓存ID
        
    Returns:
        Dict[str, Any]: 更新后的状态
    """
    # 获取测试观点
    viewpoints_to_process = None
    
    # 优先使用传入的测试观点
    if viewpoints:
        viewpoints_to_process = viewpoints
    # 其次尝试从缓存获取
    elif viewpoints_cache_id:
        cached_viewpoints = intelligent_cache_manager.get_with_intelligence(viewpoints_cache_id)
        if cached_viewpoints:
            viewpoints_to_process = cached_viewpoints
    # 最后尝试从状态获取
    elif 'viewpoints_file' in state:
        viewpoints_to_process = state['viewpoints_file']
    
    # 如果没有测试观点，抛出异常
    if not viewpoints_to_process:
        raise ValueError("未提供测试观点")
    
    # 获取差异报告
    diff_report_to_process = None
    
    # 优先使用传入的差异报告
    if difference_report:
        diff_report_to_process = difference_report
    # 其次尝试从缓存获取
    elif difference_cache_id:
        cached_diff = intelligent_cache_manager.get_with_intelligence(difference_cache_id)
        if cached_diff:
            diff_report_to_process = cached_diff
    # 最后尝试从状态获取
    elif 'difference_report' in state:
        diff_report_to_process = state['difference_report']
    
    # 如果没有差异报告，抛出异常
    if not diff_report_to_process:
        raise ValueError("未提供差异报告")
    
    # 获取测试模式库
    patterns_to_process = None
    
    # 优先使用传入的测试模式库
    if pattern_library:
        patterns_to_process = pattern_library
    # 其次尝试从缓存获取
    elif patterns_cache_id:
        cached_patterns = intelligent_cache_manager.get_with_intelligence(patterns_cache_id)
        if cached_patterns:
            patterns_to_process = cached_patterns
    # 最后尝试从状态获取
    elif 'historical_patterns' in state:
        patterns_to_process = state['historical_patterns']
    
    # 如果没有测试模式库，抛出异常
    if not patterns_to_process:
        raise ValueError("未提供测试模式库")
    
    # 评估覆盖率
    result = evaluate_coverage(viewpoints_to_process, diff_report_to_process, patterns_to_process, patterns_cache_id)
    
    # 更新状态
    state['coverage_report'] = result['coverage_report']
    
    # 记录日志
    state = _log_evaluation_result(state, result)
    
    return state

def _log_evaluation_result(state: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """记录评估结果到日志"""
    if 'workflow_log' not in state:
        state['workflow_log'] = []
    
    stats = result.get('stats', {})
    coverage_report = result.get('coverage_report', {})
    
    # 计算覆盖率百分比
    coverage_score = stats.get('overall_coverage_score', 0.0)
    coverage_percentage = f"{coverage_score * 100:.1f}%"
    
    log_message = f"覆盖率评估: 总体覆盖率 {coverage_percentage}, " \
                  f"覆盖缺口 {stats.get('gap_count', 0)} 个, " \
                  f"推荐测试点 {stats.get('recommendation_count', 0)} 个"
    
    # 添加覆盖缺口详情
    coverage_gaps = coverage_report.get('coverage_gaps', [])
    if coverage_gaps:
        gap_types = {}
        for gap in coverage_gaps:
            gap_type = gap.get('type', 'UNKNOWN')
            gap_types[gap_type] = gap_types.get(gap_type, 0) + 1
        
        if gap_types:
            type_details = []
            for gap_type, count in gap_types.items():
                type_details.append(f"{gap_type}: {count}个")
            
            log_message += f"\n覆盖缺口类型: {', '.join(type_details)}"
    
    # 添加推荐详情
    recommendations = coverage_report.get('recommendations', [])
    if recommendations:
        rec_categories = {}
        for rec in recommendations:
            category = rec.get('category', 'Functional')
            rec_categories[category] = rec_categories.get(category, 0) + 1
        
        if rec_categories:
            category_details = []
            for category, count in rec_categories.items():
                category_details.append(f"{category}: {count}个")
            
            log_message += f"\n推荐测试点类别: {', '.join(category_details)}"
    
    state['workflow_log'].append(log_message)
    
    return state 