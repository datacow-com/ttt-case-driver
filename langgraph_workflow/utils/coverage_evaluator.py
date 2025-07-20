from typing import Dict, Any, List, Set, Tuple, Optional
import hashlib
from collections import defaultdict
from utils.intelligent_cache_manager import intelligent_cache_manager

class CoverageEvaluator:
    """覆盖率评估器 - 评估测试观点覆盖率"""
    
    @staticmethod
    def evaluate_coverage(viewpoints: Dict[str, Any], difference_report: Dict[str, Any], pattern_library: Dict[str, Any]) -> Dict[str, Any]:
        """评估测试观点覆盖率"""
        # 1. 提取组件覆盖率
        component_coverage = CoverageEvaluator._evaluate_component_coverage(viewpoints, difference_report)
        
        # 2. 提取操作覆盖率
        action_coverage = CoverageEvaluator._evaluate_action_coverage(viewpoints, pattern_library)
        
        # 3. 提取测试类别覆盖率
        category_coverage = CoverageEvaluator._evaluate_category_coverage(viewpoints, pattern_library)
        
        # 4. 识别覆盖率缺口
        coverage_gaps = CoverageEvaluator._identify_coverage_gaps(component_coverage, action_coverage, category_coverage)
        
        # 5. 推荐额外测试点
        recommendations = CoverageEvaluator._recommend_additional_viewpoints(coverage_gaps, viewpoints, pattern_library)
        
        # 6. 生成覆盖率报告
        coverage_report = {
            "component_coverage": component_coverage,
            "action_coverage": action_coverage,
            "category_coverage": category_coverage,
            "coverage_gaps": coverage_gaps,
            "recommendations": recommendations,
            "metadata": {
                "overall_coverage_score": CoverageEvaluator._calculate_overall_coverage_score(component_coverage, action_coverage, category_coverage),
                "gap_count": len(coverage_gaps),
                "recommendation_count": len(recommendations)
            }
        }
        
        return coverage_report
    
    @staticmethod
    def _evaluate_component_coverage(viewpoints: Dict[str, Any], difference_report: Dict[str, Any]) -> Dict[str, Any]:
        """评估组件覆盖率"""
        # 获取所有组件类型
        all_component_types = set()
        
        # 从差异报告中获取组件类型
        for component in difference_report.get('new_components', []):
            all_component_types.add(component.get('type', ''))
        
        for component in difference_report.get('modified_components', []):
            all_component_types.add(component.get('type', ''))
        
        # 从测试观点中获取组件类型
        for component_type in viewpoints.keys():
            all_component_types.add(component_type)
        
        # 移除空字符串
        all_component_types.discard('')
        
        # 计算每种组件类型的覆盖率
        component_coverage = {}
        for component_type in all_component_types:
            # 检查该组件类型是否有测试观点
            has_viewpoints = component_type in viewpoints
            
            # 检查该组件类型是否有新组件
            has_new_components = any(comp.get('type') == component_type for comp in difference_report.get('new_components', []))
            
            # 检查该组件类型是否有修改的组件
            has_modified_components = any(comp.get('type') == component_type for comp in difference_report.get('modified_components', []))
            
            # 计算覆盖状态
            if has_viewpoints:
                if has_new_components or has_modified_components:
                    status = "COVERED"
                else:
                    status = "OVER_COVERED"  # 有测试观点但没有新/修改的组件
            else:
                if has_new_components or has_modified_components:
                    status = "GAP"  # 有新/修改的组件但没有测试观点
                else:
                    status = "NOT_APPLICABLE"  # 既没有测试观点也没有新/修改的组件
            
            # 计算覆盖分数
            score = 1.0 if status == "COVERED" else (0.5 if status == "OVER_COVERED" else 0.0)
            
            component_coverage[component_type] = {
                "status": status,
                "score": score,
                "has_viewpoints": has_viewpoints,
                "has_new_components": has_new_components,
                "has_modified_components": has_modified_components,
                "viewpoint_count": len(viewpoints.get(component_type, [])) if has_viewpoints else 0
            }
        
        return component_coverage
    
    @staticmethod
    def _evaluate_action_coverage(viewpoints: Dict[str, Any], pattern_library: Dict[str, Any]) -> Dict[str, Any]:
        """评估操作覆盖率"""
        # 从模式库中提取所有操作
        all_actions = set()
        for component_type, patterns in pattern_library.get('component_patterns', {}).items():
            for pattern in patterns:
                action = pattern.get('action')
                if action:
                    all_actions.add(action)
        
        # 从测试观点中提取操作
        viewpoint_actions = set()
        for component_type, component_viewpoints in viewpoints.items():
            for viewpoint in component_viewpoints:
                # 尝试从观点名称或描述中提取操作
                if isinstance(viewpoint, dict):
                    viewpoint_text = viewpoint.get('viewpoint', '')
                    checklist = viewpoint.get('checklist', [])
                    
                    # 检查观点名称
                    for action in all_actions:
                        if action.lower() in viewpoint_text.lower():
                            viewpoint_actions.add(action)
                    
                    # 检查检查列表
                    for item in checklist:
                        for action in all_actions:
                            if action.lower() in item.lower():
                                viewpoint_actions.add(action)
                else:
                    # 字符串形式的观点
                    for action in all_actions:
                        if action.lower() in viewpoint.lower():
                            viewpoint_actions.add(action)
        
        # 计算每种操作的覆盖率
        action_coverage = {}
        for action in all_actions:
            # 检查该操作是否被测试观点覆盖
            is_covered = action in viewpoint_actions
            
            # 计算覆盖状态
            status = "COVERED" if is_covered else "GAP"
            
            # 计算覆盖分数
            score = 1.0 if is_covered else 0.0
            
            # 查找该操作在模式库中的重要性
            importance = 0.0
            for component_type, patterns in pattern_library.get('component_patterns', {}).items():
                for pattern in patterns:
                    if pattern.get('action') == action:
                        importance = max(importance, pattern.get('importance_score', 0.0))
            
            action_coverage[action] = {
                "status": status,
                "score": score,
                "is_covered": is_covered,
                "importance": importance
            }
        
        return action_coverage
    
    @staticmethod
    def _evaluate_category_coverage(viewpoints: Dict[str, Any], pattern_library: Dict[str, Any]) -> Dict[str, Any]:
        """评估测试类别覆盖率"""
        # 从模式库中提取所有测试类别
        all_categories = set()
        for pattern in pattern_library.get('general_patterns', []):
            category = pattern.get('category')
            if category:
                all_categories.add(category)
        
        # 如果模式库中没有类别，使用默认类别
        if not all_categories:
            all_categories = {"Functional", "UI/UX", "Performance", "Security", "Accessibility"}
        
        # 从测试观点中提取类别
        viewpoint_categories = set()
        for component_type, component_viewpoints in viewpoints.items():
            for viewpoint in component_viewpoints:
                if isinstance(viewpoint, dict):
                    category = viewpoint.get('category')
                    if category:
                        viewpoint_categories.add(category)
        
        # 计算每种类别的覆盖率
        category_coverage = {}
        for category in all_categories:
            # 检查该类别是否被测试观点覆盖
            is_covered = category in viewpoint_categories
            
            # 计算覆盖状态
            status = "COVERED" if is_covered else "GAP"
            
            # 计算覆盖分数
            score = 1.0 if is_covered else 0.0
            
            # 查找该类别在模式库中的重要性
            importance = 0.0
            for pattern in pattern_library.get('general_patterns', []):
                if pattern.get('category') == category:
                    importance = pattern.get('importance_score', 0.0)
            
            category_coverage[category] = {
                "status": status,
                "score": score,
                "is_covered": is_covered,
                "importance": importance,
                "viewpoint_count": sum(1 for component_viewpoints in viewpoints.values() 
                                     for vp in component_viewpoints 
                                     if isinstance(vp, dict) and vp.get('category') == category)
            }
        
        return category_coverage
    
    @staticmethod
    def _identify_coverage_gaps(component_coverage: Dict[str, Any], action_coverage: Dict[str, Any], category_coverage: Dict[str, Any]) -> List[Dict[str, Any]]:
        """识别覆盖率缺口"""
        gaps = []
        
        # 检查组件覆盖率缺口
        for component_type, coverage in component_coverage.items():
            if coverage['status'] == "GAP":
                gap = {
                    "type": "COMPONENT",
                    "name": component_type,
                    "importance": CoverageEvaluator._get_component_importance(component_type),
                    "reason": "缺少测试观点"
                }
                gaps.append(gap)
        
        # 检查操作覆盖率缺口
        for action, coverage in action_coverage.items():
            if coverage['status'] == "GAP":
                gap = {
                    "type": "ACTION",
                    "name": action,
                    "importance": coverage['importance'],
                    "reason": "操作未被测试观点覆盖"
                }
                gaps.append(gap)
        
        # 检查类别覆盖率缺口
        for category, coverage in category_coverage.items():
            if coverage['status'] == "GAP":
                gap = {
                    "type": "CATEGORY",
                    "name": category,
                    "importance": coverage['importance'],
                    "reason": "测试类别未被覆盖"
                }
                gaps.append(gap)
        
        # 按重要性排序
        gaps.sort(key=lambda x: x['importance'], reverse=True)
        
        return gaps
    
    @staticmethod
    def _recommend_additional_viewpoints(gaps: List[Dict[str, Any]], viewpoints: Dict[str, Any], pattern_library: Dict[str, Any]) -> List[Dict[str, Any]]:
        """推荐额外测试点"""
        recommendations = []
        
        # 处理组件缺口
        component_gaps = [gap for gap in gaps if gap['type'] == "COMPONENT"]
        for gap in component_gaps:
            component_type = gap['name']
            
            # 查找该组件类型的模式
            component_patterns = []
            for comp_type, patterns in pattern_library.get('component_patterns', {}).items():
                if comp_type.upper() == component_type.upper():
                    component_patterns = patterns
                    break
            
            # 基于模式生成推荐
            if component_patterns:
                for pattern in component_patterns[:3]:  # 最多推荐3个
                    action = pattern.get('action', '')
                    step_patterns = pattern.get('step_patterns', [])
                    result_patterns = pattern.get('result_patterns', [])
                    
                    # 构建推荐的测试观点
                    viewpoint_title = f"{action} {component_type}"
                    checklist = []
                    
                    # 从步骤模式中提取检查项
                    for step_pattern in step_patterns:
                        for template in step_pattern.get('step_templates', [])[:2]:
                            checklist.append(template)
                    
                    recommendation = {
                        "component_type": component_type,
                        "viewpoint": viewpoint_title,
                        "checklist": checklist,
                        "priority": "HIGH" if gap['importance'] > 1.0 else "MEDIUM",
                        "category": "Functional",  # 默认类别
                        "reason": f"覆盖{component_type}组件的{action}操作"
                    }
                    recommendations.append(recommendation)
            else:
                # 没有模式时使用默认推荐
                recommendation = {
                    "component_type": component_type,
                    "viewpoint": f"基本功能测试 - {component_type}",
                    "checklist": [
                        f"验证{component_type}组件的基本功能",
                        f"检查{component_type}组件的交互响应",
                        f"验证{component_type}组件的显示正确性"
                    ],
                    "priority": "HIGH" if gap['importance'] > 1.0 else "MEDIUM",
                    "category": "Functional",
                    "reason": f"覆盖{component_type}组件的基本功能"
                }
                recommendations.append(recommendation)
        
        # 处理类别缺口
        category_gaps = [gap for gap in gaps if gap['type'] == "CATEGORY"]
        for gap in category_gaps:
            category = gap['name']
            
            # 为每种缺失的类别推荐通用测试观点
            if category == "Performance":
                recommendation = {
                    "component_type": "GENERAL",
                    "viewpoint": "性能测试",
                    "checklist": [
                        "验证页面加载时间在可接受范围内",
                        "检查组件响应时间",
                        "验证大数据量下的性能表现"
                    ],
                    "priority": "MEDIUM",
                    "category": "Performance",
                    "reason": "覆盖性能测试类别"
                }
                recommendations.append(recommendation)
            elif category == "Security":
                recommendation = {
                    "component_type": "GENERAL",
                    "viewpoint": "安全性测试",
                    "checklist": [
                        "验证输入验证和过滤",
                        "检查敏感数据处理",
                        "验证权限控制"
                    ],
                    "priority": "HIGH",
                    "category": "Security",
                    "reason": "覆盖安全性测试类别"
                }
                recommendations.append(recommendation)
            elif category == "UI/UX":
                recommendation = {
                    "component_type": "GENERAL",
                    "viewpoint": "UI/UX测试",
                    "checklist": [
                        "验证界面布局和对齐",
                        "检查颜色和风格一致性",
                        "验证用户交互流程"
                    ],
                    "priority": "MEDIUM",
                    "category": "UI/UX",
                    "reason": "覆盖UI/UX测试类别"
                }
                recommendations.append(recommendation)
            elif category == "Accessibility":
                recommendation = {
                    "component_type": "GENERAL",
                    "viewpoint": "可访问性测试",
                    "checklist": [
                        "验证键盘导航",
                        "检查屏幕阅读器兼容性",
                        "验证颜色对比度"
                    ],
                    "priority": "MEDIUM",
                    "category": "Accessibility",
                    "reason": "覆盖可访问性测试类别"
                }
                recommendations.append(recommendation)
        
        return recommendations
    
    @staticmethod
    def _calculate_overall_coverage_score(component_coverage: Dict[str, Any], action_coverage: Dict[str, Any], category_coverage: Dict[str, Any]) -> float:
        """计算总体覆盖率分数"""
        # 计算组件覆盖率分数
        component_scores = [coverage['score'] for coverage in component_coverage.values()]
        component_avg_score = sum(component_scores) / len(component_scores) if component_scores else 0.0
        
        # 计算操作覆盖率分数
        action_scores = [coverage['score'] for coverage in action_coverage.values()]
        action_avg_score = sum(action_scores) / len(action_scores) if action_scores else 0.0
        
        # 计算类别覆盖率分数
        category_scores = [coverage['score'] for coverage in category_coverage.values()]
        category_avg_score = sum(category_scores) / len(category_scores) if category_scores else 0.0
        
        # 加权平均
        overall_score = (component_avg_score * 0.5) + (action_avg_score * 0.3) + (category_avg_score * 0.2)
        
        return round(overall_score, 2)
    
    @staticmethod
    def _get_component_importance(component_type: str) -> float:
        """获取组件类型的重要性"""
        # 组件重要性权重
        component_weights = {
            "BUTTON": 1.0,
            "INPUT": 1.2,
            "FORM": 1.3,
            "LINK": 0.8,
            "DROPDOWN": 1.0,
            "CHECKBOX": 0.9,
            "RADIO": 0.9,
            "MODAL": 1.1,
            "TEXT": 0.7,
            "IMAGE": 0.6,
            "CONTAINER": 0.5,
            "GENERAL": 0.5
        }
        
        return component_weights.get(component_type.upper(), 0.8)
    
    @staticmethod
    def evaluate_with_cache(viewpoints: Dict[str, Any], difference_report: Dict[str, Any], pattern_library: Dict[str, Any], cache_key_prefix: str = None) -> Dict[str, Any]:
        """带缓存的覆盖率评估"""
        # 生成缓存键
        if cache_key_prefix:
            cache_key = f"{cache_key_prefix}_coverage"
        else:
            # 基于输入数据生成哈希
            input_str = str(len(viewpoints)) + str(len(difference_report)) + str(len(pattern_library))
            input_hash = hashlib.md5(input_str.encode()).hexdigest()
            cache_key = f"coverage_{input_hash}"
        
        # 检查缓存
        cached_coverage = intelligent_cache_manager.get_with_intelligence(cache_key)
        if cached_coverage is not None:
            return cached_coverage
        
        # 评估覆盖率
        coverage = CoverageEvaluator.evaluate_coverage(viewpoints, difference_report, pattern_library)
        
        # 缓存结果
        intelligent_cache_manager.set_with_intelligence(cache_key, coverage, ttl=3600)
        
        return coverage 