from typing import List, Dict, Any
import yaml
import csv
import io
import pandas as pd
from datetime import datetime
from utils.prompt_loader import PromptManager
from utils.localization import LocalizationManager

def build_prompt(system_prompt: str, few_shot_examples: list, current_input: str) -> str:
    prompt = system_prompt + '\n'
    for ex in few_shot_examples:
        prompt += f"例入力:\n{ex['input']}\n例出力:\n{ex['output']}\n"
    prompt += f"現在の入力:\n{current_input}\n出力を生成してください："
    return prompt

def format_output(testcases: List[Dict[str, Any]], output_format: str = 'excel', llm_client=None, prompt_template: str = None, few_shot_examples: list = None, language: str = "ja") -> str:
    """
    テストケースをフォーマット出力（CSV/Markdown/YAML/Excel）、LLM最適化対応
    """
    # ローカライゼーション管理
    l10n = LocalizationManager(language)
    
    if llm_client:
        # LLM最適化出力
        prompt_manager = PromptManager()
        node_prompt = prompt_manager.get_prompt('format_output')
        system_prompt = prompt_template or node_prompt.get('system_prompt', '')
        few_shot = few_shot_examples or node_prompt.get('few_shot_examples', [])
        
        current_input = f"テストケース: {testcases}\n形式: {output_format}"
        prompt = build_prompt(system_prompt, few_shot, current_input)
        llm_result = llm_client.generate(prompt)
        
        # LLMが最適化された内容を返した場合、直接使用
        if llm_result.get('steps'):
            return llm_result.get('steps')
    
    # 標準フォーマット処理
    if output_format == 'csv':
        return _format_csv_japanese(testcases, l10n)
    elif output_format == 'excel':
        return _format_excel_japanese(testcases, l10n)
    elif output_format == 'md':
        return _format_markdown_japanese(testcases, l10n)
    elif output_format == 'yaml':
        return yaml.dump(testcases, allow_unicode=True, default_flow_style=False)
    else:
        raise ValueError(f"サポートされていない形式: {output_format}")

def _format_csv_japanese(testcases: List[Dict[str, Any]], l10n: LocalizationManager) -> str:
    """日本語CSVフォーマット"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 日本語ヘッダー
    writer.writerow([
        l10n.get_text("test_case_id"),
        l10n.get_text("page"),
        l10n.get_text("component"),
        l10n.get_text("viewpoint"),
        l10n.get_text("steps"),
        l10n.get_text("expected_result"),
        l10n.get_text("priority"),
        l10n.get_text("category"),
        l10n.get_text("created_date")
    ])
    
    for idx, case in enumerate(testcases, 1):
        comp = case.get('component', {})
        testcase = case.get('testcase', {})
        viewpoint_data = case.get('viewpoint', {})
        
        # 観点データの処理
        if isinstance(viewpoint_data, dict):
            viewpoint = viewpoint_data.get('viewpoint', '')
            priority = l10n.get_priority_text(viewpoint_data.get('priority', 'MEDIUM'))
            category = l10n.get_category_text(viewpoint_data.get('category', 'Functional'))
        else:
            viewpoint = str(viewpoint_data)
            priority = l10n.get_priority_text('MEDIUM')
            category = l10n.get_category_text('Functional')
        
        writer.writerow([
            f"TC-{idx:03d}",
            comp.get('name', ''),
            l10n.get_component_text(comp.get('type', '')),
            viewpoint,
            testcase.get('steps', testcase),
            testcase.get('expected', ''),
            priority,
            category,
            l10n.format_date(datetime.now())
        ])
    
    return output.getvalue()

def _format_excel_japanese(testcases: List[Dict[str, Any]], l10n: LocalizationManager) -> bytes:
    """日本語Excelフォーマット"""
    # データフレーム作成
    data = []
    
    for idx, case in enumerate(testcases, 1):
        comp = case.get('component', {})
        testcase = case.get('testcase', {})
        viewpoint_data = case.get('viewpoint', {})
        
        # 観点データの処理
        if isinstance(viewpoint_data, dict):
            viewpoint = viewpoint_data.get('viewpoint', '')
            priority = l10n.get_priority_text(viewpoint_data.get('priority', 'MEDIUM'))
            category = l10n.get_category_text(viewpoint_data.get('category', 'Functional'))
            checklist = viewpoint_data.get('checklist', [])
            expected_result = viewpoint_data.get('expected_result', '')
            notes = viewpoint_data.get('notes', '')
        else:
            viewpoint = str(viewpoint_data)
            priority = l10n.get_priority_text('MEDIUM')
            category = l10n.get_category_text('Functional')
            checklist = []
            expected_result = ''
            notes = ''
        
        data.append({
            l10n.get_text("test_case_id"): f"TC-{idx:03d}",
            l10n.get_text("page"): comp.get('name', ''),
            l10n.get_text("component"): l10n.get_component_text(comp.get('type', '')),
            l10n.get_text("viewpoint"): viewpoint,
            l10n.get_text("steps"): testcase.get('steps', testcase),
            l10n.get_text("expected_result"): testcase.get('expected', ''),
            l10n.get_text("priority"): priority,
            l10n.get_text("category"): category,
            "チェックリスト": '\n'.join(checklist) if checklist else '',
            "期待目的": expected_result,
            l10n.get_text("notes"): notes,
            l10n.get_text("created_date"): l10n.format_date(datetime.now())
        })
    
    df = pd.DataFrame(data)
    
    # Excelファイル作成
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='テストケース', index=False)
        
        # ワークシート取得
        worksheet = writer.sheets['テストケース']
        
        # 列幅自動調整
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    return output.getvalue()

def _format_markdown_japanese(testcases: List[Dict[str, Any]], l10n: LocalizationManager) -> str:
    """日本語Markdownフォーマット"""
    lines = [
        f"# {l10n.get_text('test_case')}一覧",
        f"生成日時: {l10n.format_datetime(datetime.now())}",
        "",
        f"| {l10n.get_text('test_case_id')} | {l10n.get_text('page')} | {l10n.get_text('component')} | {l10n.get_text('viewpoint')} | {l10n.get_text('steps')} | {l10n.get_text('expected_result')} |",
        "|---|---|---|---|---|---|"
    ]
    
    for idx, case in enumerate(testcases, 1):
        comp = case.get('component', {})
        testcase = case.get('testcase', {})
        viewpoint_data = case.get('viewpoint', {})
        
        if isinstance(viewpoint_data, dict):
            viewpoint = viewpoint_data.get('viewpoint', '')
        else:
            viewpoint = str(viewpoint_data)
        
        lines.append(
            f"| TC-{idx:03d} | {comp.get('name', '')} | {l10n.get_component_text(comp.get('type', ''))} | {viewpoint} | {testcase.get('steps', testcase)} | {testcase.get('expected', '')} |"
        )
    
    return '\n'.join(lines)