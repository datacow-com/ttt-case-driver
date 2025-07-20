from typing import Dict, Any, List, Optional, Tuple
import json
import hashlib
import sys
import os
import copy
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.llm_client import LLMClient
from utils.cache_manager import cache_llm_call, cache_manager
from utils.intelligent_cache_manager import intelligent_cache_manager
from state_management import StateManager

def generate_semantic_correlation_cache_key(figma_data: Dict[str, Any], viewpoints_file: Dict[str, Any], 
                                          historical_patterns: Optional[Dict[str, Any]] = None) -> str:
    """生成语义关联映射的缓存键
    
    Args:
        figma_data: Figma设计数据
        viewpoints_file: 测试观点文件
        historical_patterns: 历史测试模式（可选）
        
    Returns:
        str: 缓存键
    """
    # 生成Figma数据的哈希
    figma_hash = hashlib.md5(json.dumps(figma_data, sort_keys=True).encode()).hexdigest()[:8]
    
    # 生成测试观点文件的哈希
    viewpoints_hash = hashlib.md5(json.dumps(viewpoints_file, sort_keys=True).encode()).hexdigest()[:8]
    
    # 生成历史模式的哈希（如果有）
    patterns_hash = ""
    if historical_patterns:
        patterns_hash = hashlib.md5(json.dumps(historical_patterns, sort_keys=True).encode()).hexdigest()[:8]
        return f"semantic_corr_{figma_hash}_{viewpoints_hash}_{patterns_hash}"
    
    return f"semantic_corr_{figma_hash}_{viewpoints_hash}"

def build_basic_correlations(figma_data: Dict[str, Any], viewpoints_data: Dict[str, Any], 
                           historical_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """构建基础语义关联
    
    Args:
        figma_data: Figma设计数据
        viewpoints_data: 测试观点数据
        historical_data: 历史测试数据（可选）
        
    Returns:
        Dict[str, Any]: 基础语义关联图谱
    """
    # 初始化关联图谱
    correlation_map = {
        "component_test_mapping": {},
        "criterion_pattern_mapping": {},
        "navigation_scenario_mapping": {},
        "metadata": {
            "total_components": len(figma_data.get("component_hierarchy", {})),
            "total_criteria": sum(len(criteria) for criteria in viewpoints_data.get("test_criteria", {}).values()),
            "total_patterns": 0,
            "total_paths": len(figma_data.get("navigation_paths", {})),
            "coverage_statistics": {},
            "generation_timestamp": datetime.now().isoformat()
        }
    }
    
    # 1. 构建组件-测试标准映射
    component_hierarchy = figma_data.get("component_hierarchy", {})
    test_criteria = viewpoints_data.get("test_criteria", {})
    priority_definitions = viewpoints_data.get("priority_definitions", {})
    
    for component_id, component in component_hierarchy.items():
        component_type = component.get("type", "UNKNOWN")
        
        # 跳过不需要测试的组件类型
        if component_type in ["GROUP", "FRAME", "INSTANCE", "VECTOR"]:
            continue
            
        # 标准化组件类型
        normalized_type = normalize_component_type(component_type)
        
        # 查找适用的测试标准
        applicable_criteria = []
        if normalized_type in test_criteria:
            for criterion in test_criteria[normalized_type]:
                applicable_criteria.append({
                    "criterion_id": criterion.get("id", f"CRIT-{len(applicable_criteria)+1}"),
                    "criterion_name": criterion.get("name", ""),
                    "priority": criterion.get("priority", "MEDIUM"),
                    "category": criterion.get("category", "Functional"),
                    "checklist": criterion.get("checklist", [])
                })
        
        # 如果没有找到特定类型的测试标准，尝试使用通用标准
        if not applicable_criteria and "GENERIC" in test_criteria:
            for criterion in test_criteria["GENERIC"]:
                applicable_criteria.append({
                    "criterion_id": criterion.get("id", f"CRIT-G-{len(applicable_criteria)+1}"),
                    "criterion_name": criterion.get("name", ""),
                    "priority": criterion.get("priority", "MEDIUM"),
                    "category": criterion.get("category", "Functional"),
                    "checklist": criterion.get("checklist", [])
                })
        
        # 计算组件优先级分数
        priority_score = calculate_component_priority(component, priority_definitions)
        
        # 确定组件复杂度
        complexity_level = determine_component_complexity(component)
        
        # 构建组件映射
        correlation_map["component_test_mapping"][component_id] = {
            "component_type": component_type,
            "component_path": get_component_path(component),
            "applicable_criteria": applicable_criteria,
            "priority_score": priority_score,
            "complexity_level": complexity_level
        }
    
    # 2. 构建导航路径-测试场景映射
    navigation_paths = figma_data.get("navigation_paths", {})
    
    for path_id, path in navigation_paths.items():
        # 识别路径涉及的组件
        involved_components = identify_path_components(path, component_hierarchy)
        
        # 收集路径需要的测试标准
        required_criteria = []
        for component_id in involved_components:
            if component_id in correlation_map["component_test_mapping"]:
                for criterion in correlation_map["component_test_mapping"][component_id]["applicable_criteria"]:
                    criterion_id = criterion["criterion_id"]
                    if criterion_id not in required_criteria:
                        required_criteria.append(criterion_id)
        
        # 构建导航路径映射
        correlation_map["navigation_scenario_mapping"][path_id] = {
            "path_name": path.get("name", f"Path {path_id}"),
            "path_sequence": path.get("sequence", []),
            "involved_components": involved_components,
            "required_criteria": required_criteria,
            "historical_scenarios": []  # 初始为空，后续增强时添加
        }
    
    # 3. 如果有历史数据，构建测试标准-历史模式映射
    if historical_data:
        test_patterns = historical_data.get("test_patterns", {})
        
        for component_type, criteria_list in test_criteria.items():
            # 检查是否有该组件类型的历史测试模式
            if component_type not in test_patterns:
                continue
                
            patterns = test_patterns[component_type]
            
            # 遍历该组件类型的所有测试标准
            for criterion in criteria_list:
                criterion_id = criterion.get("id", "")
                
                # 初始化该测试标准的映射
                if criterion_id and criterion_id not in correlation_map["criterion_pattern_mapping"]:
                    correlation_map["criterion_pattern_mapping"][criterion_id] = {"matching_patterns": []}
                
                # 寻找匹配的历史测试模式
                for pattern in patterns:
                    # 计算测试标准与历史模式的匹配度
                    match_confidence = calculate_pattern_match_confidence(criterion, pattern)
                    
                    # 如果匹配度超过阈值，添加到匹配列表
                    if match_confidence >= 0.7:  # 70%的匹配度阈值
                        pattern_id = pattern.get("id", f"PATTERN-{len(correlation_map['criterion_pattern_mapping'][criterion_id]['matching_patterns'])+1}")
                        
                        correlation_map["criterion_pattern_mapping"][criterion_id]["matching_patterns"].append({
                            "pattern_id": pattern_id,
                            "pattern_name": pattern.get("name", ""),
                            "match_confidence": match_confidence,
                            "test_steps": extract_test_steps_from_pattern(pattern),
                            "validation_points": extract_validation_points(pattern),
                            "historical_defects": extract_historical_defects(pattern)
                        })
        
        # 更新统计信息
        correlation_map["metadata"]["total_patterns"] = sum(
            len(patterns) for patterns in test_patterns.values()
        )
    
    return correlation_map

def enhance_correlations(basic_correlation_map: Dict[str, Any], figma_data: Dict[str, Any], 
                        viewpoints_data: Dict[str, Any], historical_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """增强语义关联
    
    Args:
        basic_correlation_map: 基础语义关联图谱
        figma_data: Figma设计数据
        viewpoints_data: 测试观点数据
        historical_data: 历史测试数据（可选）
        
    Returns:
        Dict[str, Any]: 增强的语义关联图谱
    """
    enhanced_map = copy.deepcopy(basic_correlation_map)
    
    # 1. 如果有历史数据，增强导航路径-测试场景映射
    if historical_data and "test_scenarios" in historical_data:
        historical_scenarios = historical_data["test_scenarios"]
        
        for path_id, path_mapping in enhanced_map["navigation_scenario_mapping"].items():
            path_name = path_mapping["path_name"]
            path_sequence = path_mapping["path_sequence"]
            
            # 寻找匹配的历史测试场景
            matching_scenarios = []
            for scenario in historical_scenarios:
                # 计算路径与历史场景的匹配度
                match_confidence = calculate_scenario_match_confidence(path_name, path_sequence, scenario)
                
                # 如果匹配度超过阈值，添加到匹配列表
                if match_confidence >= 0.6:  # 60%的匹配度阈值
                    scenario_id = scenario.get("id", f"SCENARIO-{len(matching_scenarios)+1}")
                    
                    matching_scenarios.append({
                        "scenario_id": scenario_id,
                        "scenario_name": scenario.get("name", ""),
                        "match_confidence": match_confidence,
                        "integrated_steps": extract_integrated_steps(scenario),
                        "expected_outcomes": extract_expected_outcomes(scenario)
                    })
            
            # 更新匹配的历史场景
            enhanced_map["navigation_scenario_mapping"][path_id]["historical_scenarios"] = matching_scenarios
    
    # 2. 评估关联置信度
    enhanced_map = evaluate_correlation_confidence(enhanced_map)
    
    return enhanced_map

def integrate_semantic_correlations(enhanced_map: Dict[str, Any], figma_data: Dict[str, Any], 
                                  viewpoints_data: Dict[str, Any], 
                                  historical_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """整合语义关联，生成最终的语义关联图谱
    
    Args:
        enhanced_map: 增强的语义关联图谱
        figma_data: Figma设计数据
        viewpoints_data: 测试观点数据
        historical_data: 历史测试数据（可选）
        
    Returns:
        Dict[str, Any]: 整合的语义关联图谱
    """
    integrated_map = copy.deepcopy(enhanced_map)
    
    # 1. 整合组件-测试标准映射和测试标准-历史模式映射
    if "criterion_pattern_mapping" in integrated_map and integrated_map["criterion_pattern_mapping"]:
        for component_id, component_mapping in integrated_map["component_test_mapping"].items():
            for i, criterion in enumerate(component_mapping["applicable_criteria"]):
                criterion_id = criterion["criterion_id"]
                if criterion_id in integrated_map["criterion_pattern_mapping"]:
                    # 添加匹配的历史模式引用
                    integrated_map["component_test_mapping"][component_id]["applicable_criteria"][i]["matching_patterns"] = [
                        {
                            "pattern_id": pattern["pattern_id"],
                            "match_confidence": pattern["match_confidence"]
                        }
                        for pattern in integrated_map["criterion_pattern_mapping"][criterion_id]["matching_patterns"]
                    ]
    
    # 2. 整合导航路径-测试场景映射与组件测试标准
    for path_id, path_mapping in integrated_map["navigation_scenario_mapping"].items():
        # 收集路径涉及的组件的详细测试标准
        detailed_criteria = []
        for component_id in path_mapping["involved_components"]:
            if component_id in integrated_map["component_test_mapping"]:
                for criterion in integrated_map["component_test_mapping"][component_id]["applicable_criteria"]:
                    if criterion["criterion_id"] in path_mapping["required_criteria"]:
                        detailed_criteria.append({
                            "criterion_id": criterion["criterion_id"],
                            "criterion_name": criterion["criterion_name"],
                            "component_id": component_id,
                            "priority": criterion["priority"]
                        })
        
        # 更新路径映射中的详细测试标准
        integrated_map["navigation_scenario_mapping"][path_id]["detailed_criteria"] = detailed_criteria
    
    # 3. 计算覆盖率统计
    coverage_stats = calculate_coverage_statistics(integrated_map)
    integrated_map["metadata"]["coverage_statistics"] = coverage_stats
    
    return integrated_map

def create_semantic_correlation_map(state: Dict[str, Any], llm_client: LLMClient = None) -> Dict[str, Any]:
    """创建语义关联映射并更新状态
    
    Args:
        state: 当前工作流状态
        llm_client: LLM客户端（可选）
        
    Returns:
        Dict[str, Any]: 更新后的状态
    """
    # 从状态中获取必要数据
    figma_data = state.get("figma_data", {})
    viewpoints_file = state.get("viewpoints_file", {})
    historical_cases = state.get("historical_cases")
    historical_patterns = state.get("historical_patterns")
    
    # 生成缓存键
    cache_key = generate_semantic_correlation_cache_key(figma_data, viewpoints_file, historical_patterns)
    
    # 尝试从缓存获取语义关联映射
    cached_map = intelligent_cache_manager.get_with_intelligence(cache_key)
    if cached_map is not None:
        # 更新状态并返回
        state["semantic_correlation_map"] = cached_map
        state = StateManager.log_step(state, 
            "create_semantic_correlation_map", 
            f"从缓存加载语义关联映射 (缓存键: {cache_key})")
        return state
    
    # 如果缓存中不存在，创建新的语义关联映射
    
    # 1. 构建基础关联
    basic_map = build_basic_correlations(figma_data, viewpoints_file, historical_patterns)
    
    # 2. 增强关联
    enhanced_map = enhance_correlations(basic_map, figma_data, viewpoints_file, historical_patterns)
    
    # 3. 整合关联
    semantic_correlation_map = integrate_semantic_correlations(
        enhanced_map, figma_data, viewpoints_file, historical_patterns
    )
    
    # 更新状态
    state["semantic_correlation_map"] = semantic_correlation_map
    
    # 缓存结果
    intelligent_cache_manager.set_with_intelligence(cache_key, semantic_correlation_map, ttl=3600)
    
    # 记录日志
    state = StateManager.log_step(state, 
        "create_semantic_correlation_map", 
        f"创建语义关联映射 (组件映射: {len(semantic_correlation_map['component_test_mapping'])})")
    
    return state

# 辅助函数

def normalize_component_type(component_type: str) -> str:
    """标准化组件类型"""
    component_type = component_type.upper()
    
    # 标准化常见组件类型
    component_type_mapping = {
        "BUTTON": ["BUTTON", "BTN"],
        "INPUT": ["INPUT", "TEXTFIELD", "TEXTBOX", "TEXTAREA"],
        "TEXT": ["TEXT", "LABEL", "PARAGRAPH"],
        "IMAGE": ["IMAGE", "IMG", "PICTURE"],
        "CHECKBOX": ["CHECKBOX", "CHECK"],
        "RADIO": ["RADIO", "RADIOBUTTON"],
        "SELECT": ["SELECT", "DROPDOWN", "COMBOBOX"],
        "LINK": ["LINK", "HYPERLINK", "A"]
    }
    
    # 查找匹配的标准类型
    for standard_type, variants in component_type_mapping.items():
        if component_type in variants:
            return standard_type
    
    return component_type

def calculate_component_priority(component: Dict[str, Any], priority_definitions: Dict[str, Any]) -> int:
    """计算组件优先级分数（0-100）"""
    # 简单实现：根据组件类型和位置计算优先级
    base_score = 50  # 默认中等优先级
    
    # 根据组件类型调整分数
    component_type = component.get("type", "").upper()
    type_scores = {
        "BUTTON": 20,
        "INPUT": 15,
        "LINK": 10,
        "CHECKBOX": 5,
        "RADIO": 5,
        "SELECT": 10,
        "TEXT": -5,
        "IMAGE": -10
    }
    
    type_score = type_scores.get(component_type, 0)
    base_score += type_score
    
    # 根据组件名称中的关键词调整分数
    component_name = component.get("name", "").lower()
    important_keywords = ["submit", "login", "register", "save", "delete", "confirm", "pay", "checkout"]
    for keyword in important_keywords:
        if keyword in component_name:
            base_score += 15
            break
    
    # 确保分数在0-100范围内
    return max(0, min(100, base_score))

def determine_component_complexity(component: Dict[str, Any]) -> str:
    """确定组件复杂度（LOW/MEDIUM/HIGH）"""
    # 简单实现：根据组件类型和子组件数量确定复杂度
    component_type = component.get("type", "").upper()
    children_count = len(component.get("children", []))
    
    if component_type in ["TEXT", "IMAGE", "RECTANGLE", "ELLIPSE"]:
        return "LOW"
    elif component_type in ["BUTTON", "CHECKBOX", "RADIO", "LINK"]:
        return "MEDIUM"
    elif component_type in ["INPUT", "SELECT", "DROPDOWN", "FORM"]:
        return "MEDIUM"
    elif children_count > 5:
        return "HIGH"
    elif children_count > 2:
        return "MEDIUM"
    else:
        return "LOW"

def get_component_path(component: Dict[str, Any]) -> str:
    """获取组件路径"""
    # 简单实现：返回组件名称或ID
    return component.get("name", component.get("id", ""))

def identify_path_components(path: Dict[str, Any], component_hierarchy: Dict[str, Any]) -> List[str]:
    """识别路径涉及的组件"""
    # 简单实现：返回路径中明确指定的组件ID
    return path.get("components", [])

def calculate_pattern_match_confidence(criterion: Dict[str, Any], pattern: Dict[str, Any]) -> float:
    """计算测试标准与历史模式的匹配度（0-1）"""
    # 简单实现：根据名称和描述的相似度计算匹配度
    criterion_name = criterion.get("name", "").lower()
    pattern_name = pattern.get("name", "").lower()
    
    # 名称完全匹配
    if criterion_name == pattern_name:
        return 1.0
    
    # 名称部分匹配
    if criterion_name in pattern_name or pattern_name in criterion_name:
        return 0.8
    
    # 检查关键词匹配
    criterion_keywords = set(criterion_name.split())
    pattern_keywords = set(pattern_name.split())
    common_keywords = criterion_keywords.intersection(pattern_keywords)
    
    if common_keywords:
        return 0.5 + 0.3 * (len(common_keywords) / max(len(criterion_keywords), len(pattern_keywords)))
    
    return 0.5  # 默认中等匹配度

def extract_test_steps_from_pattern(pattern: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从历史模式中提取测试步骤"""
    # 简单实现：返回模式中的测试步骤
    steps = pattern.get("steps", [])
    if not steps:
        return []
    
    result = []
    for i, step in enumerate(steps):
        result.append({
            "step_id": i + 1,
            "action": step.get("action", ""),
            "target": step.get("target", ""),
            "description": step.get("description", "")
        })
    
    return result

def extract_validation_points(pattern: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从历史模式中提取验证点"""
    # 简单实现：返回模式中的验证点
    validation_points = pattern.get("validation_points", [])
    if not validation_points:
        return []
    
    result = []
    for i, point in enumerate(validation_points):
        result.append({
            "point_id": i + 1,
            "aspect": point.get("aspect", ""),
            "expected": point.get("expected", ""),
            "threshold": point.get("threshold", "")
        })
    
    return result

def extract_historical_defects(pattern: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从历史模式中提取历史缺陷"""
    # 简单实现：返回模式中的历史缺陷
    defects = pattern.get("defects", [])
    if not defects:
        return []
    
    result = []
    for defect in defects:
        result.append({
            "defect_id": defect.get("id", ""),
            "description": defect.get("description", ""),
            "frequency": defect.get("frequency", "LOW")
        })
    
    return result

def calculate_scenario_match_confidence(path_name: str, path_sequence: List[str], 
                                      scenario: Dict[str, Any]) -> float:
    """计算路径与历史场景的匹配度（0-1）"""
    # 简单实现：根据名称和序列的相似度计算匹配度
    scenario_name = scenario.get("name", "").lower()
    path_name = path_name.lower()
    
    # 名称完全匹配
    if path_name == scenario_name:
        return 1.0
    
    # 名称部分匹配
    if path_name in scenario_name or scenario_name in path_name:
        return 0.8
    
    # 检查序列匹配
    scenario_sequence = scenario.get("sequence", [])
    if path_sequence and scenario_sequence:
        # 计算序列的相似度
        common_steps = set(path_sequence).intersection(set(scenario_sequence))
        if common_steps:
            return 0.5 + 0.3 * (len(common_steps) / max(len(path_sequence), len(scenario_sequence)))
    
    return 0.5  # 默认中等匹配度

def extract_integrated_steps(scenario: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从历史场景中提取集成测试步骤"""
    # 简单实现：返回场景中的集成测试步骤
    steps = scenario.get("steps", [])
    if not steps:
        return []
    
    result = []
    for i, step in enumerate(steps):
        result.append({
            "step_id": i + 1,
            "component_id": step.get("component_id", ""),
            "action": step.get("action", ""),
            "value": step.get("value", "")
        })
    
    return result

def extract_expected_outcomes(scenario: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从历史场景中提取预期结果"""
    # 简单实现：返回场景中的预期结果
    outcomes = scenario.get("outcomes", [])
    if not outcomes:
        return []
    
    result = []
    for i, outcome in enumerate(outcomes):
        result.append({
            "outcome_id": i + 1,
            "description": outcome.get("description", ""),
            "verification": outcome.get("verification", "")
        })
    
    return result

def evaluate_correlation_confidence(correlation_map: Dict[str, Any]) -> Dict[str, Any]:
    """评估关联置信度"""
    # 简单实现：为每个映射添加置信度评分
    result = copy.deepcopy(correlation_map)
    
    # 评估组件-测试标准映射的置信度
    for component_id, mapping in result["component_test_mapping"].items():
        mapping["confidence_score"] = 0.8  # 默认较高置信度
    
    # 评估测试标准-历史模式映射的置信度
    for criterion_id, mapping in result.get("criterion_pattern_mapping", {}).items():
        # 计算平均匹配置信度
        if mapping["matching_patterns"]:
            avg_confidence = sum(p["match_confidence"] for p in mapping["matching_patterns"]) / len(mapping["matching_patterns"])
            mapping["confidence_score"] = avg_confidence
        else:
            mapping["confidence_score"] = 0.5  # 默认中等置信度
    
    # 评估导航路径-测试场景映射的置信度
    for path_id, mapping in result["navigation_scenario_mapping"].items():
        # 计算平均匹配置信度
        if mapping["historical_scenarios"]:
            avg_confidence = sum(s["match_confidence"] for s in mapping["historical_scenarios"]) / len(mapping["historical_scenarios"])
            mapping["confidence_score"] = avg_confidence
        else:
            mapping["confidence_score"] = 0.6  # 默认较高置信度
    
    return result

def calculate_coverage_statistics(correlation_map: Dict[str, Any]) -> Dict[str, Any]:
    """计算覆盖率统计"""
    # 计算组件覆盖率
    total_components = len(correlation_map["component_test_mapping"])
    components_with_criteria = sum(1 for mapping in correlation_map["component_test_mapping"].values() 
                                if mapping["applicable_criteria"])
    component_coverage = components_with_criteria / total_components if total_components > 0 else 0
    
    # 计算测试标准-历史模式覆盖率
    total_criteria = sum(len(mapping["applicable_criteria"]) 
                       for mapping in correlation_map["component_test_mapping"].values())
    
    criteria_with_patterns = 0
    for mapping in correlation_map["component_test_mapping"].values():
        for criterion in mapping["applicable_criteria"]:
            if "matching_patterns" in criterion and criterion["matching_patterns"]:
                criteria_with_patterns += 1
    
    criterion_pattern_coverage = criteria_with_patterns / total_criteria if total_criteria > 0 else 0
    
    # 计算导航路径-测试场景覆盖率
    total_paths = len(correlation_map["navigation_scenario_mapping"])
    paths_with_scenarios = sum(1 for mapping in correlation_map["navigation_scenario_mapping"].values() 
                             if mapping["historical_scenarios"])
    path_scenario_coverage = paths_with_scenarios / total_paths if total_paths > 0 else 0
    
    return {
        "component_coverage": component_coverage,
        "criterion_pattern_coverage": criterion_pattern_coverage,
        "path_scenario_coverage": path_scenario_coverage,
        "overall_coverage": (component_coverage + criterion_pattern_coverage + path_scenario_coverage) / 3
    } 