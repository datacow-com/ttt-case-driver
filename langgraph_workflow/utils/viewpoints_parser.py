import json
import csv
import io
import pandas as pd
from typing import Dict, Any, List, Union, Optional
from fastapi import HTTPException
import hashlib
from utils.cache_manager import cache_result, cache_manager

class ViewpointsParser:
    """测试观点解析器，支持多种格式输入"""
    
    @staticmethod
    @cache_result(prefix="viewpoints_parsed", ttl=7200)  # 解析结果缓存2小时
    def parse_viewpoints(file_content: bytes, file_extension: str = None, filename: str = None) -> Dict[str, Any]:
        """解析测试观点文件（带缓存）"""
        # 文件格式检测
        format_type = ViewpointsParser._detect_format(file_extension, filename)
        
        try:
            if format_type == 'json':
                return ViewpointsParser._parse_json(file_content)
            elif format_type == 'csv':
                return ViewpointsParser._parse_csv(file_content)
            elif format_type == 'excel':
                return ViewpointsParser._parse_excel(file_content)
            else:
                raise HTTPException(status_code=400, detail=f"不支持的文件格式: {format_type}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"测试观点文件解析失败: {str(e)}")
    
    @staticmethod
    def _detect_format(file_extension: str = None, filename: str = None) -> str:
        """文件格式检测"""
        if file_extension:
            ext = file_extension.lower()
        elif filename:
            ext = filename.lower().split('.')[-1] if '.' in filename else ''
        else:
            raise HTTPException(status_code=400, detail="无法检测文件格式")
        
        if ext in ['json']:
            return 'json'
        elif ext in ['csv']:
            return 'csv'
        elif ext in ['xlsx', 'xls']:
            return 'excel'
        else:
            raise HTTPException(status_code=400, detail=f"不支持的文件扩展名: {ext}")
    
    @staticmethod
    def _parse_json(file_content: bytes) -> Dict[str, Any]:
        """JSON格式的测试观点解析"""
        try:
            content = file_content.decode('utf-8')
            data = json.loads(content)
            
            # JSON格式验证
            if not isinstance(data, dict):
                raise ValueError("JSON根必须是对象")
            
            # 格式标准化：确保每个组件类型对应观点列表
            standardized = {}
            for component_type, viewpoints in data.items():
                if isinstance(viewpoints, list):
                    standardized[component_type] = viewpoints
                elif isinstance(viewpoints, str):
                    # 字符串情况，按逗号分割
                    standardized[component_type] = [v.strip() for v in viewpoints.split(',')]
                else:
                    raise ValueError(f"组件 {component_type} 的观点格式无效")
            
            return standardized
        except json.JSONDecodeError as e:
            raise ValueError(f"无效的JSON格式: {str(e)}")
    
    @staticmethod
    def _parse_csv(file_content: bytes) -> Dict[str, Any]:
        """CSV格式的测试观点解析 - 支持专业测试模板"""
        try:
            content = file_content.decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(content))
            
            standardized = {}
            
            for row in csv_reader:
                # 检查专业测试模板格式
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
                        
                        # 解析检查列表
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
                    # 标准CSV格式处理
                    if 'ComponentType' in row and 'Viewpoint' in row:
                        comp_type = row['ComponentType'].strip()
                        viewpoint = row['Viewpoint'].strip()
                        if comp_type and viewpoint:
                            if comp_type not in standardized:
                                standardized[comp_type] = []
                            standardized[comp_type].append(viewpoint)
            
            return standardized
        except Exception as e:
            raise ValueError(f"CSV解析失败: {str(e)}")
    
    @staticmethod
    def _parse_excel(file_content: bytes) -> Dict[str, Any]:
        """Excel格式的测试观点解析 - 支持专业测试模板"""
        try:
            # 读取Excel文件
            df = pd.read_excel(io.BytesIO(file_content))
            
            standardized = {}
            
            # 检查专业测试模板格式
            if 'テスト観点（Test Viewpoint）' in df.columns:
                # 专业测试模板格式
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
                        
                        # 解析检查列表
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
                # 标准Excel格式处理
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
            raise ValueError(f"Excel解析失败: {str(e)}")
    
    @staticmethod
    def validate_viewpoints(viewpoints_data: Dict[str, Any]) -> bool:
        """验证测试观点数据的有效性"""
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
        """获取支持的格式列表"""
        return ['json', 'csv', 'xlsx', 'xls']
    
    @staticmethod
    def get_format_examples() -> Dict[str, str]:
        """获取各格式的示例"""
        return {
            'json': '''
{
  "BUTTON": ["点击可能性", "状态变化", "响应时间"],
  "INPUT": ["边界值输入", "格式验证", "响应时间"],
  "TEXT": ["可读性", "内容准确性"]
}
            ''',
            'csv': '''
组件类型,测试观点（Test Viewpoint）
BUTTON,点击可能性
BUTTON,状态变化
INPUT,边界值输入
INPUT,格式验证
            ''',
            'excel': '''
组件类型 | 测试观点（Test Viewpoint）
BUTTON        | 点击可能性
BUTTON        | 状态变化
INPUT         | 边界值输入
INPUT         | 格式验证
            '''
        }
    
    # ==================== 缓存相关方法 ====================
    @staticmethod
    def _generate_file_hash(file_content: bytes) -> str:
        """生成文件内容哈希"""
        return hashlib.md5(file_content).hexdigest()
    
    @staticmethod
    def cache_viewpoints_by_component(component_type: str, viewpoints: List[Dict[str, Any]], ttl: int = 3600):
        """按组件类型缓存测试观点"""
        cache_key = f"viewpoints_component_{component_type}"
        cache_manager.set(cache_key, viewpoints, ttl)
    
    @staticmethod
    def get_cached_viewpoints_by_component(component_type: str) -> Optional[List[Dict[str, Any]]]:
        """获取按组件类型缓存的测试观点"""
        cache_key = f"viewpoints_component_{component_type}"
        return cache_manager.get(cache_key)
    
    @staticmethod
    def cache_viewpoints_analysis(analysis_result: Dict[str, Any], ttl: int = 1800):
        """缓存测试观点分析结果"""
        cache_key = "viewpoints_analysis"
        cache_manager.set(cache_key, analysis_result, ttl)
    
    @staticmethod
    def get_cached_viewpoints_analysis() -> Optional[Dict[str, Any]]:
        """获取缓存的测试观点分析结果"""
        cache_key = "viewpoints_analysis"
        return cache_manager.get(cache_key)
    
    @staticmethod
    def parse_viewpoints_with_cache(file_content: bytes, file_extension: str = None, filename: str = None) -> Dict[str, Any]:
        """带缓存的测试观点解析"""
        # 生成文件哈希
        file_hash = ViewpointsParser._generate_file_hash(file_content)
        
        # 尝试从缓存获取
        cached_viewpoints = cache_manager.get_viewpoints(file_hash)
        if cached_viewpoints is not None:
            return cached_viewpoints
        
        # 解析文件
        viewpoints = ViewpointsParser.parse_viewpoints(file_content, file_extension, filename)
        
        # 缓存结果
        cache_manager.cache_viewpoints(file_hash, viewpoints, ttl=7200)
        
        return viewpoints