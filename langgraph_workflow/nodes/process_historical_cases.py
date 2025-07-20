from typing import Dict, Any, List, Optional
import hashlib
from utils.historical_case_parser import HistoricalCaseParser
from utils.intelligent_cache_manager import intelligent_cache_manager

def process_historical_cases(file_content: bytes = None, file_extension: str = None, filename: str = None, 
                         enable_standardization: bool = True, 
                         multiple_files: List[bytes] = None, 
                         file_extensions: List[str] = None, 
                         filenames: List[str] = None) -> Dict[str, Any]:
    """处理历史测试用例
    
    Args:
        file_content: 单个文件内容
        file_extension: 单个文件扩展名
        filename: 单个文件名
        enable_standardization: 是否启用标准化
        multiple_files: 多个文件内容列表
        file_extensions: 多个文件扩展名列表
        filenames: 多个文件名列表
        
    Returns:
        Dict[str, Any]: 包含处理结果的字典
    """
    try:
        # 判断是处理单个文件还是多个文件
        if multiple_files:
            # 处理多个文件
            historical_cases = HistoricalCaseParser.parse_multiple_files(
                multiple_files, file_extensions, filenames
            )
            # 生成缓存ID
            combined_hash = hashlib.md5(b''.join([
                hashlib.md5(content).digest() for content in multiple_files
            ])).hexdigest()
            cache_id = f"historical_cases_multi_{combined_hash}"
        elif file_content:
            # 处理单个文件
            historical_cases = HistoricalCaseParser.parse_with_cache(file_content, file_extension, filename)
            # 生成缓存ID
            file_hash = hashlib.md5(file_content).hexdigest()
            cache_id = f"historical_cases_{file_hash}"
        else:
            raise ValueError("未提供文件内容")
        
        # 统计信息
        stats = {
            "total_cases": len(historical_cases),
            "file_count": len(multiple_files) if multiple_files else 1,
            "component_types": _count_component_types(historical_cases),
            "action_types": _count_action_types(historical_cases),
            "category_types": _count_category_types(historical_cases)
        }
        
        return {
            "cases": historical_cases,
            "cache_id": cache_id,
            "stats": stats
        }
        
    except Exception as e:
        raise ValueError(f"处理历史测试用例失败: {str(e)}")

def _count_component_types(cases: Dict[str, Any]) -> Dict[str, int]:
    """统计组件类型数量"""
    component_counts = {}
    
    for case_id, case in cases.items():
        components = case.get('components', [])
        for component in components:
            component_counts[component] = component_counts.get(component, 0) + 1
    
    return component_counts

def _count_action_types(cases: Dict[str, Any]) -> Dict[str, int]:
    """统计操作类型数量"""
    action_counts = {}
    
    for case_id, case in cases.items():
        actions = case.get('actions', [])
        for action in actions:
            action_counts[action] = action_counts.get(action, 0) + 1
    
    return action_counts

def _count_category_types(cases: Dict[str, Any]) -> Dict[str, int]:
    """统计测试类别数量"""
    category_counts = {}
    
    for case_id, case in cases.items():
        category = case.get('category', 'Functional')
        category_counts[category] = category_counts.get(category, 0) + 1
    
    return category_counts

def process_historical_cases_node(state: Dict[str, Any], 
                           file_content: bytes = None, 
                           file_extension: str = None, 
                           filename: str = None, 
                           historical_cases_cache_id: str = None,
                           multiple_files: List[bytes] = None,
                           file_extensions: List[str] = None,
                           filenames: List[str] = None) -> Dict[str, Any]:
    """历史测试用例处理节点
    
    Args:
        state: 当前状态
        file_content: 单个文件内容
        file_extension: 单个文件扩展名
        filename: 单个文件名
        historical_cases_cache_id: 历史测试用例缓存ID
        multiple_files: 多个文件内容列表
        file_extensions: 多个文件扩展名列表
        filenames: 多个文件名列表
        
    Returns:
        Dict[str, Any]: 更新后的状态
    """
    # 如果提供了缓存ID，尝试从缓存获取
    if historical_cases_cache_id:
        cached_cases = intelligent_cache_manager.get_with_intelligence(historical_cases_cache_id)
        if cached_cases:
            # 更新状态
            state['historical_cases'] = cached_cases
            return state
    
    # 判断是处理单个文件还是多个文件
    if multiple_files:
        # 处理多个文件
        result = process_historical_cases(
            multiple_files=multiple_files, 
            file_extensions=file_extensions, 
            filenames=filenames
        )
    elif file_content:
        # 处理单个文件
        result = process_historical_cases(
            file_content=file_content, 
            file_extension=file_extension, 
            filename=filename
        )
    else:
        # 如果没有提供文件内容，则历史测试用例为可选项，返回原状态
        if 'historical_cases' not in state:
            state['historical_cases'] = {}
        return state
    
    # 更新状态
    state['historical_cases'] = result['cases']
    
    # 记录日志
    state = _log_processing_result(state, result)
    
    return state

def _log_processing_result(state: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """记录处理结果到日志"""
    if 'workflow_log' not in state:
        state['workflow_log'] = []
    
    stats = result.get('stats', {})
    log_message = f"处理历史测试用例: 共 {stats.get('total_cases', 0)} 个用例, " \
                  f"{len(stats.get('component_types', {}))} 种组件类型, " \
                  f"{len(stats.get('action_types', {}))} 种操作类型, " \
                  f"{len(stats.get('category_types', {}))} 种测试类别"
    
    state['workflow_log'].append(log_message)
    
    return state 