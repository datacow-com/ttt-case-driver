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
from utils.redis_manager import redis_manager
from utils.state_management import StateManager
from enhanced_workflow import run_enhanced_testcase_generation, build_enhanced_workflow_with_wrappers
import os
import json

app = FastAPI()

INTERMEDIATE_RESULTS = {}

# ==================== Redis相关API端点 ====================

@app.post("/create_session/")
async def create_session(
    input_data: dict,
    config: dict = {}
):
    """创建新session"""
    session_id = StateManager.create_session(input_data, config)
    return {"session_id": session_id, "status": "created"}

@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """获取session信息"""
    session = StateManager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@app.get("/session/{session_id}/results")
async def get_session_results(session_id: str):
    """获取session的所有节点结果"""
    results = redis_manager.get_all_node_results(session_id)
    return {"session_id": session_id, "results": results}

@app.get("/session/{session_id}/stats")
async def get_session_stats(session_id: str):
    """获取session统计信息"""
    stats = redis_manager.get_session_stats(session_id)
    return stats

@app.get("/redis/stats")
async def get_redis_stats():
    """获取Redis统计信息"""
    return redis_manager.get_stats()

@app.delete("/cache/clear")
async def clear_cache(pattern: str = None):
    """清除缓存"""
    if pattern:
        deleted_count = redis_manager.clear_cache_by_pattern(pattern)
        return {"message": f"Cleared {deleted_count} cache entries", "pattern": pattern}
    else:
        # 清除所有缓存
        deleted_count = redis_manager.clear_cache_by_pattern("*")
        return {"message": f"Cleared {deleted_count} cache entries", "pattern": "all"}

@app.get("/cache/figma/{file_key}")
async def get_cached_figma_data(file_key: str):
    """获取缓存的Figma数据"""
    data = redis_manager.get_figma_data(file_key)
    if data is None:
        raise HTTPException(status_code=404, detail="Figma data not found in cache")
    return data

@app.get("/cache/viewpoints/{file_hash}")
async def get_cached_viewpoints(file_hash: str):
    """获取缓存的测试观点"""
    data = redis_manager.get_viewpoints(file_hash)
    if data is None:
        raise HTTPException(status_code=404, detail="Viewpoints not found in cache")
    return data

# ==================== 现有API端点 ====================

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
    """解析测试观点文件"""
    try:
        file_content = await viewpoints_file.read()
        filename = viewpoints_file.filename
        
        # 使用带缓存的解析方法
        viewpoints = ViewpointsParser.parse_viewpoints_with_cache(file_content, file_extension, filename)
        
        return JSONResponse({
            "success": True,
            "viewpoints": viewpoints,
            "filename": filename
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=400)

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

@app.post("/run_enhanced_workflow/")
async def run_enhanced_workflow(
    figma_file: UploadFile,
    viewpoints_file: UploadFile,
    provider: str = Form('gpt-4o'),
    api_key: str = Form(None),
    temperature: float = Form(0.2)
):
    """运行增强的测试用例生成工作流"""
    
    try:
        # 解析输入文件
        figma_data = json.load(figma_file.file)
        viewpoints_data = json.load(viewpoints_file.file)
        
        # 配置LLM客户端
        llm_cfg = {
            'provider': provider,
            'api_key': api_key or os.environ.get('OPENAI_API_KEY', ''),
            'temperature': temperature
        }
        llm_client = LLMClient(**llm_cfg)
        
        # 运行增强工作流
        result = run_enhanced_testcase_generation(figma_data, viewpoints_data, llm_client)
        
        return JSONResponse({
            "success": True,
            "workflow_result": result,
            "modules_analysis": result.get("modules_analysis", {}),
            "figma_viewpoints_mapping": result.get("figma_viewpoints_mapping", {}),
            "checklist_mapping": result.get("checklist_mapping", []),
            "test_purpose_validation": result.get("test_purpose_validation", []),
            "quality_analysis": result.get("quality_analysis", {}),
            "final_testcases": result.get("final_testcases", []),
            "workflow_log": result.get("workflow_log", [])
        })
        
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e),
            "message": "增强工作流执行失败"
        }, status_code=500)

@app.get("/workflow_status/{workflow_id}")
async def get_workflow_status(workflow_id: str):
    """获取工作流执行状态"""
    # 这里可以实现工作流状态查询
    return JSONResponse({
        "workflow_id": workflow_id,
        "status": "completed",
        "message": "工作流执行完成"
    })

@app.post("/run_enhanced_workflow_step/")
async def run_enhanced_workflow_step(
    step_name: str = Form(...),
    state_data: UploadFile = None,
    figma_file: UploadFile = None,
    viewpoints_file: UploadFile = None,
    provider: str = Form('gpt-4o'),
    api_key: str = Form(None),
    temperature: float = Form(0.2)
):
    """运行增强工作流的单个步骤"""
    
    try:
        # 配置LLM客户端
        llm_cfg = {
            'provider': provider,
            'api_key': api_key or os.environ.get('OPENAI_API_KEY', ''),
            'temperature': temperature
        }
        llm_client = LLMClient(**llm_cfg)
        
        # 根据步骤名称执行相应的节点
        if step_name == "analyze_viewpoints_modules":
            if viewpoints_file is None:
                raise HTTPException(status_code=400, detail="需要提供测试观点文件")
            viewpoints_data = json.load(viewpoints_file.file)
            state = {"viewpoints_file": viewpoints_data}
            from nodes.analyze_viewpoints_modules import analyze_viewpoints_modules
            result = analyze_viewpoints_modules(state, llm_client)
            
        elif step_name == "map_figma_to_viewpoints":
            if state_data is None or figma_file is None or viewpoints_file is None:
                raise HTTPException(status_code=400, detail="需要提供状态数据、Figma文件和测试观点文件")
            state = json.load(state_data.file)
            figma_data = json.load(figma_file.file)
            viewpoints_data = json.load(viewpoints_file.file)
            state.update({
                "figma_data": figma_data,
                "viewpoints_file": viewpoints_data
            })
            from nodes.map_figma_to_viewpoints import map_figma_to_viewpoints
            result = map_figma_to_viewpoints(state, llm_client)
            
        elif step_name == "map_checklist_to_figma_areas":
            if state_data is None:
                raise HTTPException(status_code=400, detail="需要提供状态数据")
            state = json.load(state_data.file)
            from nodes.map_checklist_to_figma_areas import map_checklist_to_figma_areas
            result = map_checklist_to_figma_areas(state, llm_client)
            
        elif step_name == "validate_test_purpose_coverage":
            if state_data is None:
                raise HTTPException(status_code=400, detail="需要提供状态数据")
            state = json.load(state_data.file)
            from nodes.validate_test_purpose_coverage import validate_test_purpose_coverage
            result = validate_test_purpose_coverage(state, llm_client)
            
        elif step_name == "deep_understanding_and_gap_analysis":
            if state_data is None:
                raise HTTPException(status_code=400, detail="需要提供状态数据")
            state = json.load(state_data.file)
            from nodes.deep_understanding_and_gap_analysis import deep_understanding_and_gap_analysis
            result = deep_understanding_and_gap_analysis(state, llm_client)
            
        elif step_name == "generate_final_testcases":
            if state_data is None:
                raise HTTPException(status_code=400, detail="需要提供状态数据")
            state = json.load(state_data.file)
            from nodes.generate_final_testcases import generate_final_testcases
            result = generate_final_testcases(state, llm_client)
            
        else:
            raise HTTPException(status_code=400, detail=f"不支持的步骤名称: {step_name}")
        
        return JSONResponse({
            "success": True,
            "step_name": step_name,
            "result": result
        })
        
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e),
            "message": f"步骤 {step_name} 执行失败"
        }, status_code=500)
