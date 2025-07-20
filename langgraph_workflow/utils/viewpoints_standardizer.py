from typing import Dict, Any, List, Set
import json
import re
from collections import defaultdict
from datetime import datetime

class ViewpointsStandardizer:
    """测试观点标准化工具 - 提高复用性和一致性"""
    
    def __init__(self):
        self.standard_terms = {
            # 组件类型标准化
            "button": ["BUTTON", "按钮", "ボタン"],
            "input": ["INPUT", "输入框", "入力欄", "TEXT_INPUT"],
            "text": ["TEXT", "文本", "テキスト", "LABEL"],
            "image": ["IMAGE", "图片", "画像", "IMG"],
            "link": ["LINK", "链接", "リンク", "HYPERLINK"],
            "form": ["FORM", "表单", "フォーム"],
            "table": ["TABLE", "表格", "テーブル"],
            "list": ["LIST", "列表", "リスト"],
            "modal": ["MODAL", "弹窗", "モーダル", "DIALOG"],
            "menu": ["MENU", "菜单", "メニュー"],
            "card": ["CARD", "卡片", "カード"],
            "tab": ["TAB", "标签页", "タブ"],
            "dropdown": ["DROPDOWN", "下拉框", "ドロップダウン", "SELECT"],
            "checkbox": ["CHECKBOX", "复选框", "チェックボックス"],
            "radio": ["RADIO", "单选框", "ラジオボタン"],
            "slider": ["SLIDER", "滑块", "スライダー"],
            "progress": ["PROGRESS", "进度条", "プログレスバー"],
            "spinner": ["SPINNER", "加载器", "スピナー", "LOADER"]
        }
        
        self.standard_viewpoints = {
            # 功能测试观点
            "clickability": ["点击可能性", "クリック可能性", "clickable", "可点击"],
            "input_validation": ["输入验证", "入力検証", "input validation", "表单验证"],
            "navigation": ["导航", "ナビゲーション", "navigation", "页面跳转"],
            "data_display": ["数据显示", "データ表示", "data display", "信息展示"],
            "user_interaction": ["用户交互", "ユーザーインタラクション", "user interaction"],
            "accessibility": ["可访问性", "アクセシビリティ", "accessibility", "无障碍"],
            "performance": ["性能", "パフォーマンス", "performance", "响应时间"],
            "security": ["安全性", "セキュリティ", "security", "安全"],
            "compatibility": ["兼容性", "互換性", "compatibility", "适配"],
            "error_handling": ["错误处理", "エラーハンドリング", "error handling", "异常处理"]
        }
        
        # 关键功能词汇，用于优先级评估
        self.critical_keywords = {
            "HIGH": [
                "登录", "注册", "支付", "结算", "安全", "数据", "提交", "保存",
                "login", "register", "payment", "checkout", "security", "data", "submit", "save",
                "验证", "确认", "核心", "必须", "关键",
                "validation", "confirm", "core", "must", "critical"
            ],
            "MEDIUM": [
                "显示", "展示", "查看", "搜索", "筛选", "排序", "更新",
                "display", "view", "search", "filter", "sort", "update",
                "交互", "操作", "选择", "修改", 
                "interaction", "operation", "select", "modify"
            ],
            "LOW": [
                "提示", "帮助", "辅助", "建议", "可选", "次要",
                "hint", "help", "auxiliary", "suggestion", "optional", "secondary"
            ]
        }
        
        # 测试类型分类关键词
        self.category_keywords = {
            "Functional": [
                "功能", "操作", "点击", "输入", "提交", "验证", "保存", "加载", "处理",
                "function", "operation", "click", "input", "submit", "validate", "save", "load", "process"
            ],
            "UI/UX": [
                "界面", "布局", "样式", "颜色", "字体", "间距", "对齐", "响应式", "交互", "体验",
                "ui", "layout", "style", "color", "font", "spacing", "alignment", "responsive", "interaction", "experience"
            ],
            "Performance": [
                "性能", "速度", "响应时间", "加载时间", "渲染", "效率", "资源占用",
                "performance", "speed", "response time", "loading time", "rendering", "efficiency", "resource usage"
            ],
            "Security": [
                "安全", "权限", "认证", "授权", "加密", "保护", "漏洞", "攻击",
                "security", "permission", "authentication", "authorization", "encryption", "protection", "vulnerability", "attack"
            ],
            "Accessibility": [
                "可访问性", "无障碍", "屏幕阅读器", "键盘导航", "对比度", "焦点",
                "accessibility", "screen reader", "keyboard navigation", "contrast", "focus"
            ]
        }
        
        self.viewpoint_templates = {
            "BUTTON": [
                {
                    "viewpoint": "点击可能性验证",
                    "priority": "HIGH",
                    "category": "Functional",
                    "checklist": [
                        "按钮可以正常点击",
                        "点击后响应时间在可接受范围内",
                        "点击状态视觉反馈正确",
                        "禁用状态下不可点击"
                    ],
                    "expected_result": "按钮功能正常，用户体验良好"
                },
                {
                    "viewpoint": "状态变化验证",
                    "priority": "MEDIUM",
                    "category": "Functional",
                    "checklist": [
                        "正常状态显示正确",
                        "悬停状态显示正确",
                        "点击状态显示正确",
                        "禁用状态显示正确"
                    ],
                    "expected_result": "按钮状态变化符合设计规范"
                }
            ],
            "INPUT": [
                {
                    "viewpoint": "输入验证",
                    "priority": "HIGH",
                    "category": "Functional",
                    "checklist": [
                        "正常输入可以接受",
                        "边界值输入处理正确",
                        "非法输入给出正确提示",
                        "必填项验证正确"
                    ],
                    "expected_result": "输入验证功能完整，用户体验良好"
                },
                {
                    "viewpoint": "格式验证",
                    "priority": "HIGH",
                    "category": "Functional",
                    "checklist": [
                        "邮箱格式验证正确",
                        "手机号格式验证正确",
                        "密码强度验证正确",
                        "特殊字符处理正确"
                    ],
                    "expected_result": "格式验证准确，安全性保障"
                }
            ],
            "TEXT": [
                {
                    "viewpoint": "可读性验证",
                    "priority": "MEDIUM",
                    "category": "UI/UX",
                    "checklist": [
                        "文字清晰可读",
                        "字体大小合适",
                        "颜色对比度足够",
                        "行间距合理"
                    ],
                    "expected_result": "文字信息清晰易读"
                },
                {
                    "viewpoint": "内容准确性",
                    "priority": "HIGH",
                    "category": "Functional",
                    "checklist": [
                        "显示内容准确",
                        "多语言支持正确",
                        "动态内容更新正确",
                        "特殊字符显示正确"
                    ],
                    "expected_result": "文字内容准确无误"
                }
            ]
        }
    
    def standardize_viewpoints(self, viewpoints_data: Dict[str, Any]) -> Dict[str, Any]:
        """标准化测试观点"""
        standardized = {}
        
        for component_type, viewpoints in viewpoints_data.items():
            # 标准化组件类型
            std_component_type = self._standardize_component_type(component_type)
            
            # 标准化观点列表
            std_viewpoints = []
            for viewpoint in viewpoints:
                if isinstance(viewpoint, dict):
                    std_viewpoint = self._standardize_viewpoint_dict(viewpoint)
                else:
                    std_viewpoint = self._standardize_viewpoint_string(str(viewpoint))
                
                # 增强功能：动态评估优先级
                context = {
                    "component_type": std_component_type,
                    "is_in_main_user_flow": self._is_in_main_user_flow(std_component_type),
                    "has_previous_issues": False  # 这里可以集成历史问题数据
                }
                std_viewpoint["priority"] = self.evaluate_viewpoint_priority(std_viewpoint, context)
                
                # 增强功能：多维度分类
                std_viewpoint["classifications"] = self.classify_viewpoint(std_viewpoint)
                
                std_viewpoints.append(std_viewpoint)
            
            standardized[std_component_type] = std_viewpoints
        
        return standardized
    
    def _standardize_component_type(self, component_type: str) -> str:
        """标准化组件类型"""
        component_type_lower = component_type.lower()
        
        for standard, variants in self.standard_terms.items():
            if component_type_lower in [v.lower() for v in variants]:
                return standard.upper()
        
        # 如果没有找到匹配，返回原类型的大写形式
        return component_type.upper()
    
    def _standardize_viewpoint_string(self, viewpoint: str) -> Dict[str, Any]:
        """标准化观点字符串"""
        # 查找匹配的标准观点
        for standard, variants in self.standard_viewpoints.items():
            if any(variant.lower() in viewpoint.lower() for variant in variants):
                # 使用模板生成标准化观点
                return self._get_viewpoint_template(standard)
        
        # 如果没有找到匹配，创建默认观点
        return {
            "viewpoint": viewpoint,
            "priority": "MEDIUM",
            "category": "Functional",
            "checklist": [f"验证{viewpoint}功能"],
            "expected_result": f"{viewpoint}功能正常"
        }
    
    def _standardize_viewpoint_dict(self, viewpoint: Dict[str, Any]) -> Dict[str, Any]:
        """标准化观点字典"""
        standardized = {
            "viewpoint": viewpoint.get("viewpoint", ""),
            "priority": viewpoint.get("priority", "MEDIUM"),
            "category": viewpoint.get("category", "Functional"),
            "checklist": viewpoint.get("checklist", []),
            "expected_result": viewpoint.get("expected_result", ""),
            "notes": viewpoint.get("notes", "")
        }
        
        # 标准化观点名称
        std_viewpoint_name = self._standardize_viewpoint_name(standardized["viewpoint"])
        if std_viewpoint_name:
            standardized["viewpoint"] = std_viewpoint_name
        
        return standardized
    
    def evaluate_viewpoint_priority(self, viewpoint: Dict[str, Any], context: Dict[str, Any]) -> str:
        """基于多维度因素动态评估测试观点优先级"""
        # 基础优先级（来自模板或用户输入）
        base_priority = viewpoint.get("priority", "MEDIUM")
        
        # 如果已经是HIGH优先级，直接返回
        if base_priority == "HIGH":
            return "HIGH"
        
        viewpoint_text = viewpoint.get("viewpoint", "").lower()
        category = viewpoint.get("category", "Functional")
        
        # 1. 基于关键词评估
        for priority, keywords in self.critical_keywords.items():
            if any(keyword.lower() in viewpoint_text for keyword in keywords):
                if priority == "HIGH":  # 如果找到高优先级关键词，直接返回HIGH
                    return "HIGH"
                elif priority == "MEDIUM" and base_priority == "LOW":  # 中优先级关键词可以提升LOW到MEDIUM
                    base_priority = "MEDIUM"
                # LOW优先级关键词不会降低现有优先级
        
        # 2. 基于组件类型评估
        component_type = context.get("component_type", "").upper()
        if component_type in ["BUTTON", "FORM", "INPUT"] and category == "Functional":
            if base_priority == "MEDIUM":
                return "HIGH"
            elif base_priority == "LOW":
                return "MEDIUM"
        
        # 3. 基于测试类别评估
        if category in ["Security", "Performance"] and base_priority != "LOW":
            return "HIGH"
        
        # 4. 基于用户流程评估
        if context.get("is_in_main_user_flow", False) and base_priority == "MEDIUM":
            return "HIGH"
        
        # 5. 基于历史问题评估
        if context.get("has_previous_issues", False):
            if base_priority == "MEDIUM":
                return "HIGH"
            elif base_priority == "LOW":
                return "MEDIUM"
        
        # 如果没有特殊调整，返回基础优先级
        return base_priority
    
    def _is_in_main_user_flow(self, component_type: str) -> bool:
        """判断组件是否在主要用户流程中"""
        # 这里可以根据实际业务逻辑判断
        main_flow_components = ["BUTTON", "FORM", "INPUT", "LINK", "MENU"]
        return component_type in main_flow_components
    
    def classify_viewpoint(self, viewpoint: Dict[str, Any]) -> Dict[str, List[str]]:
        """对测试观点进行多维度分类"""
        classifications = {
            # 1. 功能维度分类
            "functional_type": [],
            
            # 2. 测试类型分类
            "test_type": [],
            
            # 3. 用户体验维度
            "ux_dimension": [],
            
            # 4. 技术实现维度
            "technical_aspect": []
        }
        
        viewpoint_text = viewpoint.get("viewpoint", "").lower()
        category = viewpoint.get("category", "Functional")
        
        # 功能维度分类
        if any(keyword in viewpoint_text for keyword in ["验证", "确认", "检查", "verify", "validate"]):
            classifications["functional_type"].append("VERIFICATION")
        if any(keyword in viewpoint_text for keyword in ["交互", "点击", "输入", "interaction", "click", "input"]):
            classifications["functional_type"].append("INTERACTION")
        if any(keyword in viewpoint_text for keyword in ["显示", "展示", "渲染", "display", "render"]):
            classifications["functional_type"].append("DISPLAY")
        
        # 测试类型分类
        for test_type, keywords in self.category_keywords.items():
            if any(keyword.lower() in viewpoint_text for keyword in keywords):
                classifications["test_type"].append(test_type.upper())
        
        # 如果测试类型为空，添加category
        if not classifications["test_type"] and category:
            classifications["test_type"].append(category.upper())
        
        # 用户体验维度
        ux_keywords = {
            "USABILITY": ["易用性", "使用", "操作", "usability", "ease of use"],
            "ACCESSIBILITY": ["可访问性", "无障碍", "accessibility"],
            "VISUAL": ["视觉", "外观", "样式", "visual", "appearance", "style"],
            "FEEDBACK": ["反馈", "提示", "响应", "feedback", "response"]
        }
        
        for ux_type, keywords in ux_keywords.items():
            if any(keyword.lower() in viewpoint_text for keyword in keywords):
                classifications["ux_dimension"].append(ux_type)
        
        # 技术实现维度
        tech_keywords = {
            "FRONTEND": ["前端", "界面", "UI", "渲染", "frontend", "interface", "rendering"],
            "BACKEND": ["后端", "服务", "数据", "backend", "service", "data"],
            "INTEGRATION": ["集成", "接口", "API", "integration", "interface", "api"],
            "DATABASE": ["数据库", "存储", "database", "storage"]
        }
        
        for tech_type, keywords in tech_keywords.items():
            if any(keyword.lower() in viewpoint_text for keyword in keywords):
                classifications["technical_aspect"].append(tech_type)
        
        return classifications
    
    def _standardize_viewpoint_name(self, viewpoint_name: str) -> str:
        """标准化观点名称"""
        for standard, variants in self.standard_viewpoints.items():
            if any(variant.lower() in viewpoint_name.lower() for variant in variants):
                # 返回中文标准名称
                if "点击" in viewpoint_name or "click" in viewpoint_name.lower():
                    return "点击可能性验证"
                elif "输入" in viewpoint_name or "input" in viewpoint_name.lower():
                    return "输入验证"
                elif "导航" in viewpoint_name or "navigation" in viewpoint_name.lower():
                    return "导航功能验证"
                elif "显示" in viewpoint_name or "display" in viewpoint_name.lower():
                    return "数据显示验证"
                elif "交互" in viewpoint_name or "interaction" in viewpoint_name.lower():
                    return "用户交互验证"
                elif "访问" in viewpoint_name or "accessibility" in viewpoint_name.lower():
                    return "可访问性验证"
                elif "性能" in viewpoint_name or "performance" in viewpoint_name.lower():
                    return "性能验证"
                elif "安全" in viewpoint_name or "security" in viewpoint_name.lower():
                    return "安全性验证"
                elif "兼容" in viewpoint_name or "compatibility" in viewpoint_name.lower():
                    return "兼容性验证"
                elif "错误" in viewpoint_name or "error" in viewpoint_name.lower():
                    return "错误处理验证"
        
        return viewpoint_name
    
    def _get_viewpoint_template(self, standard_name: str) -> Dict[str, Any]:
        """获取观点模板"""
        template_mapping = {
            "clickability": {
                "viewpoint": "点击可能性验证",
                "priority": "HIGH",
                "category": "Functional",
                "checklist": [
                    "组件可以正常点击",
                    "点击后响应时间在可接受范围内",
                    "点击状态视觉反馈正确",
                    "禁用状态下不可点击"
                ],
                "expected_result": "点击功能正常，用户体验良好"
            },
            "input_validation": {
                "viewpoint": "输入验证",
                "priority": "HIGH",
                "category": "Functional",
                "checklist": [
                    "正常输入可以接受",
                    "边界值输入处理正确",
                    "非法输入给出正确提示",
                    "必填项验证正确"
                ],
                "expected_result": "输入验证功能完整，用户体验良好"
            },
            "navigation": {
                "viewpoint": "导航功能验证",
                "priority": "HIGH",
                "category": "Functional",
                "checklist": [
                    "导航链接可以正常跳转",
                    "跳转目标页面正确",
                    "导航状态显示正确",
                    "返回功能正常"
                ],
                "expected_result": "导航功能正常，用户体验良好"
            }
        }
        
        return template_mapping.get(standard_name, {
            "viewpoint": f"{standard_name}验证",
            "priority": "MEDIUM",
            "category": "Functional",
            "checklist": [f"验证{standard_name}功能"],
            "expected_result": f"{standard_name}功能正常"
        })
    
    def create_viewpoint_mapping(self, viewpoints_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建观点映射关系"""
        mapping = {
            "component_type_mapping": {},
            "viewpoint_mapping": {},
            "template_mapping": {}
        }
        
        for component_type, viewpoints in viewpoints_data.items():
            std_component_type = self._standardize_component_type(component_type)
            mapping["component_type_mapping"][component_type] = std_component_type
            
            for viewpoint in viewpoints:
                if isinstance(viewpoint, dict):
                    viewpoint_name = viewpoint.get("viewpoint", "")
                else:
                    viewpoint_name = str(viewpoint)
                
                std_viewpoint_name = self._standardize_viewpoint_name(viewpoint_name)
                mapping["viewpoint_mapping"][viewpoint_name] = std_viewpoint_name
        
        return mapping
    
    def get_component_templates(self, component_type: str) -> List[Dict[str, Any]]:
        """获取组件模板"""
        std_component_type = self._standardize_component_type(component_type)
        return self.viewpoint_templates.get(std_component_type, [])
    
    def merge_viewpoints(self, viewpoints_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """合并多个观点文件"""
        merged = {}
        
        for viewpoints_data in viewpoints_list:
            for component_type, viewpoints in viewpoints_data.items():
                std_component_type = self._standardize_component_type(component_type)
                
                if std_component_type not in merged:
                    merged[std_component_type] = []
                
                # 标准化观点并去重
                for viewpoint in viewpoints:
                    if isinstance(viewpoint, dict):
                        std_viewpoint = self._standardize_viewpoint_dict(viewpoint)
                    else:
                        std_viewpoint = self._standardize_viewpoint_string(str(viewpoint))
                    
                    # 检查是否已存在
                    if not any(v.get("viewpoint") == std_viewpoint["viewpoint"] for v in merged[std_component_type]):
                        merged[std_component_type].append(std_viewpoint)
        
        return merged
    
    def validate_viewpoints(self, viewpoints_data: Dict[str, Any]) -> Dict[str, Any]:
        """验证观点数据完整性"""
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": []
        }
        
        for component_type, viewpoints in viewpoints_data.items():
            # 检查组件类型
            if not component_type or not component_type.strip():
                validation_result["errors"].append(f"组件类型不能为空")
                validation_result["is_valid"] = False
            
            # 检查观点列表
            if not isinstance(viewpoints, list):
                validation_result["errors"].append(f"组件 {component_type} 的观点必须是列表")
                validation_result["is_valid"] = False
                continue
            
            for i, viewpoint in enumerate(viewpoints):
                if isinstance(viewpoint, dict):
                    # 检查必需字段
                    if "viewpoint" not in viewpoint or not viewpoint["viewpoint"]:
                        validation_result["errors"].append(f"组件 {component_type} 第 {i+1} 个观点缺少viewpoint字段")
                        validation_result["is_valid"] = False
                    
                    # 检查优先级
                    priority = viewpoint.get("priority", "MEDIUM")
                    if priority not in ["HIGH", "MEDIUM", "LOW"]:
                        validation_result["warnings"].append(f"组件 {component_type} 第 {i+1} 个观点优先级值异常: {priority}")
                    
                    # 检查类别
                    category = viewpoint.get("category", "Functional")
                    if category not in ["Functional", "UI/UX", "Performance", "Security", "Accessibility"]:
                        validation_result["warnings"].append(f"组件 {component_type} 第 {i+1} 个观点类别值异常: {category}")
                    
                    # 检查分类
                    if "classifications" in viewpoint:
                        classifications = viewpoint.get("classifications", {})
                        if not isinstance(classifications, dict):
                            validation_result["warnings"].append(f"组件 {component_type} 第 {i+1} 个观点分类格式错误")
                        else:
                            # 检查分类维度
                            expected_dimensions = ["functional_type", "test_type", "ux_dimension", "technical_aspect"]
                            for dim in classifications:
                                if dim not in expected_dimensions:
                                    validation_result["warnings"].append(f"组件 {component_type} 第 {i+1} 个观点包含未知分类维度: {dim}")
                                
                                # 检查分类值
                                if not isinstance(classifications[dim], list):
                                    validation_result["warnings"].append(f"组件 {component_type} 第 {i+1} 个观点分类维度 {dim} 的值必须是列表")
                    
                    # 检查优先级分析
                    if "priority_analysis" in viewpoint:
                        priority_analysis = viewpoint.get("priority_analysis", {})
                        if not isinstance(priority_analysis, dict):
                            validation_result["warnings"].append(f"组件 {component_type} 第 {i+1} 个观点优先级分析格式错误")
                        else:
                            # 检查必要字段
                            required_fields = ["base_priority", "evaluated_priority"]
                            for field in required_fields:
                                if field not in priority_analysis:
                                    validation_result["warnings"].append(f"组件 {component_type} 第 {i+1} 个观点优先级分析缺少字段: {field}")
                
                elif not isinstance(viewpoint, str):
                    validation_result["errors"].append(f"组件 {component_type} 第 {i+1} 个观点格式错误")
                    validation_result["is_valid"] = False
        
        return validation_result

# 全局测试观点标准化器实例
viewpoints_standardizer = ViewpointsStandardizer()