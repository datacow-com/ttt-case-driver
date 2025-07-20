from typing import Dict, Any, List
import json
import sys
import os
import hashlib

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.llm_client import LLMClient
from state_management import StateManager
from utils.cache_manager import cache_llm_call, cache_manager

def generate_cache_key(state: Dict[str, Any]) -> str:
    """生成缓存键"""
    viewpoints_file = state.get("viewpoints_file", {})
    checklist_mapping = state.get("checklist_mapping", [])
    quality_analysis = state.get("quality_analysis", {})
    test_purpose_validation = state.get("test_purpose_validation", [])
    
    content = {
        "viewpoints_file": viewpoints_file,
        "checklist_mapping": checklist_mapping,
        "quality_analysis": quality_analysis,
        "test_purpose_validation": test_purpose_validation
    }
    return hashlib.md5(json.dumps(content, sort_keys=True).encode()).hexdigest()

@cache_llm_call(ttl=3600)  # 缓存LLM调用结果1小时
def generate_final_testcases(state: Dict[str, Any], llm_client: LLMClient) -> Dict[str, Any]:
    """
    第六步：基于完整分析生成最终测试用例（带缓存）
    """
    # 生成缓存键
    cache_key = generate_cache_key(state)
    
    # 检查缓存
    cached_result = cache_manager.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    viewpoints_file = state["viewpoints_file"]
    checklist_mapping = state["checklist_mapping"]
    quality_analysis = state["quality_analysis"]
    test_purpose_validation = state["test_purpose_validation"]
    
    final_testcases = []
    test_case_id = 1
    
    # 生成基于测试观点的测试用例
    for module_name, viewpoints in viewpoints_file.items():
        for viewpoint in viewpoints:
            if isinstance(viewpoint, dict):
                viewpoint_name = viewpoint.get('viewpoint', '')
                expected_purpose = viewpoint.get('expected_purpose', '')
                checklist_items = viewpoint.get('checklist', [])
                priority = viewpoint.get('priority', 'MEDIUM')
                category = viewpoint.get('category', 'Functional')
                test_id = viewpoint.get('test_id', f'TP-{test_case_id:03d}')
            else:
                viewpoint_name = str(viewpoint)
                expected_purpose = ''
                checklist_items = []
                priority = 'MEDIUM'
                category = 'Functional'
                test_id = f'TP-{test_case_id:03d}'
            
            # 获取相关的checklist映射
            related_checklist = [
                item for item in checklist_mapping 
                if item.get('module_name') == module_name and 
                   item.get('viewpoint_name') == viewpoint_name
            ]
            
            # 获取相关的质量分析
            related_validation = next(
                (v for v in test_purpose_validation 
                 if v.get('viewpoint') == viewpoint_name and v.get('module') == module_name),
                {}
            )
            
            prompt = f"""
            你是一个专业的测试用例设计师。基于完整分析生成详细的测试用例：

            模块：{module_name}
            测试观点：{viewpoint_name}
            预期目的：{expected_purpose}
            检查清单：{checklist_items}
            优先级：{priority}
            测试类别：{category}
            测试ID：{test_id}

            相关checklist映射：{json.dumps(related_checklist, ensure_ascii=False, indent=2)}
            测试目的验证：{json.dumps(related_validation, ensure_ascii=False, indent=2)}
            质量分析：{json.dumps(quality_analysis, ensure_ascii=False, indent=2)}

            请生成详细的测试用例，包括：
            1. 测试步骤（基于checklist项目）
            2. 预期结果（基于测试目的）
            3. 前置条件
            4. 测试数据
            5. 边界情况处理
            6. 错误场景测试

            请以JSON格式输出：
            {{
                "test_case_id": "测试用例ID",
                "module": "模块名称",
                "viewpoint": "测试观点",
                "priority": "优先级",
                "category": "测试类别",
                "preconditions": ["前置条件"],
                "test_steps": [
                    {{
                        "step_number": "步骤编号",
                        "step_description": "步骤描述",
                        "expected_result": "预期结果",
                        "checklist_item": "对应的检查项目",
                        "verification_points": ["验证点"]
                    }}
                ],
                "test_data": ["测试数据"],
                "edge_cases": ["边界情况"],
                "error_scenarios": ["错误场景"],
                "estimated_effort": "预估测试时间(分钟)",
                "dependencies": ["依赖关系"],
                "notes": "备注"
            }}
            """
            
            try:
                testcase = llm_client.generate(prompt)
                
                if isinstance(testcase, str):
                    testcase = json.loads(testcase)
                
                # 确保测试用例ID正确
                testcase['test_case_id'] = test_id
                
                final_testcases.append(testcase)
                test_case_id += 1
                
            except Exception as e:
                # 处理测试用例生成失败
                error_testcase = {
                    "test_case_id": test_id,
                    "module": module_name,
                    "viewpoint": viewpoint_name,
                    "priority": priority,
                    "category": category,
                    "preconditions": [],
                    "test_steps": [],
                    "test_data": [],
                    "edge_cases": [],
                    "error_scenarios": [],
                    "estimated_effort": 0,
                    "dependencies": [],
                    "notes": f"生成失败: {str(e)}"
                }
                final_testcases.append(error_testcase)
                test_case_id += 1
    
    # 生成基于质量分析的补充测试用例
    additional_scenarios = quality_analysis.get('additional_scenarios', [])
    for scenario in additional_scenarios:
        prompt = f"""
        基于质量分析生成补充测试用例：

        场景信息：{json.dumps(scenario, ensure_ascii=False, indent=2)}

        请生成补充测试用例：
        {{
            "test_case_id": "TC-{test_case_id:03d}",
            "module": "补充测试",
            "viewpoint": "质量分析补充",
            "priority": "优先级",
            "category": "补充测试",
            "preconditions": ["前置条件"],
            "test_steps": [
                {{
                    "step_number": "步骤编号",
                    "step_description": "步骤描述",
                    "expected_result": "预期结果"
                }}
            ],
            "test_data": ["测试数据"],
            "estimated_effort": "预估测试时间(分钟)",
            "notes": "基于质量分析的补充测试"
        }}
        """
        
        try:
            additional_testcase = llm_client.generate(prompt)
            
            if isinstance(additional_testcase, str):
                additional_testcase = json.loads(additional_testcase)
            
            additional_testcase['test_case_id'] = f'TC-{test_case_id:03d}'
            final_testcases.append(additional_testcase)
            test_case_id += 1
            
        except Exception as e:
            # 处理补充测试用例生成失败
            error_additional = {
                "test_case_id": f'TC-{test_case_id:03d}',
                "module": "补充测试",
                "viewpoint": "质量分析补充",
                "priority": "MEDIUM",
                "category": "补充测试",
                "preconditions": [],
                "test_steps": [],
                "test_data": [],
                "estimated_effort": 0,
                "notes": f"补充测试生成失败: {str(e)}"
            }
            final_testcases.append(error_additional)
            test_case_id += 1
    
    # 更新状态
    updated_state = StateManager.update_state(state, {
        "final_testcases": final_testcases
    })
    
    # 记录日志
    updated_state = StateManager.log_step(updated_state, 
        "generate_final_testcases", 
        f"成功生成 {len(final_testcases)} 个最终测试用例")
    
    # 缓存结果
    cache_manager.set(cache_key, updated_state, ttl=3600)
    
    return updated_state