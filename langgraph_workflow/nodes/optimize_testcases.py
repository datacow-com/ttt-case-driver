from typing import Dict, Any, List
import json
import sys
import os
import re

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.llm_client import LLMClient
from utils.cache_manager import cache_llm_call
from state_management import StateManager

@cache_llm_call(ttl=3600)
def optimize_testcases(state: Dict[str, Any], llm_client: LLMClient) -> Dict[str, Any]:
    """
    根据质量评估结果优化测试用例
    """
    final_testcases = state.get("final_testcases", [])
    quality_metrics = state.get("quality_metrics", [])
    
    # 如果没有质量评估结果，无法优化
    if not quality_metrics:
        return state
    
    # 创建测试用例ID到质量指标的映射
    quality_map = {m["test_case_id"]: m for m in quality_metrics}
    
    # 收集需要优化的测试用例
    testcases_to_optimize = []
    for testcase in final_testcases:
        test_id = testcase.get("test_case_id", "")
        if test_id in quality_map and quality_map[test_id].get("needs_improvement", False):
            testcases_to_optimize.append({
                "testcase": testcase,
                "quality_metric": quality_map[test_id]
            })
    
    # 如果没有需要优化的测试用例，直接返回
    if not testcases_to_optimize:
        updated_state = StateManager.log_step(
            state,
            "optimize_testcases",
            "无需优化：所有测试用例质量良好"
        )
        return updated_state
    
    # 优化测试用例
    optimized_testcases = []
    optimization_logs = []
    
    for item in testcases_to_optimize:
        testcase = item["testcase"]
        quality_metric = item["quality_metric"]
        
        # 构建优化提示
        prompt = build_optimization_prompt(testcase, quality_metric)
        
        try:
            # 调用LLM优化测试用例
            optimized_result = llm_client.generate(prompt)
            
            # 解析优化后的测试用例
            if isinstance(optimized_result, str):
                try:
                    optimized_testcase = json.loads(optimized_result)
                except:
                    # 如果无法解析为JSON，尝试提取JSON部分
                    json_match = re.search(r'\{.*\}', optimized_result, re.DOTALL)
                    if json_match:
                        try:
                            optimized_testcase = json.loads(json_match.group(0))
                        except:
                            # 如果仍然失败，保留原测试用例
                            optimized_testcase = testcase
                    else:
                        optimized_testcase = testcase
            else:
                optimized_testcase = optimized_result
            
            # 保留原始测试用例ID
            if "test_case_id" in testcase:
                optimized_testcase["test_case_id"] = testcase["test_case_id"]
            
            # 添加优化标记
            optimized_testcase["optimized"] = True
            optimized_testcase["optimization_round"] = state.get("optimization_round", 0) + 1
            
            # 添加到优化后的测试用例列表
            optimized_testcases.append(optimized_testcase)
            
            # 记录优化日志
            optimization_logs.append({
                "test_case_id": testcase.get("test_case_id", ""),
                "original_quality_score": quality_metric.get("quality_score", 0),
                "improvement_suggestions": quality_metric.get("improvement_suggestions", [])
            })
        
        except Exception as e:
            # 如果优化失败，保留原测试用例
            optimized_testcases.append(testcase)
            
            # 记录错误日志
            optimization_logs.append({
                "test_case_id": testcase.get("test_case_id", ""),
                "error": str(e)
            })
    
    # 更新最终的测试用例列表
    updated_testcases = []
    for testcase in final_testcases:
        test_id = testcase.get("test_case_id", "")
        # 如果是需要优化的测试用例，使用优化后的版本
        if test_id in quality_map and quality_map[test_id].get("needs_improvement", False):
            # 查找优化后的版本
            optimized = next((t for t in optimized_testcases if t.get("test_case_id") == test_id), None)
            if optimized:
                updated_testcases.append(optimized)
            else:
                updated_testcases.append(testcase)
        else:
            updated_testcases.append(testcase)
    
    # 更新状态
    updated_state = StateManager.update_state(state, {
        "final_testcases": updated_testcases,
        "optimization_logs": state.get("optimization_logs", []) + optimization_logs,
        "optimization_round": state.get("optimization_round", 0) + 1
    })
    
    # 添加工作流日志
    updated_state = StateManager.log_step(
        updated_state,
        "optimize_testcases",
        f"优化完成: 优化了 {len(testcases_to_optimize)} 个测试用例，当前优化轮次 {updated_state['optimization_round']}"
    )
    
    return updated_state

def build_optimization_prompt(testcase: Dict[str, Any], quality_metric: Dict[str, Any]) -> str:
    """构建优化提示"""
    suggestions = quality_metric.get("improvement_suggestions", [])
    
    prompt = f"""
    你是一个专业的测试用例优化专家。请根据以下质量评估结果和改进建议，优化下面的测试用例：

    测试用例：
    {json.dumps(testcase, ensure_ascii=False, indent=2)}

    质量评估：
    - 完整性分数: {quality_metric.get("completeness_score", 0):.2f}
    - 精确性分数: {quality_metric.get("precision_score", 0):.2f}
    - 可执行性分数: {quality_metric.get("executability_score", 0):.2f}
    - 覆盖率分数: {quality_metric.get("coverage_score", 0):.2f}
    - 总体质量分数: {quality_metric.get("quality_score", 0):.2f}

    改进建议：
    {json.dumps(suggestions, ensure_ascii=False, indent=2)}

    请根据以上评估和建议，优化测试用例。保持原有的测试用例结构，但提高其质量。
    请以JSON格式返回优化后的测试用例。
    """
    
    return prompt 