from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime
import json
from utils.redis_manager import redis_manager

class TestCaseState(TypedDict):
    """测试用例生成状态管理"""
    figma_data: Dict[str, Any]
    viewpoints_file: Dict[str, Any]
    historical_cases: Optional[Dict[str, Any]]  # 新增：历史测试用例（可选）
    historical_patterns: Optional[Dict[str, Any]]  # 新增：历史测试模式（可选）
    difference_report: Optional[Dict[str, Any]]  # 新增：差异报告（可选）
    coverage_report: Optional[Dict[str, Any]]  # 新增：覆盖率报告（可选）
    semantic_correlation_map: Optional[Dict[str, Any]]  # 新增：语义关联图谱（可选）
    modules_analysis: Dict[str, Any]
    figma_viewpoints_mapping: Dict[str, Any]
    checklist_mapping: List[Dict[str, Any]]
    test_purpose_validation: List[Dict[str, Any]]
    quality_analysis: Dict[str, Any]
    final_testcases: List[Dict[str, Any]]
    workflow_log: List[str]
    cache_metadata: Dict[str, Any]  # 新增：缓存元数据

class StateManager:
    """状态管理器 - 基于Redis"""
    
    @staticmethod
    def create_initial_state(figma_data: Dict[str, Any], viewpoints_file: Dict[str, Any], 
                            historical_cases: Optional[Dict[str, Any]] = None) -> TestCaseState:
        """创建初始状态"""
        return TestCaseState(
            figma_data=figma_data,
            viewpoints_file=viewpoints_file,
            historical_cases=historical_cases,
            historical_patterns=None,
            difference_report=None,
            coverage_report=None,
            semantic_correlation_map=None,  # 初始化语义关联图谱为None
            modules_analysis={},
            figma_viewpoints_mapping={},
            checklist_mapping=[],
            test_purpose_validation=[],
            quality_analysis={},
            final_testcases=[],
            workflow_log=[],
            cache_metadata={
                "figma_cache_keys": [],
                "viewpoints_cache_keys": [],
                "historical_cache_keys": [] if historical_cases else None,
                "llm_cache_keys": [],
                "created_at": datetime.now().isoformat()
            }
        )
    
    @staticmethod
    def update_state(state: TestCaseState, updates: Dict[str, Any]) -> TestCaseState:
        """更新状态"""
        return {**state, **updates}
    
    @staticmethod
    def log_step(state: TestCaseState, step_name: str, message: str) -> TestCaseState:
        """记录工作流步骤"""
        log_entry = f"[{datetime.now().isoformat()}] {step_name}: {message}"
        workflow_log = state.get('workflow_log', []) + [log_entry]
        return {**state, 'workflow_log': workflow_log}
    
    @staticmethod
    def save_workflow_state(workflow_id: str, state: TestCaseState, ttl: int = 7200) -> bool:
        """保存工作流状态到Redis"""
        return redis_manager.save_workflow_state(workflow_id, state, ttl)
    
    @staticmethod
    def get_workflow_state(workflow_id: str) -> Optional[TestCaseState]:
        """从Redis获取工作流状态"""
        return redis_manager.get_workflow_state(workflow_id)
    
    @staticmethod
    def create_session(input_data: Dict[str, Any], config: Dict[str, Any]) -> str:
        """创建新session"""
        return redis_manager.create_session(input_data, config)
    
    @staticmethod
    def get_session(session_id: str) -> Optional[Dict[str, Any]]:
        """获取session信息"""
        return redis_manager.get_session(session_id)
    
    @staticmethod
    def update_session(session_id: str, updates: Dict[str, Any]) -> bool:
        """更新session信息"""
        return redis_manager.update_session(session_id, updates)
    
    @staticmethod
    def save_node_result(session_id: str, node_name: str, 
                        input_data: Dict[str, Any], output_data: Dict[str, Any]) -> bool:
        """保存节点结果"""
        return redis_manager.save_node_result(session_id, node_name, input_data, output_data)
    
    @staticmethod
    def get_node_result(session_id: str, node_name: str) -> Optional[Dict[str, Any]]:
        """获取节点结果"""
        return redis_manager.get_node_result(session_id, node_name)
    
    @staticmethod
    def get_all_node_results(session_id: str) -> Dict[str, Any]:
        """获取session的所有节点结果"""
        return redis_manager.get_all_node_results(session_id)
    
    @staticmethod
    def save_feedback(session_id: str, node_name: str, feedback: Dict[str, Any]) -> bool:
        """保存反馈"""
        return redis_manager.save_feedback(session_id, node_name, feedback)
    
    @staticmethod
    def get_feedback(session_id: str, node_name: str) -> Optional[Dict[str, Any]]:
        """获取反馈"""
        return redis_manager.get_feedback(session_id, node_name)
    
    @staticmethod
    def track_cache_usage(state: TestCaseState, cache_type: str, cache_key: str) -> TestCaseState:
        """跟踪缓存使用情况"""
        cache_metadata = state.get('cache_metadata', {})
        cache_keys = cache_metadata.get(f"{cache_type}_cache_keys", [])
        if cache_key not in cache_keys:
            cache_keys.append(cache_key)
            cache_metadata[f"{cache_type}_cache_keys"] = cache_keys
        return {**state, 'cache_metadata': cache_metadata}
    
    @staticmethod
    def save_semantic_correlation_map(workflow_id: str, correlation_map: Dict[str, Any], ttl: int = 7200) -> bool:
        """保存语义关联映射到Redis
        
        Args:
            workflow_id: 工作流ID
            correlation_map: 语义关联图谱
            ttl: 过期时间（秒）
            
        Returns:
            bool: 是否保存成功
        """
        key = f"semantic_correlation_map_{workflow_id}"
        return redis_manager.set_cache(key, correlation_map, ttl)
    
    @staticmethod
    def get_semantic_correlation_map(workflow_id: str) -> Optional[Dict[str, Any]]:
        """从Redis获取语义关联映射
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            Optional[Dict[str, Any]]: 语义关联图谱，如果不存在则返回None
        """
        key = f"semantic_correlation_map_{workflow_id}"
        return redis_manager.get_cache(key) 