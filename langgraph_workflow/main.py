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
from nodes.fetch_and_clean_figma_json import fetch_and_clean_figma_json, get_compression_stats, get_cache_stats
from utils.config_loader import load_config, get_agent_config
from utils.llm_client import LLMClient
from utils.param_utils import save_temp_upload, parse_yaml_file
from utils.viewpoints_parser import ViewpointsParser
from utils.redis_manager import redis_manager
from utils.state_management import StateManager
from utils.intelligent_cache_manager import intelligent_cache_manager
from utils.figma_compressor import figma_compressor
from utils.viewpoints_standardizer import viewpoints_standardizer
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

# ==================== 智能缓存管理API端点 ====================

@app.get("/cache/intelligent/stats")
async def get_intelligent_cache_stats():
    """获取智能缓存统计信息"""
    return intelligent_cache_manager.get_stats()

@app.delete("/cache/intelligent/clear")
async def clear_intelligent_cache():
    """清空智能缓存"""
    intelligent_cache_manager.clear_hot_cache()
    return {"message": "Intelligent cache cleared"}

@app.get("/cache/intelligent/hot_keys")
async def get_hot_cache_keys():
    """获取热点缓存键列表"""
    return {"hot_keys": intelligent_cache_manager.get_hot_cache_keys()}

# ==================== Figma压缩API端点 ====================

@app.get("/figma/compression/stats")
async def get_figma_compression_stats():
    """获取Figma压缩统计信息"""
    return figma_compressor.get_compression_stats()

@app.post("/figma/compress")
async def compress_figma_data(figma_data: dict):
    """压缩Figma数据"""
    compressed = figma_compressor.compress_figma_data(figma_data)
    return {"original_size": len(str(figma_data)), "compressed_size": len(str(compressed)), "data": compressed}

@app.post("/figma/decompress")
async def decompress_figma_data(compressed_data: dict):
    """解压缩Figma数据"""
    decompressed = figma_compressor.decompress_figma_data(compressed_data)
    return {"decompressed_data": decompressed}

# ==================== 测试观点标准化API端点 ====================

@app.post("/viewpoints/standardize")
async def standardize_viewpoints(viewpoints_data: dict):
    """标准化测试观点"""
    standardized = viewpoints_standardizer.standardize_viewpoints(viewpoints_data)
    return {"standardized_viewpoints": standardized}

@app.post("/viewpoints/create_mapping")
async def create_viewpoint_mapping(viewpoints_data: dict):
    """创建观点映射关系"""
    mapping = viewpoints_standardizer.create_viewpoint_mapping(viewpoints_data)
    return {"mapping": mapping}

@app.get("/viewpoints/templates/{component_type}")
async def get_component_templates(component_type: str):
    """获取组件模板"""
    templates = viewpoints_standardizer.get_component_templates(component_type)
    return {"templates": templates}

@app.post("/viewpoints/merge")
async def merge_viewpoints(viewpoints_list: list):
    """合并多个观点文件"""
    merged = viewpoints_standardizer.merge_viewpoints(viewpoints_list)
    return {"merged_viewpoints": merged}

@app.post("/viewpoints/validate")
async def validate_viewpoints_comprehensive(viewpoints_data: dict):
    """全面验证观点数据"""
    validation = viewpoints_standardizer.validate_viewpoints(viewpoints_data)
    return {"validation": validation}

# ==================== 性能监控API端点 ====================

@app.get("/performance/stats")
async def get_performance_stats():
    """获取性能统计信息"""
    return {
        "redis_stats": redis_manager.get_stats(),
        "intelligent_cache_stats": intelligent_cache_manager.get_stats(),
        "figma_compression_stats": figma_compressor.get_compression_stats(),
        "cache_stats": get_cache_stats()
    }

@app.get("/performance/token_usage")
async def get_token_usage_stats():
    """获取TOKEN使用统计"""
    # 这里可以添加TOKEN使用统计逻辑
    return {
        "total_llm_calls": 0,
        "total_tokens_used": 0,
        "cached_calls": 0,
        "tokens_saved": 0,
        "cache_hit_rate": "0%"
    }

# ==================== 现有API端点 ====================

@app.post("/run_node/fetch_and_clean_figma_json/")
async def run_node_fetch_and_clean_figma_json(
    access_token: str = Form(...),
    file_key: str = Form(...),
    enable_compression: bool = Form(True)
):
    cleaned = fetch_and_clean_figma_json(access_token, file_key, enable_compression)
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
    # few_shot_examples 传入为JSON字符串
    few_shot = json.loads(few_shot_examples) if few_shot_examples else None
    llm_cfg = {
        'provider': provider or 'gpt-4o',
        'api_key': api_key or os.environ.get('OPENAI_API_KEY', ''),
        'endpoint': endpoint,
        'temperature': temperature
    }
    llm_client = LLMClient(**llm_cfg)
    result = format_output(testcases_obj, output_format, language, llm_client, prompt_template, few_shot)
    INTERMEDIATE_RESULTS['format_output'] = result
    return JSONResponse(result)

@app.get("/intermediate/{node_name}")
async def get_intermediate_result(node_name: str):
    """获取中间结果"""
    if node_name in INTERMEDIATE_RESULTS:
        return JSONResponse(INTERMEDIATE_RESULTS[node_name])
    else:
        raise HTTPException(status_code=404, detail=f"Node {node_name} result not found")

@app.post("/parse_viewpoints/")
async def parse_viewpoints(
    viewpoints_file: UploadFile,
    file_extension: str = Form(None),
    enable_standardization: bool = Form(True)
):
    """解析测试观点文件（支持多种格式）"""
    try:
        file_content = viewpoints_file.file.read()
        viewpoints_data = ViewpointsParser.parse_viewpoints_with_cache(
            file_content, 
            file_extension, 
            viewpoints_file.filename, 
            enable_standardization
        )
        return JSONResponse({
            "success": True,
            "viewpoints": viewpoints_data,
            "file_info": {
                "filename": viewpoints_file.filename,
                "size": len(file_content),
                "format": file_extension or viewpoints_file.filename.split('.')[-1]
            }
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=400)

@app.get("/viewpoints/formats")
async def get_supported_viewpoint_formats():
    """获取支持的测试观点文件格式"""
    return {
        "supported_formats": ViewpointsParser.get_supported_formats(),
        "examples": ViewpointsParser.get_format_examples()
    }

@app.get("/system/language")
async def get_system_language():
    """获取系统语言设置"""
    config = load_config()
    return {"language": config.get('output', {}).get('language', 'ja')}

@app.post("/system/language")
async def set_system_language(language: str = Form(...)):
    """设置系统语言"""
    # 这里可以添加语言设置逻辑
    return {"message": f"Language set to {language}", "language": language}

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
    """获取工作流状态"""
    # 这里可以添加工作流状态查询逻辑
    return {"workflow_id": workflow_id, "status": "completed"}

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)