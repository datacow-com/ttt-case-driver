from fastapi import FastAPI, UploadFile, Form, Request
from fastapi.responses import PlainTextResponse, JSONResponse
import tempfile
import shutil
from workflow import run_workflow
from nodes.load_page import load_page
from nodes.match_viewpoints import match_viewpoints
from nodes.generate_testcases import generate_testcases
from nodes.route_infer import route_infer
from nodes.generate_cross_page_case import generate_cross_page_case
from nodes.format_output import format_output
from utils.config_loader import load_config, get_agent_config
from utils.llm_client import LLMClient
from utils.param_utils import save_temp_upload, parse_yaml_file
import os
import json

app = FastAPI()

# 用于存储中间结果，实际生产建议用数据库
INTERMEDIATE_RESULTS = {}

@app.post("/run_workflow/")
async def run_workflow_api(
    figma_yaml: UploadFile,
    viewpoints_yaml: UploadFile,
    output_format: str = Form('csv')
):
    with tempfile.NamedTemporaryFile(delete=False) as f1, tempfile.NamedTemporaryFile(delete=False) as f2:
        shutil.copyfileobj(figma_yaml.file, f1)
        shutil.copyfileobj(viewpoints_yaml.file, f2)
        figma_yaml_path = f1.name
        viewpoints_yaml_path = f2.name
    output = run_workflow(figma_yaml_path, viewpoints_yaml_path, output_format)
    return PlainTextResponse(output)

# ----------- 节点级API实现 -------------

@app.post("/run_node/load_page/")
async def run_node_load_page(figma_yaml: UploadFile):
    yaml_path = save_temp_upload(figma_yaml)
    page_structure = load_page(yaml_path)
    INTERMEDIATE_RESULTS['load_page'] = page_structure
    return JSONResponse(page_structure)

@app.post("/run_node/match_viewpoints/")
async def run_node_match_viewpoints(
    page_structure: UploadFile,
    viewpoints_yaml: UploadFile
):
    page_structure_obj = parse_yaml_file(save_temp_upload(page_structure))
    viewpoints_path = save_temp_upload(viewpoints_yaml)
    result = match_viewpoints(page_structure_obj, viewpoints_path)
    INTERMEDIATE_RESULTS['match_viewpoints'] = result
    return JSONResponse(result)

@app.post("/run_node/generate_testcases/")
async def run_node_generate_testcases(
    component_viewpoints: UploadFile,
    provider: str = Form(None),
    api_key: str = Form(None),
    endpoint: str = Form(None),
    temperature: float = Form(0.2)
):
    component_viewpoints_obj = parse_yaml_file(save_temp_upload(component_viewpoints))
    # 动态Agent配置
    llm_cfg = {
        'provider': provider or os.environ.get('OPENAI_API_KEY', 'gpt-4o'),
        'api_key': api_key or os.environ.get('OPENAI_API_KEY', ''),
        'endpoint': endpoint,
        'temperature': temperature
    }
    llm_client = LLMClient(**llm_cfg)
    result = generate_testcases(component_viewpoints_obj, llm_client)
    INTERMEDIATE_RESULTS['generate_testcases'] = result
    return JSONResponse(result)

@app.post("/run_node/route_infer/")
async def run_node_route_infer(page_structure: UploadFile):
    page_structure_obj = parse_yaml_file(save_temp_upload(page_structure))
    result = route_infer(page_structure_obj)
    INTERMEDIATE_RESULTS['route_infer'] = result
    return JSONResponse(result)

@app.post("/run_node/generate_cross_page_case/")
async def run_node_generate_cross_page_case(
    routes: UploadFile,
    testcases: UploadFile,
    provider: str = Form(None),
    api_key: str = Form(None),
    endpoint: str = Form(None),
    temperature: float = Form(0.2)
):
    routes_obj = parse_yaml_file(save_temp_upload(routes))
    testcases_obj = parse_yaml_file(save_temp_upload(testcases))
    llm_cfg = {
        'provider': provider or os.environ.get('OPENAI_API_KEY', 'gpt-4o'),
        'api_key': api_key or os.environ.get('OPENAI_API_KEY', ''),
        'endpoint': endpoint,
        'temperature': temperature
    }
    llm_client = LLMClient(**llm_cfg)
    result = generate_cross_page_case(routes_obj, testcases_obj, llm_client)
    INTERMEDIATE_RESULTS['generate_cross_page_case'] = result
    return JSONResponse(result)

@app.post("/run_node/format_output/")
async def run_node_format_output(
    testcases: UploadFile,
    output_format: str = Form('csv')
):
    testcases_obj = parse_yaml_file(save_temp_upload(testcases))
    result = format_output(testcases_obj, output_format)
    INTERMEDIATE_RESULTS['format_output'] = result
    return PlainTextResponse(result)

# ----------- 中间结果可视化接口 -------------

@app.get("/intermediate/{node_name}")
async def get_intermediate_result(node_name: str):
    result = INTERMEDIATE_RESULTS.get(node_name)
    if result is None:
        return JSONResponse({"error": "No result for node."}, status_code=404)
    return JSONResponse(result)
