from typing import Dict, Any, List
import json
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.llm_client import LLMClient
from state_management import StateManager

def map_checklist_to_figma_areas(state: Dict[str, Any], llm_client: LLMClient) -> Dict[str, Any]:
    """
    第三步：将每个checklist项目映射到Figma中的具体功能区域
    """
    figma_data = state["figma_data"]
    viewpoints_file = state["viewpoints_file"]
    figma_viewpoints_mapping = state["figma_viewpoints_mapping"]
    
    detailed_mapping = []
    
    # 遍历所有测试观点和checklist项目
    for module_name, viewpoints in viewpoints_file.items():
        for viewpoint in viewpoints:
            if isinstance(viewpoint, dict):
                viewpoint_name = viewpoint.get('viewpoint', '')
                checklist_items = viewpoint.get('checklist', [])
                expected_purpose = viewpoint.get('expected_purpose', '')
            else:
                viewpoint_name = str(viewpoint)
                checklist_items = []
                expected_purpose = ''
            
            # 为每个checklist项目创建映射
            for i, item in enumerate(checklist_items):
                prompt = f"""
                你是一个专业的测试分析师。请分析checklist项目，在Figma中定位对应功能区域：

                Checklist项目：{item}
                所属模块：{module_name}
                测试观点：{viewpoint_name}
                预期目的：{expected_purpose}
                项目序号：{i+1}

                Figma文件结构：
                {json.dumps(figma_data, ensure_ascii=False, indent=2)}

                请分析：
                1. 这个checklist项目在Figma中对应的具体页面
                2. 涉及的具体组件和交互元素
                3. 用户操作路径和步骤
                4. 预期结果验证点
                5. 测试的复杂程度

                请以JSON格式输出：
                {{
                    "checklist_item": "检查项目内容",
                    "module": "所属模块",
                    "viewpoint": "测试观点",
                    "figma_page": "页面名称",
                    "components": ["相关组件ID和名称"],
                    "user_actions": ["用户操作步骤"],
                    "verification_points": ["验证点"],
                    "complexity": "SIMPLE/MEDIUM/COMPLEX",
                    "test_priority": "HIGH/MEDIUM/LOW",
                    "estimated_effort": "预估测试时间(分钟)"
                }}
                """
                
                try:
                    item_mapping = llm_client.generate(prompt)
                    
                    if isinstance(item_mapping, str):
                        item_mapping = json.loads(item_mapping)
                    
                    # 添加元数据
                    item_mapping.update({
                        "item_index": i,
                        "module_name": module_name,
                        "viewpoint_name": viewpoint_name
                    })
                    
                    detailed_mapping.append(item_mapping)
                    
                except Exception as e:
                    # 处理单个项目映射失败
                    error_mapping = {
                        "checklist_item": item,
                        "module": module_name,
                        "viewpoint": viewpoint_name,
                        "figma_page": "未知",
                        "components": [],
                        "user_actions": [],
                        "verification_points": [],
                        "complexity": "UNKNOWN",
                        "test_priority": "MEDIUM",
                        "estimated_effort": 0,
                        "error": str(e)
                    }
                    detailed_mapping.append(error_mapping)
    
    updated_state = StateManager.update_state(state, {
        "checklist_mapping": detailed_mapping
    })
    
    updated_state = StateManager.log_step(updated_state, 
        "map_checklist_to_figma_areas", 
        f"成功映射 {len(detailed_mapping)} 个checklist项目")
    
    return updated_state 