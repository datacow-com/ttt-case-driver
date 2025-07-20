from typing import Dict, Any, List, Set
import json
import re
from collections import defaultdict

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
                
                elif not isinstance(viewpoint, str):
                    validation_result["errors"].append(f"组件 {component_type} 第 {i+1} 个观点格式错误")
                    validation_result["is_valid"] = False
        
        return validation_result

# 全局测试观点标准化器实例
viewpoints_standardizer = ViewpointsStandardizer()