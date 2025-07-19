from nodes.load_page import load_page
from nodes.match_viewpoints import match_viewpoints
from nodes.generate_testcases import generate_testcases
from nodes.route_infer import route_infer
from nodes.generate_cross_page_case import generate_cross_page_case
from nodes.format_output import format_output
from utils.config_loader import load_config, get_agent_config
from utils.llm_client import LLMClient


def run_workflow(figma_yaml_path, viewpoints_yaml_path, output_format='csv'):
    config = load_config()
    # 1. 加载页面结构
    page_structure = load_page(figma_yaml_path)
    # 2. 匹配测试观点
    component_viewpoints = match_viewpoints(page_structure, viewpoints_yaml_path)
    # 3. 生成组件级测试用例
    llm_cfg = get_agent_config('generate_testcases', config)
    llm_client = LLMClient(**llm_cfg)
    testcases = generate_testcases(component_viewpoints, llm_client)
    # 4. 路由链推理
    routes = route_infer(page_structure)
    # 5. 生成跨页用例
    llm_cfg_cross = get_agent_config('generate_cross_page_case', config)
    llm_client_cross = LLMClient(**llm_cfg_cross)
    cross_page_cases = generate_cross_page_case(routes, testcases, llm_client_cross)
    # 6. 格式化输出
    output = format_output(testcases + cross_page_cases, output_format)
    return output
