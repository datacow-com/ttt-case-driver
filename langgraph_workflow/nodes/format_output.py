from typing import List, Dict, Any
import csv
import io

def format_output(testcases: List[Dict[str, Any]], output_format: str = 'csv') -> str:
    """
    格式化输出为CSV/Markdown等
    """
    if output_format == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['编号', '页面', '组件', '观点', '步骤', '预期结果'])
        for idx, case in enumerate(testcases, 1):
            comp = case.get('component', {})
            testcase = case.get('testcase', {})
            writer.writerow([
                f"TC-{idx:03d}",
                comp.get('page', ''),
                comp.get('id', ''),
                case.get('viewpoint', ''),
                testcase.get('steps', testcase),
                testcase.get('expected', '')
            ])
        return output.getvalue()
    elif output_format == 'md':
        lines = ["| 编号 | 页面 | 组件 | 观点 | 步骤 | 预期结果 |", "|---|---|---|---|---|---|"]
        for idx, case in enumerate(testcases, 1):
            comp = case.get('component', {})
            testcase = case.get('testcase', {})
            lines.append(f"| TC-{idx:03d} | {comp.get('page', '')} | {comp.get('id', '')} | {case.get('viewpoint', '')} | {testcase.get('steps', testcase)} | {testcase.get('expected', '')} |")
        return '\n'.join(lines)
    else:
        raise ValueError(f"Unsupported format: {output_format}")
