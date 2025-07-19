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
from nodes.fetch_and_clean_figma_json import fetch_and_clean_figma_json
from utils.config_loader import load_config, get_agent_config
from utils.llm_client import LLMClient
from utils.param_utils import save_temp_upload, parse_yaml_file
import os
import json

app = FastAPI()

INTERMEDIATE_RESULTS = {}

@app.post("/run_node/fetch_and_clean_figma_json/")
async def run_node_fetch_and_clean_figma_json(
    access_token: str = Form(...),
    file_key: str = Form(...)
):
    cleaned = fetch_and_clean_figma_json(access_token, file_key)
    INTERMEDIATE_RESULTS['fetch_and_clean_figma_json'] = cleaned
    return JSONResponse(cleaned)

@app.post("/run_node/match_viewpoints/")
async def run_node_match_viewpoints(
    clean_json: UploadFile,
    viewpoints_db: UploadFile
):
    clean_json_obj = json.load(clean_json.file)
    viewpoints_db_obj = json.load(viewpoints_db.file)
    result = match_viewpoints(clean_json_obj, viewpoints_db_obj)
    INTERMEDIATE_RESULTS['match_viewpoints'] = result
    return JSONResponse(result)

@app.post("/run_node/generate_testcases/")
async def run_node_generate_testcases(
    component_viewpoints: UploadFile,
    provider: str = Form(None),
    api_key: str = Form(None),
    endpoint: str = Form(None),
    temperature: float = Form(0.2),
    prompt_template: str = Form(None),
    few_shot_examples: str = Form(None)
):
    component_viewpoints_obj = json.load(component_viewpoints.file)
    # few_shot_examples 传入为JSON字符串
    few_shot = json.loads(few_shot_examples) if few_shot_examples else None
    llm_cfg = {
        'provider': provider or os.environ.get('OPENAI_API_KEY', 'gpt-4o'),
        'api_key': api_key or os.environ.get('OPENAI_API_KEY', ''),
        'endpoint': endpoint,
        'temperature': temperature
    }
    llm_client = LLMClient(**llm_cfg)
    result = generate_testcases(component_viewpoints_obj, llm_client, prompt_template, few_shot)
    INTERMEDIATE_RESULTS['generate_testcases'] = result
    return JSONResponse(result)

@app.post("/run_node/route_infer/")
async def run_node_route_infer(clean_json: UploadFile):
    clean_json_obj = json.load(clean_json.file)
    result = route_infer(clean_json_obj)
    INTERMEDIATE_RESULTS['route_infer'] = result
    return JSONResponse(result)

@app.post("/run_node/generate_cross_page_case/")
async def run_node_generate_cross_page_case(
    routes: UploadFile,
    testcases: UploadFile,
    provider: str = Form(None),
    api_key: str = Form(None),
    endpoint: str = Form(None),
    temperature: float = Form(0.2),
    prompt_template: str = Form(None),
    few_shot_examples: str = Form(None)
):
    routes_obj = json.load(routes.file)
    testcases_obj = json.load(testcases.file)
    few_shot = json.loads(few_shot_examples) if few_shot_examples else None
    llm_cfg = {
        'provider': provider or os.environ.get('OPENAI_API_KEY', 'gpt-4o'),
        'api_key': api_key or os.environ.get('OPENAI_API_KEY', ''),
        'endpoint': endpoint,
        'temperature': temperature
    }
    llm_client = LLMClient(**llm_cfg)
    result = generate_cross_page_case(routes_obj, testcases_obj, llm_client, prompt_template, few_shot)
    INTERMEDIATE_RESULTS['generate_cross_page_case'] = result
    return JSONResponse(result)

@app.post("/run_node/format_output/")
async def run_node_format_output(
    testcases: UploadFile,
    output_format: str = Form('csv')
):
    testcases_obj = json.load(testcases.file)
    result = format_output(testcases_obj, output_format)
    INTERMEDIATE_RESULTS['format_output'] = result
    return PlainTextResponse(result)

@app.get("/intermediate/{node_name}")
async def get_intermediate_result(node_name: str):
    result = INTERMEDIATE_RESULTS.get(node_name)
    if result is None:
        return JSONResponse({"error": "No result for node."}, status_code=404)
    return JSONResponse(result)
