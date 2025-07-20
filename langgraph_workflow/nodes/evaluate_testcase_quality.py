from typing import Dict, Any, List
import json
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.llm_client import LLMClient
from utils.cache_manager import cache_llm_call
from state_management import StateManager

@cache_llm_call(ttl=3600)
def evaluate_testcase_quality(state: Dict[str, Any], llm_client: LLMClient) -> Dict[str, Any]:
    """
    评估测试用例质量，提供改进建议
    """
    final_testcases = state.get("final_testcases", [])
    quality_metrics = []
    
    for testcase in final_testcases:
        # 计算测试用例的完整性分数
        completeness_score = calculate_completeness(testcase)
        
        # 计算测试用例的精确性分数
        precision_score = calculate_precision(testcase, state.get("figma_data", {}))
        
        # 计算测试用例的可执行性分数
        executability_score = calculate_executability(testcase)
        
        # 计算测试用例的覆盖率分数
        coverage_score = calculate_coverage(testcase, state.get("viewpoints_file", {}))
        
        # 计算总体质量分数
        quality_score = (completeness_score * 0.3 + 
                         precision_score * 0.3 + 
                         executability_score * 0.2 + 
                         coverage_score * 0.2)
        
        # 生成改进建议
        improvement_suggestions = generate_improvement_suggestions(
            testcase, completeness_score, precision_score, executability_score, coverage_score
        )
        
        quality_metrics.append({
            "test_case_id": testcase.get("test_case_id", ""),
            "completeness_score": completeness_score,
            "precision_score": precision_score,
            "executability_score": executability_score,
            "coverage_score": coverage_score,
            "quality_score": quality_score,
            "improvement_suggestions": improvement_suggestions,
            "needs_improvement": quality_score < 0.7  # 质量阈值
        })
    
    # 计算整体质量统计
    overall_quality = {
        "average_quality_score": sum(m["quality_score"] for m in quality_metrics) / len(quality_metrics) if quality_metrics else 0,
        "low_quality_count": sum(1 for m in quality_metrics if m["quality_score"] < 0.7),
        "high_quality_count": sum(1 for m in quality_metrics if m["quality_score"] >= 0.7),
        "improvement_needed": any(m["needs_improvement"] for m in quality_metrics)
    }
    
    # 更新状态
    updated_state = StateManager.update_state(state, {
        "quality_metrics": quality_metrics,
        "overall_quality": overall_quality
    })
    
    # 添加工作流日志
    updated_state = StateManager.log_step(
        updated_state,
        "evaluate_testcase_quality",
        f"评估完成: 平均质量分数 {overall_quality['average_quality_score']:.2f}, " +
        f"需要改进的测试用例: {overall_quality['low_quality_count']}/{len(quality_metrics)}"
    )
    
    return updated_state

def calculate_completeness(testcase: Dict[str, Any]) -> float:
    """计算测试用例的完整性分数"""
    score = 0.0
    total_weight = 0.0
    
    # 检查必要字段
    required_fields = [
        ("test_case_id", 0.05),
        ("module", 0.05),
        ("viewpoint", 0.05),
        ("priority", 0.05),
        ("category", 0.05),
        ("preconditions", 0.15),
        ("test_steps", 0.6)
    ]
    
    for field, weight in required_fields:
        if field in testcase and testcase[field]:
            if field == "test_steps":
                steps = testcase[field]
                if steps:
                    step_score = 0.0
                    for step in steps:
                        if "step_number" in step and "step_description" in step and "expected_result" in step:
                            step_score += 1.0
                    score += (step_score / len(steps)) * weight
            else:
                score += weight
        total_weight += weight
    
    return score / total_weight if total_weight > 0 else 0.0

def calculate_precision(testcase: Dict[str, Any], figma_data: Dict[str, Any]) -> float:
    """计算测试用例的精确性分数"""
    score = 0.7  # 基础分数
    
    # 检查测试步骤是否具体明确
    steps = testcase.get("test_steps", [])
    if steps:
        specific_steps = 0
        for step in steps:
            step_desc = step.get("step_description", "")
            # 检查步骤描述是否具体
            if len(step_desc.split()) >= 5 and any(action in step_desc.lower() for action in ["点击", "输入", "选择", "验证", "检查", "click", "input", "select", "verify", "check"]):
                specific_steps += 1
        
        specificity_score = specific_steps / len(steps) if len(steps) > 0 else 0
        score = 0.7 + (specificity_score * 0.3)  # 最高分1.0
    
    return score

def calculate_executability(testcase: Dict[str, Any]) -> float:
    """计算测试用例的可执行性分数"""
    score = 0.5  # 基础分数
    
    # 检查前置条件是否完整
    preconditions = testcase.get("preconditions", [])
    if preconditions and len(preconditions) > 0:
        score += 0.2
    
    # 检查测试步骤是否有明确的预期结果
    steps = testcase.get("test_steps", [])
    if steps:
        steps_with_expected_results = 0
        for step in steps:
            if "expected_result" in step and step["expected_result"]:
                steps_with_expected_results += 1
        
        if len(steps) > 0:
            expected_results_score = steps_with_expected_results / len(steps)
            score += expected_results_score * 0.3
    
    return min(score, 1.0)

def calculate_coverage(testcase: Dict[str, Any], viewpoints_data: Dict[str, Any]) -> float:
    """计算测试用例的覆盖率分数"""
    score = 0.6  # 基础分数
    
    # 检查测试用例是否覆盖了相关的测试观点
    viewpoint = testcase.get("viewpoint", "")
    module = testcase.get("module", "")
    
    if viewpoint and module and module in viewpoints_data:
        module_viewpoints = viewpoints_data[module]
        if any(v.get("viewpoint", "") == viewpoint for v in module_viewpoints if isinstance(v, dict)) or viewpoint in module_viewpoints:
            score += 0.2
    
    # 检查是否包含边界情况测试
    steps = testcase.get("test_steps", [])
    if any("边界" in step.get("step_description", "") or "boundary" in step.get("step_description", "").lower() for step in steps):
        score += 0.1
    
    # 检查是否包含异常情况测试
    if any("异常" in step.get("step_description", "") or "error" in step.get("step_description", "").lower() for step in steps):
        score += 0.1
    
    return min(score, 1.0)

def generate_improvement_suggestions(testcase: Dict[str, Any], completeness: float, precision: float, executability: float, coverage: float) -> List[str]:
    """生成测试用例改进建议"""
    suggestions = []
    
    # 根据完整性分数生成建议
    if completeness < 0.7:
        suggestions.append("提高完整性：确保包含所有必要字段和详细的测试步骤")
        
        # 检查缺失的关键字段
        missing_fields = []
        if "preconditions" not in testcase or not testcase["preconditions"]:
            missing_fields.append("前置条件")
        if "test_steps" not in testcase or not testcase["test_steps"]:
            missing_fields.append("测试步骤")
        
        if missing_fields:
            suggestions.append(f"添加缺失的关键信息：{', '.join(missing_fields)}")
    
    # 根据精确性分数生成建议
    if precision < 0.7:
        suggestions.append("提高精确性：使测试步骤更加具体明确，包含明确的操作对象和操作方式")
    
    # 根据可执行性分数生成建议
    if executability < 0.7:
        suggestions.append("提高可执行性：为每个测试步骤添加明确的预期结果")
    
    # 根据覆盖率分数生成建议
    if coverage < 0.7:
        suggestions.append("提高覆盖率：考虑添加边界条件和异常情况的测试")
    
    return suggestions 