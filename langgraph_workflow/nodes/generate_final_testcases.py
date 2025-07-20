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
    semantic_correlation_map = state.get("semantic_correlation_map", {})
    
    content = {
        "viewpoints_file": viewpoints_file,
        "checklist_mapping": checklist_mapping,
        "quality_analysis": quality_analysis,
        "test_purpose_validation": test_purpose_validation,
        "semantic_correlation_map_exists": bool(semantic_correlation_map)  # 只记录是否存在，不包含完整内容以减小缓存键大小
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
    
    # 检查是否有语义关联映射
    semantic_correlation_map = state.get("semantic_correlation_map")
    if semantic_correlation_map:
        # 使用语义关联映射生成测试用例
        return generate_testcases_with_semantic_correlation(state, llm_client)
    
    # 如果没有语义关联映射，使用原有逻辑生成测试用例
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
            error_testcase = {
                "test_case_id": f'TC-{test_case_id:03d}',
                "module": "补充测试",
                "viewpoint": "质量分析补充",
                "priority": "MEDIUM",
                "category": "补充测试",
                "preconditions": [],
                "test_steps": [],
                "test_data": [],
                "notes": f"生成失败: {str(e)}"
            }
            final_testcases.append(error_testcase)
            test_case_id += 1
    
    # 更新状态
    updated_state = StateManager.update_state(state, {
        "final_testcases": final_testcases
    })
    
    # 记录日志
    updated_state = StateManager.log_step(updated_state, 
        "generate_final_testcases", 
        f"生成 {len(final_testcases)} 个测试用例")
    
    # 缓存结果
    cache_manager.set(cache_key, updated_state, ttl=3600)
    
    return updated_state

def generate_testcases_with_semantic_correlation(state: Dict[str, Any], llm_client: LLMClient) -> Dict[str, Any]:
    """基于语义关联映射生成测试用例
    
    Args:
        state: 当前工作流状态
        llm_client: LLM客户端
        
    Returns:
        Dict[str, Any]: 更新后的状态
    """
    semantic_correlation_map = state["semantic_correlation_map"]
    final_testcases = []
    test_case_id = 1
    
    # 1. 基于组件-测试标准映射生成组件测试用例
    component_test_mapping = semantic_correlation_map.get("component_test_mapping", {})
    for component_id, mapping in component_test_mapping.items():
        component_type = mapping["component_type"]
        component_path = mapping["component_path"]
        
        for criterion in mapping["applicable_criteria"]:
            # 构建测试用例
            testcase = build_component_testcase(
                component_id, 
                component_type,
                component_path,
                criterion, 
                mapping,
                llm_client
            )
            
            # 设置测试用例ID
            testcase["test_case_id"] = f"TC-COMP-{test_case_id:03d}"
            test_case_id += 1
            
            final_testcases.append(testcase)
    
    # 2. 基于导航路径-测试场景映射生成集成测试用例
    navigation_scenario_mapping = semantic_correlation_map.get("navigation_scenario_mapping", {})
    for path_id, mapping in navigation_scenario_mapping.items():
        # 构建集成测试用例
        testcase = build_integration_testcase(
            path_id,
            mapping,
            semantic_correlation_map,
            llm_client
        )
        
        # 设置测试用例ID
        testcase["test_case_id"] = f"TC-FLOW-{test_case_id:03d}"
        test_case_id += 1
        
        final_testcases.append(testcase)
    
    # 更新状态
    updated_state = StateManager.update_state(state, {
        "final_testcases": final_testcases
    })
    
    # 记录日志
    updated_state = StateManager.log_step(updated_state, 
        "generate_final_testcases", 
        f"基于语义关联映射生成 {len(final_testcases)} 个测试用例")
    
    return updated_state

def build_component_testcase(component_id: str, component_type: str, component_path: str, 
                          criterion: Dict[str, Any], mapping: Dict[str, Any], 
                          llm_client: LLMClient) -> Dict[str, Any]:
    """构建组件测试用例
    
    Args:
        component_id: 组件ID
        component_type: 组件类型
        component_path: 组件路径
        criterion: 测试标准
        mapping: 组件映射
        llm_client: LLM客户端
        
    Returns:
        Dict[str, Any]: 测试用例
    """
    # 准备提示模板
    prompt = f"""
    你是一个专业的测试用例设计师。基于以下信息生成详细的组件测试用例：

    组件ID: {component_id}
    组件类型: {component_type}
    组件路径: {component_path}
    测试标准: {criterion["criterion_name"]}
    优先级: {criterion["priority"]}
    测试类别: {criterion["category"]}
    检查清单: {json.dumps(criterion["checklist"], ensure_ascii=False)}
    
    """
    
    # 如果有匹配的历史模式，添加到提示中
    if "matching_patterns" in criterion:
        patterns = criterion["matching_patterns"]
        if patterns:
            prompt += f"\n历史测试模式:"
            for pattern in patterns:
                prompt += f"\n- 模式: {pattern['pattern_id']}, 匹配度: {pattern['match_confidence']}"
    
    prompt += """
    请生成详细的测试用例，包括：
    1. 测试步骤
    2. 预期结果
    3. 前置条件
    4. 测试数据
    5. 边界情况处理
    6. 错误场景测试

    请以JSON格式输出：
    {
        "component_id": "组件ID",
        "component_type": "组件类型",
        "test_criterion": "测试标准",
        "priority": "优先级",
        "category": "测试类别",
        "preconditions": ["前置条件"],
        "test_steps": [
            {
                "step_number": "步骤编号",
                "step_description": "步骤描述",
                "expected_result": "预期结果"
            }
        ],
        "test_data": ["测试数据"],
        "edge_cases": ["边界情况"],
        "error_scenarios": ["错误场景"]
    }
    """
    
    try:
        # 调用LLM生成测试用例
        testcase_json = llm_client.generate(prompt)
        
        # 解析JSON结果
        if isinstance(testcase_json, str):
            testcase = json.loads(testcase_json)
        else:
            testcase = testcase_json
            
        # 添加必要的字段
        testcase["component_id"] = component_id
        testcase["component_type"] = component_type
        
        return testcase
        
    except Exception as e:
        # 处理错误情况
        return {
            "component_id": component_id,
            "component_type": component_type,
            "test_criterion": criterion["criterion_name"],
            "priority": criterion["priority"],
            "category": criterion["category"],
            "preconditions": [],
            "test_steps": [],
            "test_data": [],
            "edge_cases": [],
            "error_scenarios": [],
            "error": str(e)
        }

def build_integration_testcase(path_id: str, mapping: Dict[str, Any], 
                            semantic_correlation_map: Dict[str, Any], 
                            llm_client: LLMClient) -> Dict[str, Any]:
    """构建集成测试用例
    
    Args:
        path_id: 路径ID
        mapping: 路径映射
        semantic_correlation_map: 语义关联图谱
        llm_client: LLM客户端
        
    Returns:
        Dict[str, Any]: 测试用例
    """
    path_name = mapping["path_name"]
    path_sequence = mapping["path_sequence"]
    involved_components = mapping["involved_components"]
    
    # 获取详细的测试标准
    detailed_criteria = mapping.get("detailed_criteria", [])
    
    # 获取历史测试场景
    historical_scenarios = mapping.get("historical_scenarios", [])
    
    # 准备提示模板
    prompt = f"""
    你是一个专业的测试用例设计师。基于以下信息生成详细的集成测试用例：

    路径ID: {path_id}
    路径名称: {path_name}
    路径序列: {json.dumps(path_sequence, ensure_ascii=False)}
    涉及的组件: {json.dumps(involved_components, ensure_ascii=False)}
    测试标准: {json.dumps(detailed_criteria, ensure_ascii=False)}
    """
    
    # 如果有匹配的历史场景，添加到提示中
    if historical_scenarios:
        prompt += f"\n历史测试场景:"
        for scenario in historical_scenarios:
            prompt += f"\n- 场景: {scenario['scenario_name']}, 匹配度: {scenario['match_confidence']}"
            
            # 添加集成测试步骤
            if "integrated_steps" in scenario:
                prompt += f"\n  步骤:"
                for step in scenario["integrated_steps"]:
                    prompt += f"\n  - {step['action']} {step['component_id']} {step.get('value', '')}"
            
            # 添加预期结果
            if "expected_outcomes" in scenario:
                prompt += f"\n  预期结果:"
                for outcome in scenario["expected_outcomes"]:
                    prompt += f"\n  - {outcome['description']}"
    
    prompt += """
    请生成详细的集成测试用例，包括：
    1. 测试步骤（按照路径序列顺序）
    2. 预期结果
    3. 前置条件
    4. 测试数据
    5. 边界情况处理
    6. 错误场景测试

    请以JSON格式输出：
    {
        "path_id": "路径ID",
        "path_name": "路径名称",
        "test_type": "集成测试",
        "priority": "优先级",
        "preconditions": ["前置条件"],
        "test_steps": [
            {
                "step_number": "步骤编号",
                "component_id": "组件ID",
                "action": "操作",
                "input_data": "输入数据",
                "expected_result": "预期结果"
            }
        ],
        "test_data": ["测试数据"],
        "edge_cases": ["边界情况"],
        "error_scenarios": ["错误场景"]
    }
    """
    
    try:
        # 调用LLM生成测试用例
        testcase_json = llm_client.generate(prompt)
        
        # 解析JSON结果
        if isinstance(testcase_json, str):
            testcase = json.loads(testcase_json)
        else:
            testcase = testcase_json
            
        # 添加必要的字段
        testcase["path_id"] = path_id
        testcase["path_name"] = path_name
        
        return testcase
        
    except Exception as e:
        # 处理错误情况
        return {
            "path_id": path_id,
            "path_name": path_name,
            "test_type": "集成测试",
            "priority": "MEDIUM",
            "preconditions": [],
            "test_steps": [],
            "test_data": [],
            "edge_cases": [],
            "error_scenarios": [],
            "error": str(e)
        }