import json
import csv
import io
import pandas as pd
from typing import Dict, Any, List, Union
from fastapi import HTTPException

class ViewpointsParser:
    """テスト観点解析器、複数形式の入力をサポート"""
    
    @staticmethod
    def parse_viewpoints(file_content: bytes, file_extension: str = None, filename: str = None) -> Dict[str, Any]:
        """
        テスト観点ファイルを解析、JSON、CSV、Excel形式をサポート
        
        Args:
            file_content: ファイル内容（bytes）
            file_extension: ファイル拡張子
            filename: ファイル名（形式推論用）
        
        Returns:
            Dict[str, Any]: 標準化されたテスト観点辞書
        """
        # ファイル形式を決定
        format_type = ViewpointsParser._detect_format(file_extension, filename)
        
        try:
            if format_type == 'json':
                return ViewpointsParser._parse_json(file_content)
            elif format_type == 'csv':
                return ViewpointsParser._parse_csv(file_content)
            elif format_type == 'excel':
                return ViewpointsParser._parse_excel(file_content)
            else:
                raise HTTPException(status_code=400, detail=f"サポートされていないファイル形式: {format_type}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"テスト観点ファイルの解析に失敗しました: {str(e)}")
    
    @staticmethod
    def _detect_format(file_extension: str = None, filename: str = None) -> str:
        """ファイル形式を検出"""
        if file_extension:
            ext = file_extension.lower()
        elif filename:
            ext = filename.lower().split('.')[-1] if '.' in filename else ''
        else:
            raise HTTPException(status_code=400, detail="ファイル形式を検出できません")
        
        if ext in ['json']:
            return 'json'
        elif ext in ['csv']:
            return 'csv'
        elif ext in ['xlsx', 'xls']:
            return 'excel'
        else:
            raise HTTPException(status_code=400, detail=f"サポートされていないファイル拡張子: {ext}")
    
    @staticmethod
    def _parse_json(file_content: bytes) -> Dict[str, Any]:
        """JSON形式のテスト観点を解析"""
        try:
            content = file_content.decode('utf-8')
            data = json.loads(content)
            
            # JSON形式を検証
            if not isinstance(data, dict):
                raise ValueError("JSONルートはオブジェクトである必要があります")
            
            # 形式を標準化：各コンポーネントタイプが観点リストに対応することを確認
            standardized = {}
            for component_type, viewpoints in data.items():
                if isinstance(viewpoints, list):
                    standardized[component_type] = viewpoints
                elif isinstance(viewpoints, str):
                    # 文字列の場合、カンマで分割
                    standardized[component_type] = [v.strip() for v in viewpoints.split(',')]
                else:
                    raise ValueError(f"コンポーネント {component_type} の観点形式が無効です")
            
            return standardized
        except json.JSONDecodeError as e:
            raise ValueError(f"無効なJSON形式: {str(e)}")
    
    @staticmethod
    def _parse_csv(file_content: bytes) -> Dict[str, Any]:
        """CSV形式のテスト観点を解析 - 専門テストテンプレートをサポート"""
        try:
            content = file_content.decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(content))
            
            standardized = {}
            
            for row in csv_reader:
                # 専門テストテンプレート形式かチェック
                if 'テスト観点（Test Viewpoint）' in row:
                    component_type = row.get('コンポーネントタイプ', 'GENERAL').strip()
                    viewpoint = row.get('テスト観点（Test Viewpoint）', '').strip()
                    priority = row.get('優先度', 'MEDIUM').strip()
                    category = row.get('テストタイプ', 'Functional').strip()
                    checklist = row.get('チェックリスト', '').strip()
                    expected_result = row.get('期待目的', '').strip()
                    notes = row.get('備考', '').strip()
                    
                    if component_type and viewpoint:
                        if component_type not in standardized:
                            standardized[component_type] = []
                        
                        # チェックリストを解析
                        checklist_items = []
                        if checklist:
                            checklist_items = [item.strip() for item in checklist.replace('<br>', '\n').split('\n') if item.strip()]
                        
                        standardized[component_type].append({
                            'viewpoint': viewpoint,
                            'priority': priority,
                            'category': category,
                            'checklist': checklist_items,
                            'expected_result': expected_result,
                            'notes': notes
                        })
                else:
                    # 標準CSV形式処理
                    if 'ComponentType' in row and 'Viewpoint' in row:
                        comp_type = row['ComponentType'].strip()
                        viewpoint = row['Viewpoint'].strip()
                        if comp_type and viewpoint:
                            if comp_type not in standardized:
                                standardized[comp_type] = []
                            standardized[comp_type].append(viewpoint)
            
            return standardized
        except Exception as e:
            raise ValueError(f"CSVの解析に失敗しました: {str(e)}")
    
    @staticmethod
    def _parse_excel(file_content: bytes) -> Dict[str, Any]:
        """Excel形式のテスト観点を解析 - 専門テストテンプレートをサポート"""
        try:
            # Excelファイルを読み込み
            df = pd.read_excel(io.BytesIO(file_content))
            
            standardized = {}
            
            # 専門テストテンプレート形式かチェック
            if 'テスト観点（Test Viewpoint）' in df.columns:
                # 専門テストテンプレート形式
                for _, row in df.iterrows():
                    component_type = str(row.get('コンポーネントタイプ', 'GENERAL')).strip()
                    viewpoint = str(row.get('テスト観点（Test Viewpoint）', '')).strip()
                    priority = str(row.get('優先度', 'MEDIUM')).strip()
                    category = str(row.get('テストタイプ', 'Functional')).strip()
                    checklist = str(row.get('チェックリスト', '')).strip()
                    expected_result = str(row.get('期待目的', '')).strip()
                    notes = str(row.get('備考', '')).strip()
                    
                    if component_type and viewpoint and component_type != 'nan' and viewpoint != 'nan':
                        if component_type not in standardized:
                            standardized[component_type] = []
                        
                        # チェックリストを解析
                        checklist_items = []
                        if checklist and checklist != 'nan':
                            checklist_items = [item.strip() for item in checklist.replace('<br>', '\n').split('\n') if item.strip()]
                        
                        standardized[component_type].append({
                            'viewpoint': viewpoint,
                            'priority': priority,
                            'category': category,
                            'checklist': checklist_items,
                            'expected_result': expected_result,
                            'notes': notes if notes != 'nan' else ''
                        })
            else:
                # 標準Excel形式処理
                if len(df.columns) >= 2:
                    for _, row in df.iterrows():
                        comp_type = str(row.iloc[0]).strip()
                        viewpoint = str(row.iloc[1]).strip()
                        if comp_type and viewpoint and comp_type != 'nan' and viewpoint != 'nan':
                            if comp_type not in standardized:
                                standardized[comp_type] = []
                            standardized[comp_type].append(viewpoint)
            
            return standardized
        except Exception as e:
            raise ValueError(f"Excelの解析に失敗しました: {str(e)}")
    
    @staticmethod
    def validate_viewpoints(viewpoints_data: Dict[str, Any]) -> bool:
        """テスト観点データの有効性を検証"""
        if not isinstance(viewpoints_data, dict):
            return False
        
        for component_type, viewpoints in viewpoints_data.items():
            if not isinstance(component_type, str) or not component_type.strip():
                return False
            
            if not isinstance(viewpoints, list):
                return False
            
            for viewpoint in viewpoints:
                if isinstance(viewpoint, dict):
                    if not viewpoint.get('viewpoint'):
                        return False
                elif not isinstance(viewpoint, str) or not viewpoint.strip():
                    return False
        
        return True
    
    @staticmethod
    def get_supported_formats() -> List[str]:
        """サポートされている形式リストを取得"""
        return ['json', 'csv', 'xlsx', 'xls']
    
    @staticmethod
    def get_format_examples() -> Dict[str, str]:
        """各形式の例を取得"""
        return {
            'json': '''
{
  "BUTTON": ["クリック可能性", "状態変化", "応答時間"],
  "INPUT": ["境界値入力", "形式検証", "応答時間"],
  "TEXT": ["可読性", "内容正確性"]
}
            ''',
            'csv': '''
コンポーネントタイプ,テスト観点（Test Viewpoint）
BUTTON,クリック可能性
BUTTON,状態変化
INPUT,境界値入力
INPUT,形式検証
            ''',
            'excel': '''
コンポーネントタイプ | テスト観点（Test Viewpoint）
BUTTON        | クリック可能性
BUTTON        | 状態変化
INPUT         | 境界値入力
INPUT         | 形式検証
            '''
        }