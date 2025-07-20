from typing import Dict, Any
import json
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.llm_client import LLMClient
from state_management import StateManager

def map_figma_to_viewpoints(state: Dict[str, Any], llm_client: LLMClient) -> Dict[str, Any]:
    """
    第二步：将Figma文件与测试观点模块进行映射
    """
    figma_data = state["figma_data"]
    viewpoints_file = state["viewpoints_file"]
    modules_analysis = state["modules_analysis"]
    
    prompt = f"""
    你是一个专业的UI/UX分析师。请分析Figma文件，与测试观点模块进行映射：

    Figma文件结构：
    {json.dumps(figma_data, ensure_ascii=False, indent=2)}

    测试观点模块：
    {json.dumps(modules_analysis, ensure_ascii=False, indent=2)}

    请进行以下分析：
    1. Figma中是否包含测试观点文件中的所有模块
    2. 每个模块在Figma中的具体页面和组件位置
    3. 是否存在测试观点中提到的功能在Figma中缺失
    4. Figma中是否有测试观点未覆盖的功能
    5. 分析页面结构和组件层次关系

    请以JSON格式输出映射结果：
    {{
        "module_mapping": [
            {{
                "viewpoint_module": "测试观点模块名",
                "figma_pages": ["相关页面名称"],
                "figma_components": ["相关组件ID和名称"],
                "coverage_status": "FULL_COVERAGE/PARTIAL_COVERAGE/MISSING",
                "missing_features": ["缺失的功能描述"],
                "extra_features": ["额外功能描述"],
                "component_hierarchy": "组件层次结构"
            }}
        ],
        "coverage_gaps": ["覆盖缺口列表"],
        "recommendations": ["改进建议"],
        "mapping_quality_score": "映射质量评分(0-100)"
    }}
    """
    
    try:
        mapping_result = llm_client.generate(prompt)
        
        if isinstance(mapping_result, str):
            mapping_result = json.loads(mapping_result)
        
        updated_state = StateManager.update_state(state, {
            "figma_viewpoints_mapping": mapping_result
        })
        
        updated_state = StateManager.log_step(updated_state, 
            "map_figma_to_viewpoints", 
            f"成功映射 {len(mapping_result.get('module_mapping', []))} 个模块")
        
        return updated_state
        
    except Exception as e:
        error_result = {
            "module_mapping": [],
            "coverage_gaps": ["映射分析失败"],
            "recommendations": ["请检查Figma文件格式"],
            "mapping_quality_score": 0
        }
        
        updated_state = StateManager.update_state(state, {
            "figma_viewpoints_mapping": error_result
        })
        
        updated_state = StateManager.log_step(updated_state, 
            "map_figma_to_viewpoints", 
            f"映射失败: {str(e)}")
        
        return updated_state 