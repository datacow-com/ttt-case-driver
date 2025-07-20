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
from utils.llm_client import LLMClient

def build_enhanced_workflow():
    """构建增强的测试用例生成工作流"""
    
    workflow = StateGraph(StateManager.create_initial_state)
    
    # 添加节点
    workflow.add_node("analyze_viewpoints_modules", analyze_viewpoints_modules)
    workflow.add_node("map_figma_to_viewpoints", map_figma_to_viewpoints)
    workflow.add_node("map_checklist_to_figma_areas", map_checklist_to_figma_areas)
    workflow.add_node("validate_test_purpose_coverage", validate_test_purpose_coverage)
    workflow.add_node("deep_understanding_and_gap_analysis", deep_understanding_and_gap_analysis)
    workflow.add_node("generate_final_testcases", generate_final_testcases)
    
    # 定义工作流
    workflow.set_entry_point("analyze_viewpoints_modules")
    
    workflow.add_edge("analyze_viewpoints_modules", "map_figma_to_viewpoints")
    workflow.add_edge("map_figma_to_viewpoints", "map_checklist_to_figma_areas")
    workflow.add_edge("map_checklist_to_figma_areas", "validate_test_purpose_coverage")
    workflow.add_edge("validate_test_purpose_coverage", "deep_understanding_and_gap_analysis")
    workflow.add_edge("deep_understanding_and_gap_analysis", "generate_final_testcases")
    
    workflow.add_edge("generate_final_testcases", END)
    
    return workflow.compile()

def run_enhanced_testcase_generation(figma_data: Dict[str, Any], viewpoints_file: Dict[str, Any], llm_client: LLMClient):
    """运行增强的测试用例生成流程"""
    
    # 初始化状态
    initial_state = StateManager.create_initial_state(figma_data, viewpoints_file)
    
    # 构建并运行工作流
    workflow = build_enhanced_workflow()
    result = workflow.invoke(initial_state)
    
    return result

# 工作流节点包装器，用于LangGraph调用
def analyze_viewpoints_modules_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClient(
        provider='gpt-4o',
        api_key=os.environ.get('OPENAI_API_KEY', ''),
        temperature=0.2
    )
    return analyze_viewpoints_modules(state, llm_client)

def map_figma_to_viewpoints_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClient(
        provider='gpt-4o',
        api_key=os.environ.get('OPENAI_API_KEY', ''),
        temperature=0.2
    )
    return map_figma_to_viewpoints(state, llm_client)

def map_checklist_to_figma_areas_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClient(
        provider='gpt-4o',
        api_key=os.environ.get('OPENAI_API_KEY', ''),
        temperature=0.2
    )
    return map_checklist_to_figma_areas(state, llm_client)

def validate_test_purpose_coverage_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClient(
        provider='gpt-4o',
        api_key=os.environ.get('OPENAI_API_KEY', ''),
        temperature=0.2
    )
    return validate_test_purpose_coverage(state, llm_client)

def deep_understanding_and_gap_analysis_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClient(
        provider='gpt-4o',
        api_key=os.environ.get('OPENAI_API_KEY', ''),
        temperature=0.2
    )
    return deep_understanding_and_gap_analysis(state, llm_client)

def generate_final_testcases_wrapper(state: Dict[str, Any]):
    """包装器函数，用于LangGraph节点调用"""
    llm_client = LLMClient(
        provider='gpt-4o',
        api_key=os.environ.get('OPENAI_API_KEY', ''),
        temperature=0.2
    )
    return generate_final_testcases(state, llm_client)

def build_enhanced_workflow_with_wrappers():
    """构建使用包装器的增强工作流"""
    
    workflow = StateGraph(StateManager.create_initial_state)
    
    # 添加节点（使用包装器）
    workflow.add_node("analyze_viewpoints_modules", analyze_viewpoints_modules_wrapper)
    workflow.add_node("map_figma_to_viewpoints", map_figma_to_viewpoints_wrapper)
    workflow.add_node("map_checklist_to_figma_areas", map_checklist_to_figma_areas_wrapper)
    workflow.add_node("validate_test_purpose_coverage", validate_test_purpose_coverage_wrapper)
    workflow.add_node("deep_understanding_and_gap_analysis", deep_understanding_and_gap_analysis_wrapper)
    workflow.add_node("generate_final_testcases", generate_final_testcases_wrapper)
    
    # 定义工作流
    workflow.set_entry_point("analyze_viewpoints_modules")
    
    workflow.add_edge("analyze_viewpoints_modules", "map_figma_to_viewpoints")
    workflow.add_edge("map_figma_to_viewpoints", "map_checklist_to_figma_areas")
    workflow.add_edge("map_checklist_to_figma_areas", "validate_test_purpose_coverage")
    workflow.add_edge("validate_test_purpose_coverage", "deep_understanding_and_gap_analysis")
    workflow.add_edge("deep_understanding_and_gap_analysis", "generate_final_testcases")
    
    workflow.add_edge("generate_final_testcases", END)
    
    return workflow.compile() 