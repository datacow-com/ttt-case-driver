import os
from typing import Dict, Any, Optional
from datetime import datetime

class LocalizationManager:
    """ローカライゼーション管理クラス"""
    
    def __init__(self, language: str = "ja"):
        self.language = language
        self.translations = self._load_translations()
    
    def _load_translations(self) -> Dict[str, Dict[str, str]]:
        """翻訳データを読み込む"""
        return {
            "ja": {
                # システムメッセージ
                "system_error": "システムエラーが発生しました",
                "file_parse_error": "ファイルの解析に失敗しました",
                "invalid_format": "無効な形式です",
                "success": "成功",
                
                # テストケース関連
                "test_case": "テストケース",
                "test_case_id": "テストケースID",
                "page": "ページ",
                "component": "コンポーネント",
                "viewpoint": "観点",
                "steps": "手順",
                "expected_result": "期待結果",
                "priority": "優先度",
                "category": "カテゴリ",
                "notes": "備考",
                "created_date": "作成日",
                "tester": "テスター",
                "status": "ステータス",
                
                # 優先度
                "priority_high": "高",
                "priority_medium": "中", 
                "priority_low": "低",
                
                # カテゴリ
                "category_functional": "機能テスト",
                "category_performance": "パフォーマンステスト",
                "category_security": "セキュリティテスト",
                "category_compatibility": "互換性テスト",
                "category_accessibility": "アクセシビリティテスト",
                "category_ux": "ユーザーエクスペリエンステスト",
                
                # ステータス
                "status_pending": "未実行",
                "status_running": "実行中",
                "status_passed": "合格",
                "status_failed": "不合格",
                "status_blocked": "ブロック",
                
                # コンポーネントタイプ
                "component_button": "ボタン",
                "component_input": "入力欄",
                "component_link": "リンク",
                "component_form": "フォーム",
                "component_select": "セレクトボックス",
                "component_checkbox": "チェックボックス",
                "component_radio": "ラジオボタン",
                "component_container": "コンテナ",
                "component_text": "テキスト",
                "component_image": "画像",
                "component_loading": "ローディング",
                "component_toast": "トースト",
                "component_modal": "モーダル",
                "component_page": "ページ",
                "component_rating": "評価",
                "component_filter": "フィルター",
                "component_map": "マップ",
                
                # テスト観点
                "viewpoint_clickability": "クリック可能性",
                "viewpoint_input_validation": "入力検証",
                "viewpoint_response_time": "応答時間",
                "viewpoint_state_change": "状態変化",
                "viewpoint_error_handling": "エラー処理",
                "viewpoint_accessibility": "アクセシビリティ",
                "viewpoint_security": "セキュリティ",
                "viewpoint_compatibility": "互換性",
                "viewpoint_performance": "パフォーマンス",
                "viewpoint_ui_consistency": "UI一貫性",
                
                # エラーメッセージ
                "error_invalid_component": "無効なコンポーネントです",
                "error_missing_viewpoint": "テスト観点が不足しています",
                "error_invalid_format": "無効な形式です",
                "error_file_not_found": "ファイルが見つかりません",
                "error_permission_denied": "権限がありません",
                
                # 成功メッセージ
                "success_testcase_generated": "テストケースが正常に生成されました",
                "success_viewpoints_parsed": "テスト観点が正常に解析されました",
                "success_file_uploaded": "ファイルが正常にアップロードされました",
                
                # 日付・時間フォーマット
                "date_format": "%Y年%m月%d日",
                "time_format": "%H時%M分",
                "datetime_format": "%Y年%m月%d日 %H時%M分"
            },
            "en": {
                # English translations (fallback)
                "test_case": "Test Case",
                "test_case_id": "Test Case ID",
                "page": "Page",
                "component": "Component",
                "viewpoint": "Viewpoint",
                "steps": "Steps",
                "expected_result": "Expected Result",
                "priority": "Priority",
                "category": "Category",
                "notes": "Notes",
                "created_date": "Created Date",
                "tester": "Tester",
                "status": "Status",
                "priority_high": "High",
                "priority_medium": "Medium",
                "priority_low": "Low",
                "category_functional": "Functional",
                "category_performance": "Performance",
                "category_security": "Security",
                "category_compatibility": "Compatibility",
                "category_accessibility": "Accessibility",
                "category_ux": "User Experience",
                "component_button": "Button",
                "component_input": "Input",
                "component_link": "Link",
                "component_form": "Form",
                "component_select": "Select",
                "component_checkbox": "Checkbox",
                "component_radio": "Radio",
                "component_container": "Container",
                "component_text": "Text",
                "component_image": "Image",
                "component_loading": "Loading",
                "component_toast": "Toast",
                "component_modal": "Modal",
                "component_page": "Page",
                "component_rating": "Rating",
                "component_filter": "Filter",
                "component_map": "Map",
                "date_format": "%Y-%m-%d",
                "time_format": "%H:%M",
                "datetime_format": "%Y-%m-%d %H:%M"
            }
        }
    
    def get_text(self, key: str, default: str = None) -> str:
        """翻訳テキストを取得"""
        translations = self.translations.get(self.language, self.translations.get("en", {}))
        return translations.get(key, default or key)
    
    def format_date(self, date: datetime) -> str:
        """日付をフォーマット"""
        if self.language == "ja":
            return date.strftime(self.get_text("date_format"))
        else:
            return date.strftime("%Y-%m-%d")
    
    def format_datetime(self, date: datetime) -> str:
        """日時をフォーマット"""
        if self.language == "ja":
            return date.strftime(self.get_text("datetime_format"))
        else:
            return date.strftime("%Y-%m-%d %H:%M")
    
    def get_priority_text(self, priority: str) -> str:
        """優先度テキストを取得"""
        priority_map = {
            "HIGH": self.get_text("priority_high"),
            "MEDIUM": self.get_text("priority_medium"),
            "LOW": self.get_text("priority_low")
        }
        return priority_map.get(priority, priority)
    
    def get_category_text(self, category: str) -> str:
        """カテゴリテキストを取得"""
        category_map = {
            "Functional": self.get_text("category_functional"),
            "Performance": self.get_text("category_performance"),
            "Security": self.get_text("category_security"),
            "Compatibility": self.get_text("category_compatibility"),
            "Accessibility": self.get_text("category_accessibility"),
            "UX": self.get_text("category_ux")
        }
        return category_map.get(category, category)
    
    def get_component_text(self, component_type: str) -> str:
        """コンポーネントタイプテキストを取得"""
        component_map = {
            "BUTTON": self.get_text("component_button"),
            "INPUT": self.get_text("component_input"),
            "LINK": self.get_text("component_link"),
            "FORM": self.get_text("component_form"),
            "SELECT": self.get_text("component_select"),
            "CHECKBOX": self.get_text("component_checkbox"),
            "RADIO": self.get_text("component_radio"),
            "CONTAINER": self.get_text("component_container"),
            "TEXT": self.get_text("component_text"),
            "IMAGE": self.get_text("component_image"),
            "LOADING": self.get_text("component_loading"),
            "TOAST": self.get_text("component_toast"),
            "MODAL": self.get_text("component_modal"),
            "PAGE": self.get_text("component_page"),
            "RATING": self.get_text("component_rating"),
            "FILTER": self.get_text("component_filter"),
            "MAP": self.get_text("component_map")
        }
        return component_map.get(component_type, component_type)