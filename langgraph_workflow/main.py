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
