from typing import Dict, Any
import os
import json
from fastapi import HTTPException
from nodes.fetch_figma_data import fetch_figma_data
from nodes.match_viewpoints import match_viewpoints
from nodes.generate_testcases import generate_testcases
from nodes.route_infer import route_infer
from nodes.generate_cross_page_case import generate_cross_page_case
from nodes.format_output import format_output

def run_workflow(figma_yaml_path: str, viewpoints_db_path: str):
    """运行工作流"""
    # 加载Figma数据
    figma_access_token = os.environ.get("FIGMA_ACCESS_TOKEN", "")
    figma_file_key = os.environ.get("FIGMA_FILE_KEY", "")
    
    if not figma_access_token or not figma_file_key:
        # 尝试从文件路径中读取
        try:
            with open(figma_yaml_path, 'r') as f:
                figma_data = json.load(f)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"无法读取Figma数据: {str(e)}")
    else:
        # 使用API获取数据
        try:
            figma_data = fetch_figma_data(figma_access_token, figma_file_key)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"无法通过API获取Figma数据: {str(e)}")
    
    # 加载测试观点数据库
    with open(viewpoints_db_path, 'r') as f:
        viewpoints_db = json.load(f)
    
    # 匹配测试观点
    component_viewpoints = match_viewpoints(figma_data, viewpoints_db)
    
    # 推断路由
    routes = route_infer(figma_data)
    
    # 生成测试用例
    testcases = generate_testcases(component_viewpoints)
    
    # 生成跨页面测试用例
    cross_page_cases = generate_cross_page_case(routes, testcases)
    
    # 格式化输出
    formatted_output = format_output(cross_page_cases)
    
    return {
        "testcases": testcases,
        "cross_page_cases": cross_page_cases,
        "formatted_output": formatted_output
    }
