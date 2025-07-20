from typing import Dict, Any
import json
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.llm_client import LLMClient
from state_management import StateManager

def deep_understanding_and_gap_analysis(state: Dict[str, Any], llm_client: LLMClient) -> Dict[str, Any]:
    """
    第五步：大模型的深度理解与查缺补漏
    """
    figma_data = state["figma_data"]
    viewpoints_file = state["viewpoints_file"]
    modules_analysis = state["modules_analysis"]
    figma_viewpoints_mapping = state["figma_viewpoints_mapping"]
    checklist_mapping = state["checklist_mapping"]
    test_purpose_validation = state["test_purpose_validation"]
    
    prompt = f"""
    你是一个资深的测试架构师和质量专家。基于前面的分析，进行深度理解与查缺补漏：

    综合分析数据：
    1. Figma文件结构：{json.dumps(figma_data, ensure_ascii=False, indent=2)}
    2. 测试观点文件：{json.dumps(viewpoints_file, ensure_ascii=False, indent=2)}
    3. 模块分析结果：{json.dumps(modules_analysis, ensure_ascii=False, indent=2)}
    4. Figma映射结果：{json.dumps(figma_viewpoints_mapping, ensure_ascii=False, indent=2)}
    5. Checklist映射：{json.dumps(checklist_mapping, ensure_ascii=False, indent=2)}
    6. 测试目的验证：{json.dumps(test_purpose_validation, ensure_ascii=False, indent=2)}

    请进行深度分析：
    1. 识别测试覆盖的盲点和遗漏
    2. 发现潜在的边界情况和异常场景
    3. 考虑用户体验的完整性和一致性
    4. 识别性能、安全、兼容性等非功能性需求
    5. 分析测试用例的优先级和依赖关系
    6. 建议补充的测试场景和用例

    请以JSON格式输出深度分析结果：
    {{
        "blind_spots": [
            {{
                "category": "盲点类别",
                "description": "盲点描述",
                "impact": "影响程度",
                "suggestion": "建议的测试场景"
            }}
        ],
        "edge_cases": [
            {{
                "scenario": "边界场景描述",
                "trigger_conditions": "触发条件",
                "expected_behavior": "预期行为",
                "priority": "优先级"
            }}
        ],
        "ux_gaps": [
            {{
                "gap_type": "用户体验缺口类型",
                "description": "缺口描述",
                "affected_modules": ["受影响模块"],
                "suggestion": "改进建议"
            }}
        ],
        "non_functional_needs": [
            {{
                "category": "非功能性需求类别",
                "requirement": "需求描述",
                "test_scenarios": ["测试场景"],
                "priority": "优先级"
            }}
        ],
        "additional_scenarios": [
            {{
                "scenario_name": "场景名称",
                "description": "场景描述",
                "test_steps": ["测试步骤"],
                "expected_results": ["预期结果"],
                "priority": "优先级"
            }}
        ],
        "overall_quality_score": "整体质量评分(0-100)",
        "risk_assessment": "风险评估",
        "recommendations": ["改进建议"],
        "next_steps": ["下一步行动建议"]
    }}
    """
    
    try:
        gap_analysis = llm_client.generate(prompt)
        
        if isinstance(gap_analysis, str):
            gap_analysis = json.loads(gap_analysis)
        
        updated_state = StateManager.update_state(state, {
            "quality_analysis": gap_analysis
        })
        
        updated_state = StateManager.log_step(updated_state, 
            "deep_understanding_and_gap_analysis", 
            f"完成深度分析，识别 {len(gap_analysis.get('blind_spots', []))} 个盲点")
        
        return updated_state
        
    except Exception as e:
        error_result = {
            "blind_spots": [],
            "edge_cases": [],
            "ux_gaps": [],
            "non_functional_needs": [],
            "additional_scenarios": [],
            "overall_quality_score": 0,
            "risk_assessment": f"分析失败: {str(e)}",
            "recommendations": ["请检查输入数据格式"],
            "next_steps": ["重新运行分析"]
        }
        
        updated_state = StateManager.update_state(state, {
            "quality_analysis": error_result
        })
        
        updated_state = StateManager.log_step(updated_state, 
            "deep_understanding_and_gap_analysis", 
            f"深度分析失败: {str(e)}")
        
        return updated_state 