from typing import Dict, Any, List, Set, Tuple, Optional
import hashlib
from collections import Counter, defaultdict
from utils.intelligent_cache_manager import intelligent_cache_manager

class TestPatternExtractor:
    """测试模式提取器 - 从历史测试用例中提取测试模式"""
    
    @staticmethod
    def extract_patterns(standardized_cases: Dict[str, Any]) -> Dict[str, Any]:
        """从标准化历史用例中提取测试模式"""
        # 1. 按组件类型分组测试用例
        cases_by_component = TestPatternExtractor._group_cases_by_component(standardized_cases)
        
        # 2. 提取每种组件类型的测试模式
        component_patterns = {}
        for component_type, cases in cases_by_component.items():
            component_patterns[component_type] = TestPatternExtractor._extract_component_patterns(component_type, cases)
        
        # 3. 提取通用测试模式
        general_patterns = TestPatternExtractor._extract_general_patterns(standardized_cases)
        
        # 4. 整合结果
        pattern_library = {
            "component_patterns": component_patterns,
            "general_patterns": general_patterns,
            "metadata": {
                "total_cases": len(standardized_cases),
                "total_patterns": sum(len(patterns) for patterns in component_patterns.values()) + len(general_patterns),
                "component_coverage": len(component_patterns)
            }
        }
        
        return pattern_library
    
    @staticmethod
    def _group_cases_by_component(cases: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """按组件类型分组测试用例"""
        grouped_cases = defaultdict(list)
        
        for case_id, case_data in cases.items():
            components = case_data.get('components', [])
            
            if not components:
                # 如果没有明确的组件，放入GENERAL类别
                grouped_cases["GENERAL"].append(case_data)
                continue
            
            # 将用例添加到每个相关组件的列表中
            for component in components:
                grouped_cases[component].append(case_data)
        
        return grouped_cases
    
    @staticmethod
    def _extract_component_patterns(component_type: str, cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """提取特定组件类型的测试模式"""
        patterns = []
        
        # 1. 收集所有操作
        all_actions = set()
        for case in cases:
            actions = case.get('actions', [])
            all_actions.update(actions)
        
        # 2. 收集每种操作的步骤模式
        action_step_patterns = defaultdict(list)
        for case in cases:
            for step in case.get('steps', []):
                if isinstance(step, dict):
                    action = step.get('action')
                    if action:
                        action_step_patterns[action].append(step)
        
        # 3. 收集每种操作的预期结果模式
        action_result_patterns = defaultdict(list)
        for case in cases:
            for result in case.get('expected_results', []):
                if isinstance(result, dict):
                    # 尝试将结果与操作关联
                    for step in case.get('steps', []):
                        if isinstance(step, dict) and step.get('action'):
                            action_result_patterns[step.get('action')].append(result)
                            break
        
        # 4. 提取每种操作的模式
        for action in all_actions:
            steps = action_step_patterns.get(action, [])
            results = action_result_patterns.get(action, [])
            
            if not steps:
                continue
            
            # 提取步骤模式
            step_patterns = TestPatternExtractor._extract_step_patterns(steps)
            
            # 提取结果模式
            result_patterns = TestPatternExtractor._extract_result_patterns(results)
            
            # 创建操作模式
            action_pattern = {
                "action": action,
                "component_type": component_type,
                "step_patterns": step_patterns,
                "result_patterns": result_patterns,
                "frequency": len(steps),
                "importance_score": TestPatternExtractor._calculate_importance_score(action, component_type, len(steps))
            }
            
            patterns.append(action_pattern)
        
        # 5. 按重要性排序
        patterns.sort(key=lambda x: x['importance_score'], reverse=True)
        
        return patterns
    
    @staticmethod
    def _extract_general_patterns(cases: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取通用测试模式（不特定于组件类型）"""
        general_patterns = []
        
        # 1. 收集所有测试类别
        categories = Counter([case.get('category', 'Functional') for case_id, case in cases.items()])
        
        # 2. 提取每个类别的通用模式
        for category, count in categories.items():
            # 筛选该类别的用例
            category_cases = [case for case_id, case in cases.items() if case.get('category', 'Functional') == category]
            
            # 提取该类别的常见步骤序列
            common_steps = TestPatternExtractor._extract_common_step_sequences(category_cases)
            
            # 提取该类别的常见预期结果
            common_results = TestPatternExtractor._extract_common_result_patterns(category_cases)
            
            # 创建类别模式
            category_pattern = {
                "category": category,
                "frequency": count,
                "common_step_sequences": common_steps,
                "common_result_patterns": common_results,
                "importance_score": TestPatternExtractor._calculate_category_importance(category, count)
            }
            
            general_patterns.append(category_pattern)
        
        # 3. 按重要性排序
        general_patterns.sort(key=lambda x: x['importance_score'], reverse=True)
        
        return general_patterns
    
    @staticmethod
    def _extract_step_patterns(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """提取步骤模式"""
        if not steps:
            return []
        
        # 收集步骤描述和目标
        targets = Counter()
        descriptions = []
        
        for step in steps:
            target = step.get('target', '')
            if target:
                targets[target] += 1
            descriptions.append(step.get('description', ''))
        
        # 提取最常见的目标
        common_targets = [target for target, count in targets.most_common(3)]
        
        # 提取步骤模板
        step_templates = TestPatternExtractor._extract_templates(descriptions, 3)
        
        return [
            {
                "common_targets": common_targets,
                "step_templates": step_templates
            }
        ]
    
    @staticmethod
    def _extract_result_patterns(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """提取预期结果模式"""
        if not results:
            return []
        
        # 收集验证点和状态
        verification_points = Counter()
        statuses = Counter()
        descriptions = []
        
        for result in results:
            verification_point = result.get('verification_point', '')
            status = result.get('status', 'GENERAL')
            
            if verification_point:
                verification_points[verification_point] += 1
            if status:
                statuses[status] += 1
            
            descriptions.append(result.get('description', ''))
        
        # 提取最常见的验证点和状态
        common_verification_points = [vp for vp, count in verification_points.most_common(3)]
        common_statuses = [status for status, count in statuses.most_common(3)]
        
        # 提取结果模板
        result_templates = TestPatternExtractor._extract_templates(descriptions, 3)
        
        return [
            {
                "common_verification_points": common_verification_points,
                "common_statuses": common_statuses,
                "result_templates": result_templates
            }
        ]
    
    @staticmethod
    def _extract_common_step_sequences(cases: List[Dict[str, Any]]) -> List[List[str]]:
        """提取常见步骤序列"""
        # 收集所有操作序列
        action_sequences = []
        
        for case in cases:
            steps = case.get('steps', [])
            if not steps:
                continue
                
            # 提取操作序列
            action_sequence = []
            for step in steps:
                if isinstance(step, dict):
                    action = step.get('action')
                    if action:
                        action_sequence.append(action)
            
            if action_sequence:
                action_sequences.append(tuple(action_sequence))
        
        # 计算常见序列
        common_sequences = Counter(action_sequences).most_common(5)
        
        # 转换为列表格式
        return [list(seq) for seq, count in common_sequences]
    
    @staticmethod
    def _extract_common_result_patterns(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """提取常见预期结果模式"""
        # 收集所有状态
        all_statuses = []
        
        for case in cases:
            results = case.get('expected_results', [])
            if not results:
                continue
                
            # 提取状态
            for result in results:
                if isinstance(result, dict):
                    status = result.get('status')
                    if status:
                        all_statuses.append(status)
        
        # 计算常见状态
        common_statuses = Counter(all_statuses).most_common(5)
        
        # 转换为字典格式
        return [{"status": status, "frequency": count} for status, count in common_statuses]
    
    @staticmethod
    def _extract_templates(texts: List[str], max_templates: int = 3) -> List[str]:
        """从文本列表中提取模板"""
        if not texts:
            return []
            
        # 简单实现：返回最长的几个文本作为模板
        sorted_texts = sorted(texts, key=len, reverse=True)
        return sorted_texts[:max_templates]
    
    @staticmethod
    def _calculate_importance_score(action: str, component_type: str, frequency: int) -> float:
        """计算操作重要性分数"""
        # 重要操作加权
        action_weights = {
            "CLICK": 1.0,
            "INPUT": 1.2,
            "SELECT": 1.0,
            "VERIFY": 1.5,
            "SUBMIT": 1.3,
            "NAVIGATE": 0.8
        }
        
        # 重要组件加权
        component_weights = {
            "BUTTON": 1.0,
            "INPUT": 1.2,
            "FORM": 1.3,
            "LINK": 0.8,
            "DROPDOWN": 1.0,
            "CHECKBOX": 0.9,
            "RADIO": 0.9,
            "MODAL": 1.1
        }
        
        action_weight = action_weights.get(action, 1.0)
        component_weight = component_weights.get(component_type, 1.0)
        
        # 基于频率的对数加权（避免高频模式过度主导）
        frequency_factor = 1.0 + 0.5 * (frequency / 10.0) if frequency > 0 else 1.0
        
        return action_weight * component_weight * frequency_factor
    
    @staticmethod
    def _calculate_category_importance(category: str, frequency: int) -> float:
        """计算测试类别重要性分数"""
        # 类别重要性加权
        category_weights = {
            "Functional": 1.2,
            "Security": 1.5,
            "Performance": 1.0,
            "UI/UX": 0.8,
            "Accessibility": 0.9,
            "Compatibility": 0.7
        }
        
        category_weight = category_weights.get(category, 1.0)
        
        # 基于频率的对数加权
        frequency_factor = 1.0 + 0.3 * (frequency / 10.0) if frequency > 0 else 1.0
        
        return category_weight * frequency_factor
    
    @staticmethod
    def extract_with_cache(standardized_cases: Dict[str, Any], cache_key_prefix: str = None) -> Dict[str, Any]:
        """带缓存的测试模式提取"""
        # 生成缓存键
        if cache_key_prefix:
            cache_key = f"{cache_key_prefix}_patterns"
        else:
            # 基于用例内容生成哈希
            cases_str = str(sorted(standardized_cases.keys()))
            cases_hash = hashlib.md5(cases_str.encode()).hexdigest()
            cache_key = f"test_patterns_{cases_hash}"
        
        # 检查缓存
        cached_patterns = intelligent_cache_manager.get_with_intelligence(cache_key)
        if cached_patterns is not None:
            return cached_patterns
        
        # 提取模式
        patterns = TestPatternExtractor.extract_patterns(standardized_cases)
        
        # 缓存结果
        intelligent_cache_manager.set_with_intelligence(cache_key, patterns, ttl=7200)
        
        return patterns 