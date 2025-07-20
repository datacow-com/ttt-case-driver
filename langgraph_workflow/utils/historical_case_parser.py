import json
import csv
import io
import pandas as pd
import re
import hashlib
from typing import Dict, Any, List, Tuple, Optional
from fastapi import HTTPException
from utils.intelligent_cache_manager import intelligent_cache_manager

class HistoricalCaseParser:
    """历史测试用例解析器 - 支持多种格式输入和标准化"""
    
    @staticmethod
    def parse_historical_cases(file_content: bytes, file_extension: str = None, filename: str = None) -> Dict[str, Any]:
        """解析历史测试用例文件"""
        # 文件格式检测
        format_type = HistoricalCaseParser._detect_format(file_extension, filename)
        
        try:
            if format_type == 'json':
                raw_cases = HistoricalCaseParser._parse_json_cases(file_content)
            elif format_type == 'csv':
                raw_cases = HistoricalCaseParser._parse_csv_cases(file_content)
            elif format_type == 'excel':
                raw_cases = HistoricalCaseParser._parse_excel_cases(file_content)
            else:
                raise ValueError(f"不支持的文件格式: {format_type}")
            
            # 清洗和标准化
            standardized_cases = HistoricalCaseParser.clean_and_standardize(raw_cases)
            return standardized_cases
                
        except Exception as e:
            raise ValueError(f"历史测试用例解析失败: {str(e)}")
    
    @staticmethod
    def _detect_format(file_extension: str = None, filename: str = None) -> str:
        """文件格式检测"""
        if file_extension:
            ext = file_extension.lower()
        elif filename:
            ext = filename.lower().split('.')[-1] if '.' in filename else ''
        else:
            raise ValueError("无法检测文件格式")
        
        if ext in ['json']:
            return 'json'
        elif ext in ['csv']:
            return 'csv'
        elif ext in ['xlsx', 'xls']:
            return 'excel'
        else:
            raise ValueError(f"不支持的文件扩展名: {ext}")
    
    @staticmethod
    def _parse_json_cases(file_content: bytes) -> Dict[str, Any]:
        """JSON格式的历史测试用例解析"""
        try:
            content = file_content.decode('utf-8')
            data = json.loads(content)
            
            # 处理不同的JSON结构
            if isinstance(data, list):
                # 列表结构转换为字典
                cases = {}
                for i, case in enumerate(data):
                    if isinstance(case, dict):
                        case_id = case.get('id', case.get('case_id', case.get('testCaseId', f'case_{i+1}')))
                        cases[str(case_id)] = case
                return cases
            elif isinstance(data, dict):
                # 检查是否已经是字典的字典结构
                if all(isinstance(v, dict) for v in data.values()):
                    return data
                # 单个用例转换为字典的字典
                case_id = data.get('id', data.get('case_id', data.get('testCaseId', 'case_1')))
                return {str(case_id): data}
            else:
                raise ValueError("无效的JSON格式：必须是对象或对象数组")
                
        except json.JSONDecodeError as e:
            raise ValueError(f"无效的JSON格式: {str(e)}")
    
    @staticmethod
    def _parse_csv_cases(file_content: bytes) -> Dict[str, Any]:
        """CSV格式的历史测试用例解析"""
        try:
            content = file_content.decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(content))
            
            cases = {}
            for i, row in enumerate(csv_reader):
                # 尝试提取用例ID
                case_id = row.get('ID', row.get('Case ID', row.get('Test Case ID', f'case_{i+1}')))
                cases[str(case_id)] = dict(row)
            
            return cases
            
        except Exception as e:
            raise ValueError(f"CSV解析失败: {str(e)}")
    
    @staticmethod
    def _parse_excel_cases(file_content: bytes) -> Dict[str, Any]:
        """Excel格式的历史测试用例解析 - 支持多个sheet页面"""
        try:
            # 读取Excel文件的所有sheet
            excel_file = pd.ExcelFile(io.BytesIO(file_content))
            sheet_names = excel_file.sheet_names
            
            # 合并所有sheet的用例
            cases = {}
            for sheet_name in sheet_names:
                df = excel_file.parse(sheet_name)
                
                # 跳过空sheet
                if df.empty:
                    continue
                
                # 处理当前sheet中的用例
                for i, row in df.iterrows():
                    # 尝试提取用例ID
                    if 'ID' in df.columns:
                        case_id = str(row['ID'])
                    elif 'Case ID' in df.columns:
                        case_id = str(row['Case ID'])
                    elif 'Test Case ID' in df.columns:
                        case_id = str(row['Test Case ID'])
                    else:
                        case_id = f'{sheet_name}_case_{i+1}'
                    
                    # 转换行为字典
                    case_data = row.to_dict()
                    # 处理NaN值
                    case_data = {k: ('' if pd.isna(v) else v) for k, v in case_data.items()}
                    # 添加sheet信息
                    case_data['sheet_name'] = sheet_name
                    cases[case_id] = case_data
            
            return cases
            
        except Exception as e:
            raise ValueError(f"Excel解析失败: {str(e)}")
    
    @staticmethod
    def clean_and_standardize(raw_cases: Dict[str, Any]) -> Dict[str, Any]:
        """清洗并标准化历史测试用例"""
        standardized = {}
        
        for case_id, case_data in raw_cases.items():
            # 1. 基础数据清洗
            cleaned_case = HistoricalCaseParser._clean_case_data(case_data)
            
            # 2. 提取关键测试信息
            test_info = HistoricalCaseParser._extract_test_info(cleaned_case)
            
            # 3. 识别测试组件和操作
            components, actions = HistoricalCaseParser._identify_components_and_actions(test_info)
            
            # 4. 标准化测试步骤
            std_steps = HistoricalCaseParser._standardize_steps(test_info.get('steps', []))
            
            # 5. 标准化预期结果
            std_expected = HistoricalCaseParser._standardize_expected_results(test_info.get('expected_results', []))
            
            # 6. 构建标准化用例
            standardized[case_id] = {
                "case_id": case_id,
                "title": test_info.get('title', f"Test Case {case_id}"),
                "components": components,
                "actions": actions,
                "steps": std_steps,
                "expected_results": std_expected,
                "priority": test_info.get('priority', 'MEDIUM'),
                "category": test_info.get('category', 'Functional'),
                "metadata": {
                    "source": test_info.get('source', 'historical'),
                    "created_at": test_info.get('created_at', ''),
                    "author": test_info.get('author', ''),
                    "version": test_info.get('version', '1.0')
                }
            }
        
        return standardized
    
    @staticmethod
    def _clean_case_data(case_data: Dict[str, Any]) -> Dict[str, Any]:
        """清洗测试用例数据"""
        cleaned = {}
        
        # 1. 移除空值
        for key, value in case_data.items():
            if value is not None and value != "":
                cleaned[key] = value
        
        # 2. 规范化字符串（去除多余空格、换行等）
        for key, value in cleaned.items():
            if isinstance(value, str):
                cleaned[key] = ' '.join(value.split())
        
        # 3. 处理列表类型
        for key, value in cleaned.items():
            if isinstance(value, list):
                cleaned[key] = [item for item in value if item is not None and item != ""]
                # 规范化列表中的字符串
                cleaned[key] = [' '.join(item.split()) if isinstance(item, str) else item for item in cleaned[key]]
        
        return cleaned
    
    @staticmethod
    def _extract_test_info(cleaned_case: Dict[str, Any]) -> Dict[str, Any]:
        """提取测试关键信息"""
        test_info = {}
        
        # 映射常见字段名到标准字段名
        field_mapping = {
            # 标题字段映射
            'title': ['title', 'name', 'test_name', 'test_title', 'case_name', 'case_title', 'テストケース名', 'テスト名'],
            # 步骤字段映射
            'steps': ['steps', 'test_steps', 'procedure', 'test_procedure', 'actions', 'テスト手順', 'ステップ'],
            # 预期结果字段映射
            'expected_results': ['expected_results', 'expected', 'expected_outcome', 'results', 'テスト結果', '期待結果'],
            # 优先级字段映射
            'priority': ['priority', 'importance', 'severity', '優先度', '重要度'],
            # 分类字段映射
            'category': ['category', 'type', 'test_type', 'テストタイプ', 'カテゴリ'],
            # 元数据字段映射
            'source': ['source', 'from', 'origin', 'ソース'],
            'created_at': ['created_at', 'date', 'creation_date', '作成日'],
            'author': ['author', 'creator', 'created_by', '作成者'],
            'version': ['version', 'ver', 'バージョン']
        }
        
        # 应用字段映射
        for std_field, alt_fields in field_mapping.items():
            for field in alt_fields:
                if field in cleaned_case:
                    test_info[std_field] = cleaned_case[field]
                    break
        
        # 处理步骤 - 可能是字符串或列表
        if 'steps' in test_info and isinstance(test_info['steps'], str):
            # 尝试拆分步骤字符串为列表
            steps_text = test_info['steps']
            # 按数字+点或数字+括号模式拆分
            step_pattern = r'(\d+[\.\)]\s+|Step\s+\d+[\.\:]\s+)'
            steps = re.split(step_pattern, steps_text)
            # 过滤空步骤并清理
            steps = [step.strip() for step in steps if step.strip() and not re.match(r'^\d+[\.\)]\s+$|^Step\s+\d+[\.\:]\s+$', step)]
            test_info['steps'] = steps
        
        # 处理预期结果 - 类似步骤的处理
        if 'expected_results' in test_info and isinstance(test_info['expected_results'], str):
            results_text = test_info['expected_results']
            result_pattern = r'(\d+[\.\)]\s+|Expected\s+\d+[\.\:]\s+)'
            results = re.split(result_pattern, results_text)
            results = [result.strip() for result in results if result.strip() and not re.match(r'^\d+[\.\)]\s+$|^Expected\s+\d+[\.\:]\s+$', result)]
            test_info['expected_results'] = results
        
        return test_info
    
    @staticmethod
    def _identify_components_and_actions(test_info: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        """识别测试用例中涉及的组件和操作"""
        components = set()
        actions = set()
        
        # 组件类型关键词
        component_keywords = {
            "button": ["button", "btn", "按钮", "ボタン"],
            "input": ["input", "field", "textbox", "输入框", "入力欄"],
            "dropdown": ["dropdown", "select", "下拉框", "ドロップダウン"],
            "checkbox": ["checkbox", "check box", "复选框", "チェックボックス"],
            "radio": ["radio", "option", "单选框", "ラジオボタン"],
            "link": ["link", "hyperlink", "链接", "リンク"],
            "modal": ["modal", "dialog", "popup", "弹窗", "モーダル"],
            "form": ["form", "表单", "フォーム"],
            "menu": ["menu", "菜单", "メニュー"],
            "tab": ["tab", "标签页", "タブ"]
        }
        
        # 操作类型关键词
        action_keywords = {
            "click": ["click", "tap", "press", "点击", "クリック"],
            "input": ["input", "enter", "type", "fill", "输入", "入力"],
            "select": ["select", "choose", "选择", "選択"],
            "verify": ["verify", "check", "confirm", "validate", "验证", "確認"],
            "navigate": ["navigate", "go to", "open", "导航", "移動"],
            "submit": ["submit", "send", "提交", "送信"],
            "upload": ["upload", "上传", "アップロード"],
            "download": ["download", "下载", "ダウンロード"]
        }
        
        # 从步骤和标题中提取组件和操作
        text_to_analyze = []
        if 'title' in test_info:
            text_to_analyze.append(test_info['title'])
        if 'steps' in test_info:
            text_to_analyze.extend(test_info['steps'])
        
        for text in text_to_analyze:
            if not text or not isinstance(text, str):
                continue
                
            text_lower = text.lower()
            
            # 识别组件
            for comp_type, keywords in component_keywords.items():
                for keyword in keywords:
                    if keyword.lower() in text_lower:
                        components.add(comp_type.upper())
            
            # 识别操作
            for action_type, keywords in action_keywords.items():
                for keyword in keywords:
                    if keyword.lower() in text_lower:
                        actions.add(action_type.upper())
        
        return list(components), list(actions)
    
    @staticmethod
    def _standardize_steps(steps: List[str]) -> List[Dict[str, Any]]:
        """标准化测试步骤"""
        std_steps = []
        
        for i, step in enumerate(steps):
            if not step:
                continue
                
            # 提取操作和对象
            action, target = HistoricalCaseParser._extract_action_target(step)
            
            std_step = {
                "step_number": i + 1,
                "description": step,
                "action": action,
                "target": target
            }
            
            std_steps.append(std_step)
        
        return std_steps

    @staticmethod
    def _extract_action_target(step_text: str) -> Tuple[str, str]:
        """从步骤文本中提取操作和目标对象"""
        # 操作关键词模式
        action_patterns = {
            "CLICK": r"(?:click|tap|press|点击|クリック)(?:\s+on)?\s+(?:the\s+)?(.+?)(?:\s+button|\s+link|\s+icon|\s+tab|\s+menu|\s+option|$)",
            "INPUT": r"(?:input|enter|type|fill|输入|入力)(?:\s+in(?:to)?)?\s+(?:the\s+)?(.+?)(?:\s+field|\s+box|\s+input|\s+area|$)",
            "SELECT": r"(?:select|choose|选择|選択)(?:\s+from)?\s+(?:the\s+)?(.+?)(?:\s+dropdown|\s+list|\s+menu|\s+option|$)",
            "VERIFY": r"(?:verify|check|confirm|validate|验证|確認)(?:\s+that)?\s+(?:the\s+)?(.+)"
        }
        
        for action, pattern in action_patterns.items():
            match = re.search(pattern, step_text, re.IGNORECASE)
            if match:
                target = match.group(1).strip()
                return action, target
        
        # 默认返回
        return "OPERATION", ""
    
    @staticmethod
    def _standardize_expected_results(expected_results: List[str]) -> List[Dict[str, Any]]:
        """标准化预期结果"""
        std_results = []
        
        for i, result in enumerate(expected_results):
            if not result:
                continue
                
            # 提取验证点和状态
            verification_point, status = HistoricalCaseParser._extract_verification_point(result)
            
            std_result = {
                "result_number": i + 1,
                "description": result,
                "verification_point": verification_point,
                "status": status
            }
            
            std_results.append(std_result)
        
        return std_results

    @staticmethod
    def _extract_verification_point(result_text: str) -> Tuple[str, str]:
        """从预期结果中提取验证点和状态"""
        # 状态关键词
        status_keywords = {
            "SUCCESS": ["success", "successful", "successfully", "成功", "正常", "正確"],
            "DISPLAY": ["display", "displayed", "shows", "shown", "visible", "表示", "表示される"],
            "ENABLED": ["enabled", "active", "有効", "アクティブ"],
            "DISABLED": ["disabled", "inactive", "無効", "非アクティブ"],
            "ERROR": ["error", "fail", "エラー", "失敗"]
        }
        
        # 尝试匹配状态
        result_lower = result_text.lower()
        matched_status = "GENERAL"
        
        for status, keywords in status_keywords.items():
            for keyword in keywords:
                if keyword.lower() in result_lower:
                    matched_status = status
                    break
            if matched_status != "GENERAL":
                break
        
        # 提取验证点 - 通常是主语部分
        verification_point = ""
        # 尝试提取主语
        subject_match = re.search(r"^(?:The\s+)?(.+?)(?:\s+(?:is|are|should|will|must|displays?|shows?))", result_text, re.IGNORECASE)
        if subject_match:
            verification_point = subject_match.group(1).strip()
        else:
            # 回退：使用前半部分作为验证点
            words = result_text.split()
            if len(words) > 3:
                verification_point = " ".join(words[:len(words)//2])
            else:
                verification_point = result_text
        
        return verification_point, matched_status
    
    @staticmethod
    def parse_with_cache(file_content: bytes, file_extension: str = None, filename: str = None) -> Dict[str, Any]:
        """带缓存的历史测试用例解析"""
        # 生成文件哈希
        file_hash = hashlib.md5(file_content).hexdigest()
        
        # 使用智能缓存管理器
        cache_key = f"historical_cases_{file_hash}"
        cached_cases = intelligent_cache_manager.get_with_intelligence(cache_key)
        if cached_cases is not None:
            return cached_cases
        
        # 解析文件
        cases = HistoricalCaseParser.parse_historical_cases(file_content, file_extension, filename)
        
        # 缓存结果
        intelligent_cache_manager.set_with_intelligence(cache_key, cases, ttl=7200)
        
        return cases
    
    @staticmethod
    def parse_multiple_files(file_contents: List[bytes], file_extensions: List[str] = None, filenames: List[str] = None) -> Dict[str, Any]:
        """解析多个历史测试用例文件
        
        Args:
            file_contents: 多个文件内容的列表
            file_extensions: 文件扩展名列表（可选）
            filenames: 文件名列表（可选）
            
        Returns:
            Dict[str, Any]: 合并后的历史测试用例
        """
        all_cases = {}
        file_count = len(file_contents)
        
        # 确保扩展名和文件名列表长度匹配
        if file_extensions is None:
            file_extensions = [None] * file_count
        elif len(file_extensions) < file_count:
            file_extensions.extend([None] * (file_count - len(file_extensions)))
            
        if filenames is None:
            filenames = [None] * file_count
        elif len(filenames) < file_count:
            filenames.extend([None] * (file_count - len(filenames)))
        
        # 解析每个文件
        for i, file_content in enumerate(file_contents):
            try:
                # 解析当前文件
                cases = HistoricalCaseParser.parse_with_cache(
                    file_content, 
                    file_extensions[i], 
                    filenames[i]
                )
                
                # 添加文件来源信息
                file_source = filenames[i] if filenames[i] else f"file_{i+1}"
                for case_id, case_data in cases.items():
                    # 确保case_id在合并后不重复
                    unique_case_id = f"{file_source}_{case_id}"
                    # 添加文件来源信息
                    case_data['file_source'] = file_source
                    all_cases[unique_case_id] = case_data
                    
            except Exception as e:
                # 记录错误但继续处理其他文件
                print(f"解析文件 {filenames[i] if filenames[i] else i+1} 失败: {str(e)}")
                continue
        
        return all_cases
    
    @staticmethod
    def get_supported_formats() -> List[str]:
        """获取支持的格式列表"""
        return ['json', 'csv', 'xlsx', 'xls']
    
    @staticmethod
    def get_format_examples() -> Dict[str, str]:
        """获取各格式的示例"""
        return {
            'json': '''
[
  {
    "id": "TC-001",
    "title": "登录功能测试",
    "steps": [
      "1. 打开登录页面",
      "2. 输入有效用户名和密码",
      "3. 点击登录按钮"
    ],
    "expected_results": [
      "1. 成功登录系统",
      "2. 跳转到首页"
    ],
    "priority": "HIGH"
  }
]
            ''',
            'csv': '''
ID,Title,Steps,Expected Results,Priority
TC-001,登录功能测试,"1. 打开登录页面
2. 输入有效用户名和密码
3. 点击登录按钮","1. 成功登录系统
2. 跳转到首页",HIGH
            ''',
            'excel': '''
ID | Title | Steps | Expected Results | Priority
TC-001 | 登录功能测试 | 1. 打开登录页面\n2. 输入有效用户名和密码\n3. 点击登录按钮 | 1. 成功登录系统\n2. 跳转到首页 | HIGH
            '''
        } 