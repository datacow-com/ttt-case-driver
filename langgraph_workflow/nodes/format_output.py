from typing import List, Dict, Any
import yaml
import csv
import io
from utils.prompt_loader import PromptManager

def build_prompt(system_prompt: str, few_shot_examples: list, current_input: str) -> str:
    prompt = system_prompt + '\n'
    for ex in few_shot_examples:
        prompt += f"示例输入:\n{ex['input']}\n示例输出:\n{ex['output']}\n"
    prompt += f"当前输入:\n{current_input}\n请生成输出："
    return prompt

def format_output(testcases: List[Dict[str, Any]], output_format: str = 'csv', llm_client=None, prompt_template: str = None, few_shot_examples: list = None) -> str:
    """
    格式化输出为CSV/Markdown/YAML等，支持LLM优化
    """
    if llm_client:
        # 使用LLM优化输出
        prompt_manager = PromptManager()
        node_prompt = prompt_manager.get_prompt('format_output')
        system_prompt = prompt_template or node_prompt.get('system_prompt', '')
        few_shot = few_shot_examples or node_prompt.get('few_shot_examples', [])
        
        current_input = f"测试用例: {testcases}\n格式: {output_format}"
        prompt = build_prompt(system_prompt, few_shot, current_input)
        llm_result = llm_client.generate(prompt)
        
        # 如果LLM返回了优化后的内容，直接使用
        if llm_result.get('steps'):
            return llm_result.get('steps')
    
    # 原有的格式化逻辑
    if output_format == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['编号', '页面', '组件', '观点', '步骤', '预期结果'])
        for idx, case in enumerate(testcases, 1):
            comp = case.get('component', {})
            testcase = case.get('testcase', {})
            writer.writerow([
                f"TC-{idx:03d}",
                comp.get('name', ''),
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
            lines.append(f"| TC-{idx:03d} | {comp.get('name', '')} | {comp.get('id', '')} | {case.get('viewpoint', '')} | {testcase.get('steps', testcase)} | {testcase.get('expected', '')} |")
        return '\n'.join(lines)
    elif output_format == 'yaml':
        return yaml.dump(testcases, allow_unicode=True)
    else:
        raise ValueError(f"Unsupported format: {output_format}")