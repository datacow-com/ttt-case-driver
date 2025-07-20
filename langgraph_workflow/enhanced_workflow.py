from langgraph.graph import StateGraph, END
from typing import Dict, Any
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from state_management import StateManager
from nodes.analyze_viewpoints_modules import analyze_viewpoints_modules
from nodes.map_figma_to_viewpoints import map_figma_to_viewpoints
from nodes.map_checklist_to_figma_areas import map_checklist_to_figma_areas
from nodes.validate_test_purpose_coverage import validate_test_purpose_coverage
from nodes.deep_understanding_and_gap_analysis import deep_understanding_and_gap_analysis
from nodes.generate_final_testcases import generate_final_testcases
from nodes.process_historical_cases import process_historical_cases_node
from nodes.extract_test_patterns import extract_test_patterns_node
from nodes.analyze_differences import analyze_differences_node
from nodes.evaluate_coverage import evaluate_coverage_node
from nodes.create_semantic_correlation_map import create_semantic_correlation_map
from nodes.evaluate_testcase_quality import evaluate_testcase_quality
from nodes.optimize_testcases import optimize_testcases
from utils.llm_client import LLMClient
from utils.llm_client_factory import LLMClientFactory
from utils.retry_controller import RetryController

def build_enhanced_workflow(use_historical_cases: bool = False):
    """构建增强的测试用例生成工作流
    
    Args:
        use_historical_cases: 是否使用历史测试用例
    """
    
    workflow = StateGraph(StateManager.create_initial_state)
    
    # 添加基础节点
    workflow.add_node("analyze_viewpoints_modules", analyze_viewpoints_modules)
    workflow.add_node("map_figma_to_viewpoints", map_figma_to_viewpoints)
    workflow.add_node("create_semantic_correlation_map", create_semantic_correlation_map)
    workflow.add_node("map_checklist_to_figma_areas", map_checklist_to_figma_areas)
    workflow.add_node("validate_test_purpose_coverage", validate_test_purpose_coverage)
    workflow.add_node("deep_understanding_and_gap_analysis", deep_understanding_and_gap_analysis)
    workflow.add_node("generate_final_testcases", generate_final_testcases)
    
    # 添加测试用例质量评估和优化节点
    workflow.add_node("evaluate_testcase_quality", evaluate_testcase_quality)
    workflow.add_node("optimize_testcases", optimize_testcases)
    
    # 添加历史测试用例处理节点
    if use_historical_cases:
        workflow.add_node("process_historical_cases", process_historical_cases_node)
        workflow.add_node("extract_test_patterns", extract_test_patterns_node)
        workflow.add_node("analyze_differences", analyze_differences_node)
        workflow.add_node("evaluate_coverage", evaluate_coverage_node)
    
    # 定义工作流
    if use_historical_cases:
        # 使用历史测试用例的工作流
        workflow.set_entry_point("process_historical_cases")
        
        # 历史测试用例处理流程
        workflow.add_edge("process_historical_cases", "extract_test_patterns")
        workflow.add_edge("extract_test_patterns", "analyze_viewpoints_modules")
        
        # 基础流程
        workflow.add_edge("analyze_viewpoints_modules", "map_figma_to_viewpoints")
        workflow.add_edge("map_figma_to_viewpoints", "create_semantic_correlation_map")
        workflow.add_edge("create_semantic_correlation_map", "map_checklist_to_figma_areas")
        workflow.add_edge("map_checklist_to_figma_areas", "validate_test_purpose_coverage")
        
        # 差异分析和覆盖率评估
        workflow.add_edge("validate_test_purpose_coverage", "analyze_differences")
        workflow.add_edge("analyze_differences", "evaluate_coverage")
        workflow.add_edge("evaluate_coverage", "deep_understanding_and_gap_analysis")
        
        workflow.add_edge("deep_understanding_and_gap_analysis", "generate_final_testcases")
    else:
        # 不使用历史测试用例的工作流
        workflow.set_entry_point("analyze_viewpoints_modules")
        
        workflow.add_edge("analyze_viewpoints_modules", "map_figma_to_viewpoints")
        workflow.add_edge("map_figma_to_viewpoints", "create_semantic_correlation_map")
        workflow.add_edge("create_semantic_correlation_map", "map_checklist_to_figma_areas")
        workflow.add_edge("map_checklist_to_figma_areas", "validate_test_purpose_coverage")
        workflow.add_edge("validate_test_purpose_coverage", "deep_understanding_and_gap_analysis")
        workflow.add_edge("deep_understanding_and_gap_analysis", "generate_final_testcases")
    
    # 添加质量评估和优化流程
    workflow.add_edge("generate_final_testcases", "evaluate_testcase_quality")
    
    # 添加条件分支：根据质量评估结果决定是否需要优化
    workflow.add_conditional_edges(
        "evaluate_testcase_quality",
        lambda state: "optimize_testcases" if state.get("overall_quality", {}).get("improvement_needed", False) else END
    )
    
    # 添加优化后的循环：优化后重新评估
    workflow.add_edge("optimize_testcases", "evaluate_testcase_quality")
    
    return workflow.compile()

def run_enhanced_testcase_generation(figma_data: Dict[str, Any], viewpoints_file: Dict[str, Any], 
                                llm_client: LLMClient, historical_cases: Dict[str, Any] = None):
    """运行增强的测试用例生成流程
    
    Args:
        figma_data: Figma设计数据
        viewpoints_file: 测试观点文件
        llm_client: LLM客户端
        historical_cases: 历史测试用例（可选）
    """
    
    # 初始化状态
    initial_state = StateManager.create_initial_state(figma_data, viewpoints_file, historical_cases)
    
    # 构建并运行工作流
    use_historical_cases = historical_cases is not None
    workflow = build_enhanced_workflow(use_historical_cases)
    result = workflow.invoke(initial_state)
    
    return result

# 工作流节点包装器，用于LangGraph调用
def analyze_viewpoints_modules_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClientFactory.create_agent_client("analyze_viewpoints_modules")
    return analyze_viewpoints_modules(state, llm_client)

def map_figma_to_viewpoints_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClientFactory.create_agent_client("map_figma_to_viewpoints")
    return map_figma_to_viewpoints(state, llm_client)

def create_semantic_correlation_map_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClientFactory.create_agent_client("create_semantic_correlation_map")
    return create_semantic_correlation_map(state, llm_client)

def map_checklist_to_figma_areas_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClientFactory.create_agent_client("map_checklist_to_figma_areas")
    return map_checklist_to_figma_areas(state, llm_client)

def validate_test_purpose_coverage_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClientFactory.create_agent_client("validate_test_purpose_coverage")
    return validate_test_purpose_coverage(state, llm_client)

def deep_understanding_and_gap_analysis_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClientFactory.create_agent_client("deep_understanding_and_gap_analysis")
    return deep_understanding_and_gap_analysis(state, llm_client)

def generate_final_testcases_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClientFactory.create_agent_client("generate_testcases")
    return generate_final_testcases(state, llm_client)

def evaluate_testcase_quality_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClientFactory.create_agent_client("evaluate_testcase_quality")
    return evaluate_testcase_quality(state, llm_client)

def optimize_testcases_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClientFactory.create_agent_client("optimize_testcases")
    return optimize_testcases(state, llm_client)

def process_historical_cases_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClientFactory.create_agent_client("process_historical_cases")
    return process_historical_cases_node(state)

def extract_test_patterns_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClientFactory.create_agent_client("extract_test_patterns")
    return extract_test_patterns_node(state)

def analyze_differences_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClientFactory.create_agent_client("analyze_differences")
    return analyze_differences_node(state)

def evaluate_coverage_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClientFactory.create_agent_client("evaluate_coverage")
    return evaluate_coverage_node(state)

def build_enhanced_workflow_with_wrappers(use_historical_cases: bool = False):
    """构建使用包装器的增强工作流
    
    Args:
        use_historical_cases: 是否使用历史测试用例
    """
    
    workflow = StateGraph(StateManager.create_initial_state)
    
    # 添加基础节点（使用包装器）
    workflow.add_node("analyze_viewpoints_modules", analyze_viewpoints_modules_wrapper)
    workflow.add_node("map_figma_to_viewpoints", map_figma_to_viewpoints_wrapper)
    workflow.add_node("create_semantic_correlation_map", create_semantic_correlation_map_wrapper)
    workflow.add_node("map_checklist_to_figma_areas", map_checklist_to_figma_areas_wrapper)
    workflow.add_node("validate_test_purpose_coverage", validate_test_purpose_coverage_wrapper)
    workflow.add_node("deep_understanding_and_gap_analysis", deep_understanding_and_gap_analysis_wrapper)
    workflow.add_node("generate_final_testcases", generate_final_testcases_wrapper)
    
    # 添加测试用例质量评估和优化节点（使用包装器）
    workflow.add_node("evaluate_testcase_quality", evaluate_testcase_quality_wrapper)
    workflow.add_node("optimize_testcases", optimize_testcases_wrapper)
    
    # 添加历史测试用例处理节点（使用包装器）
    if use_historical_cases:
        workflow.add_node("process_historical_cases", process_historical_cases_wrapper)
        workflow.add_node("extract_test_patterns", extract_test_patterns_wrapper)
        workflow.add_node("analyze_differences", analyze_differences_wrapper)
        workflow.add_node("evaluate_coverage", evaluate_coverage_wrapper)
    
    # 定义工作流
    if use_historical_cases:
        # 使用历史测试用例的工作流
        workflow.set_entry_point("process_historical_cases")
        
        # 历史测试用例处理流程
        workflow.add_edge("process_historical_cases", "extract_test_patterns")
        workflow.add_edge("extract_test_patterns", "analyze_viewpoints_modules")
        
        # 基础流程
        workflow.add_edge("analyze_viewpoints_modules", "map_figma_to_viewpoints")
        workflow.add_edge("map_figma_to_viewpoints", "create_semantic_correlation_map")
        workflow.add_edge("create_semantic_correlation_map", "map_checklist_to_figma_areas")
        workflow.add_edge("map_checklist_to_figma_areas", "validate_test_purpose_coverage")
        
        # 差异分析和覆盖率评估
        workflow.add_edge("validate_test_purpose_coverage", "analyze_differences")
        workflow.add_edge("analyze_differences", "evaluate_coverage")
        workflow.add_edge("evaluate_coverage", "deep_understanding_and_gap_analysis")
        
        workflow.add_edge("deep_understanding_and_gap_analysis", "generate_final_testcases")
    else:
        # 不使用历史测试用例的工作流
        workflow.set_entry_point("analyze_viewpoints_modules")
        
        workflow.add_edge("analyze_viewpoints_modules", "map_figma_to_viewpoints")
        workflow.add_edge("map_figma_to_viewpoints", "create_semantic_correlation_map")
        workflow.add_edge("create_semantic_correlation_map", "map_checklist_to_figma_areas")
        workflow.add_edge("map_checklist_to_figma_areas", "validate_test_purpose_coverage")
        workflow.add_edge("validate_test_purpose_coverage", "deep_understanding_and_gap_analysis")
        workflow.add_edge("deep_understanding_and_gap_analysis", "generate_final_testcases")
    
    # 添加质量评估和优化流程
    workflow.add_edge("generate_final_testcases", "evaluate_testcase_quality")
    
    # 添加条件分支：根据质量评估结果决定是否需要优化
    workflow.add_conditional_edges(
        "evaluate_testcase_quality",
        lambda state: "optimize_testcases" if state.get("overall_quality", {}).get("improvement_needed", False) else END
    )
    
    # 添加优化后的循环：优化后重新评估
    workflow.add_edge("optimize_testcases", "evaluate_testcase_quality")
    
    return workflow.compile() 