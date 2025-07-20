from fastapi import FastAPI, UploadFile, Form, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse, Response
import tempfile
import shutil
from datetime import datetime
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
from utils.viewpoints_parser import ViewpointsParser
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
    viewpoints_db: UploadFile,
    provider: str = Form(None),
    api_key: str = Form(None),
    endpoint: str = Form(None),
    temperature: float = Form(0.2),
    prompt_template: str = Form(None),
    few_shot_examples: str = Form(None)
):
    clean_json_obj = json.load(clean_json.file)
    viewpoints_db_obj = json.load(viewpoints_db.file)
    
    # 如果提供了LLM参数，使用LLM模式
    if provider or api_key:
        few_shot = json.loads(few_shot_examples) if few_shot_examples else None
        llm_cfg = {
            'provider': provider or 'gpt-4o',
            'api_key': api_key or os.environ.get('OPENAI_API_KEY', ''),
            'endpoint': endpoint,
            'temperature': temperature
        }
        llm_client = LLMClient(**llm_cfg)
        result = match_viewpoints(clean_json_obj, viewpoints_db_obj, llm_client, prompt_template, few_shot)
    else:
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
        'provider': provider or 'gpt-4o',
        'api_key': api_key or os.environ.get('OPENAI_API_KEY', ''),
        'endpoint': endpoint,
        'temperature': temperature
    }
    llm_client = LLMClient(**llm_cfg)
    result = generate_testcases(component_viewpoints_obj, llm_client, prompt_template, few_shot)
    INTERMEDIATE_RESULTS['generate_testcases'] = result
    return JSONResponse(result)

@app.post("/run_node/route_infer/")
async def run_node_route_infer(
    clean_json: UploadFile,
    provider: str = Form(None),
    api_key: str = Form(None),
    endpoint: str = Form(None),
    temperature: float = Form(0.2),
    prompt_template: str = Form(None),
    few_shot_examples: str = Form(None)
):
    clean_json_obj = json.load(clean_json.file)
    
    # 如果提供了LLM参数，使用LLM模式
    if provider or api_key:
        few_shot = json.loads(few_shot_examples) if few_shot_examples else None
        llm_cfg = {
            'provider': provider or 'gpt-4o',
            'api_key': api_key or os.environ.get('OPENAI_API_KEY', ''),
            'endpoint': endpoint,
            'temperature': temperature
        }
        llm_client = LLMClient(**llm_cfg)
        result = route_infer(clean_json_obj, llm_client, prompt_template, few_shot)
    else:
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
        'provider': provider or 'gpt-4o',
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
    output_format: str = Form('excel'),
    language: str = Form('ja'),
    provider: str = Form(None),
    api_key: str = Form(None),
    endpoint: str = Form(None),
    temperature: float = Form(0.2),
    prompt_template: str = Form(None),
    few_shot_examples: str = Form(None)
):
    testcases_obj = json.load(testcases.file)
    
    # LLMパラメータが提供された場合、LLMモードを使用
    if provider or api_key:
        few_shot = json.loads(few_shot_examples) if few_shot_examples else None
        llm_cfg = {
            'provider': provider or 'gpt-4o',
            'api_key': api_key or os.environ.get('OPENAI_API_KEY', ''),
            'endpoint': endpoint,
            'temperature': temperature
        }
        llm_client = LLMClient(**llm_cfg)
        result = format_output(testcases_obj, output_format, llm_client, prompt_template, few_shot, language)
    else:
        result = format_output(testcases_obj, output_format, language=language)
    
    INTERMEDIATE_RESULTS['format_output'] = result
    
    # Excelファイルの場合はバイナリレスポンス
    if output_format == 'excel':
        return Response(
            content=result,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=テストケース_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"}
        )
    else:
        return PlainTextResponse(result)

@app.get("/intermediate/{node_name}")
async def get_intermediate_result(node_name: str):
    result = INTERMEDIATE_RESULTS.get(node_name)
    if result is None:
        return JSONResponse({"error": "No result for node."}, status_code=404)
    return JSONResponse(result)

@app.post("/parse_viewpoints/")
async def parse_viewpoints(
    viewpoints_file: UploadFile,
    file_extension: str = Form(None)
):
    """テスト観点ファイルを解析"""
    try:
        file_content = await viewpoints_file.read()
        filename = viewpoints_file.filename
        
        # ファイル拡張子を決定
        if file_extension:
            ext = file_extension
        elif filename and '.' in filename:
            ext = filename.split('.')[-1]
        else:
            raise HTTPException(status_code=400, detail="ファイル拡張子を指定してください")
        
        # テスト観点を解析
        parser = ViewpointsParser()
        viewpoints_data = parser.parse_viewpoints(file_content, ext, filename)
        
        # 有効性を検証
        if not parser.validate_viewpoints(viewpoints_data):
            raise HTTPException(status_code=400, detail="無効なテスト観点データです")
        
        return JSONResponse({
            "success": True,
            "message": "テスト観点が正常に解析されました",
            "data": viewpoints_data,
            "format": ext,
            "component_count": len(viewpoints_data),
            "total_viewpoints": sum(len(viewpoints) for viewpoints in viewpoints_data.values())
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"テスト観点の解析に失敗しました: {str(e)}")

@app.get("/viewpoints/formats")
async def get_supported_viewpoint_formats():
    """サポートされているテスト観点形式を取得"""
    parser = ViewpointsParser()
    return JSONResponse({
        "supported_formats": parser.get_supported_formats(),
        "examples": parser.get_format_examples()
    })

@app.get("/system/language")
async def get_system_language():
    """システムの言語設定を取得"""
    return JSONResponse({
        "current_language": "ja",
        "supported_languages": ["en", "ja"],
        "default_language": "ja"
    })

@app.post("/system/language")
async def set_system_language(language: str = Form(...)):
    """システムの言語設定を変更"""
    if language not in ["en", "ja"]:
        raise HTTPException(status_code=400, detail="サポートされていない言語です")
    
    # ここでシステム言語設定を更新
    return JSONResponse({
        "message": f"言語が{language}に設定されました",
        "language": language
    })
