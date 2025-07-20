from typing import Dict, Any, Callable, List, Optional
import time

class RetryController:
    """
    反馈驱动的重试控制器，根据质量评估结果决定是否需要重试
    """
    
    def __init__(self, max_retries: int = 3, quality_threshold: float = 0.7, 
                 retry_delay: int = 1, retry_backoff: float = 1.5):
        """
        初始化重试控制器
        
        Args:
            max_retries: 最大重试次数
            quality_threshold: 质量阈值，低于此值触发重试
            retry_delay: 初始重试延迟（秒）
            retry_backoff: 重试延迟的增长因子
        """
        self.max_retries = max_retries
        self.quality_threshold = quality_threshold
        self.retry_delay = retry_delay
        self.retry_backoff = retry_backoff
    
    def needs_retry(self, state: Dict[str, Any]) -> bool:
        """
        判断是否需要重试
        
        Args:
            state: 当前状态
            
        Returns:
            bool: 是否需要重试
        """
        # 检查当前重试次数
        current_retry = state.get("optimization_round", 0)
        if current_retry >= self.max_retries:
            return False
        
        # 检查整体质量
        overall_quality = state.get("overall_quality", {})
        average_quality = overall_quality.get("average_quality_score", 1.0)
        
        # 如果平均质量低于阈值，需要重试
        if average_quality < self.quality_threshold:
            return True
        
        # 检查是否有需要改进的测试用例
        quality_metrics = state.get("quality_metrics", [])
        low_quality_cases = [m for m in quality_metrics if m.get("quality_score", 1.0) < self.quality_threshold]
        
        # 如果低质量测试用例比例超过20%，需要重试
        if len(low_quality_cases) > 0 and len(low_quality_cases) / len(quality_metrics) > 0.2:
            return True
        
        return False
    
    def execute_with_retry(self, func: Callable, state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
        """
        执行函数并根据需要重试
        
        Args:
            func: 要执行的函数
            state: 当前状态
            *args, **kwargs: 传递给函数的参数
            
        Returns:
            Dict[str, Any]: 更新后的状态
        """
        current_state = state.copy()
        current_state["optimization_round"] = 0
        
        while True:
            # 执行函数
            updated_state = func(current_state, *args, **kwargs)
            
            # 检查是否需要重试
            if not self.needs_retry(updated_state):
                return updated_state
            
            # 增加重试计数
            current_retry = updated_state.get("optimization_round", 0)
            updated_state["optimization_round"] = current_retry + 1
            
            # 如果达到最大重试次数，返回当前状态
            if updated_state["optimization_round"] >= self.max_retries:
                return updated_state
            
            # 等待一段时间后重试
            delay = self.retry_delay * (self.retry_backoff ** current_retry)
            time.sleep(delay)
            
            # 更新当前状态
            current_state = updated_state 