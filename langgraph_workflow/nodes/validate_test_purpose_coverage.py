from typing import Dict, Any, List
import json
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.llm_client import LLMClient
from state_management import StateManager

def validate_test_purpose_coverage(state: Dict[str, Any], llm_client: LLMClient) -> Dict[str, Any]:
    """
    第四步：验证checklist是否满足测试目的
    """
    viewpoints_file = state["viewpoints_file"]
    checklist_mapping = state["checklist_mapping"]
    
    validation_results = []
    
    # 按模块和测试观点分组验证
    for module_name, viewpoints in viewpoints_file.items():
        for viewpoint in viewpoints:
            if isinstance(viewpoint, dict):
                viewpoint_name = viewpoint.get('viewpoint', '')
                expected_purpose = viewpoint.get('expected_purpose', '')
                checklist_items = viewpoint.get('checklist', [])
                priority = viewpoint.get('priority', 'MEDIUM')
                category = viewpoint.get('category', 'Functional')
            else:
                viewpoint_name = str(viewpoint)
                expected_purpose = ''
                checklist_items = []
                priority = 'MEDIUM'
                category = 'Functional'
            
            # 获取该测试观点对应的checklist映射
            related_checklist = [
                item for item in checklist_mapping 
                if item.get('module_name') == module_name and 
                   item.get('viewpoint_name') == viewpoint_name
            ]
            
            prompt = f"""
            你是一个专业的测试质量分析师。请验证测试目的覆盖度：

            测试目的：{expected_purpose}
            测试观点：{viewpoint_name}
            所属模块：{module_name}
            优先级：{priority}
            测试类别：{category}
            
            检查清单：{checklist_items}
            
            相关Figma映射：{json.dumps(related_checklist, ensure_ascii=False, indent=2)}

            请进行以下分析：
            1. 检查清单是否完全覆盖了测试目的
            2. 是否存在测试目的中提到的要求未被检查清单覆盖
            3. 检查清单中是否有冗余项目
            4. 建议补充的检查项目
            5. 测试覆盖的质量评估

            请以JSON格式输出验证结果：
            {{
                "test_purpose": "测试目的",
                "viewpoint": "测试观点",
                "module": "所属模块",
                "coverage_analysis": "覆盖度分析描述",
                "missing_coverage": ["缺失的覆盖点"],
                "redundant_items": ["冗余项目"],
                "suggested_additions": ["建议补充的检查项目"],
                "coverage_score": "覆盖度评分(0-100)",
                "quality_assessment": "质量评估",
                "recommendations": ["改进建议"]
            }}
            """
            
            try:
                validation_result = llm_client.generate(prompt)
                
                if isinstance(validation_result, str):
                    validation_result = json.loads(validation_result)
                
                validation_results.append(validation_result)
                
            except Exception as e:
                # 处理验证失败
                error_result = {
                    "test_purpose": expected_purpose,
                    "viewpoint": viewpoint_name,
                    "module": module_name,
                    "coverage_analysis": "验证失败",
                    "missing_coverage": [],
                    "redundant_items": [],
                    "suggested_additions": [],
                    "coverage_score": 0,
                    "quality_assessment": f"验证失败: {str(e)}",
                    "recommendations": ["请检查测试目的和检查清单的格式"]
                }
                validation_results.append(error_result)
    
    updated_state = StateManager.update_state(state, {
        "test_purpose_validation": validation_results
    })
    
    updated_state = StateManager.log_step(updated_state, 
        "validate_test_purpose_coverage", 
        f"成功验证 {len(validation_results)} 个测试观点")
    
    return updated_state 