from fastapi import FastAPI, UploadFile, Form, Request, HTTPException, Depends, Body
from fastapi.responses import PlainTextResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
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
from utils.enhanced_config_loader import config_loader
from utils.llm_client_factory import SmartLLMClient, LLMClientFactory
from utils.config_validator import ConfigValidator
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
import yaml
from typing import Any, List
import uuid
import asyncio

# 任务优先级常量
PRIORITY_HIGH = "high"
PRIORITY_MEDIUM = "medium"
PRIORITY_LOW = "low"

# 优先级对应的资源分配
PRIORITY_RESOURCES = {
    PRIORITY_HIGH: {"max_workers": 8, "timeout": 60},
    PRIORITY_MEDIUM: {"max_workers": 4, "timeout": 120},
    PRIORITY_LOW: {"max_workers": 2, "timeout": 300}
}

def process_with_priority(priority: str = PRIORITY_MEDIUM, **kwargs):
    """根据优先级分配计算资源
    
    Args:
        priority: 任务优先级，可选值为high、medium、low
        **kwargs: 其他参数
        
    Returns:
        包含资源分配的参数字典
    """
    # 获取优先级对应的资源分配
    resources = PRIORITY_RESOURCES.get(priority, PRIORITY_RESOURCES[PRIORITY_MEDIUM])
    
    # 合并资源分配和其他参数
    params = {**kwargs}
    
    # 如果未指定max_workers，则使用优先级对应的值
    if "max_workers" not in params and "max_workers" in resources:
        params["max_workers"] = resources["max_workers"]
    
    # 如果未指定timeout，则使用优先级对应的值
    if "timeout" not in params and "timeout" in resources:
        params["timeout"] = resources["timeout"]
    
    return params

app = FastAPI(
    title="LangGraph Workflow API",
    description="マルチモデル・マルチプロバイダーをサポートするFigmaテストケース生成API",
    version="2.0.0"
)

# CORSミドルウェアを追加
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

INTERMEDIATE_RESULTS = {}

# ==================== 設定管理API ====================

@app.get("/config/providers")
async def get_available_providers():
    """利用可能なプロバイダーを取得"""
    return {
        "providers": config_loader.get_available_providers()
    }

@app.get("/config/provider/{provider_name}")
async def get_provider_config(provider_name: str):
    """プロバイダー設定を取得"""
    try:
        provider_config = config_loader.get_provider_config(provider_name)
        return {
            "name": provider_config.name,
            "endpoint": provider_config.endpoint,
            "default_model": provider_config.default_model,
            "models": {
                model_name: {
                    "name": model.name,
                    "max_tokens": model.max_tokens,
                    "cost_per_1k_tokens": model.cost_per_1k_tokens,
                    "capabilities": model.capabilities
                } for model_name, model in provider_config.models.items()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"プロバイダー設定が見つかりません: {str(e)}")

@app.get("/config/models")
async def get_available_models(provider: str = None):
    """利用可能なモデルを取得"""
    return config_loader.get_available_models(provider)

@app.get("/config/agents")
async def get_available_agents():
    """利用可能なエージェントを取得"""
    return {
        "agents": list(config_loader.config["llm_agents"].keys())
    }

@app.get("/config/agent/{agent_name}")
async def get_agent_config(agent_name: str):
    """エージェント設定を取得"""
    try:
        agent_config = config_loader.get_agent_config(agent_name)
        return {
            "provider": agent_config.provider,
            "model": agent_config.model,
            "temperature": agent_config.temperature,
            "max_tokens": agent_config.max_tokens,
            "fallback_providers": agent_config.fallback_providers,
            "custom_params": agent_config.custom_params
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"エージェント設定が見つかりません: {str(e)}")

@app.post("/config/validate")
async def validate_config():
    """設定を検証"""
    return ConfigValidator.validate_all_configs()

@app.post("/config/test_provider/{provider_name}")
async def test_provider(provider_name: str):
    """プロバイダー接続をテスト"""
    return ConfigValidator.test_provider_connection(provider_name)

@app.post("/config/test_agent/{agent_name}")
async def test_agent(agent_name: str):
    """エージェント設定をテスト"""
    return ConfigValidator.test_agent_configuration(agent_name)

@app.get("/config/reload")
async def reload_config():
    """設定を再読み込み"""
    config_loader.reload_config()
    return {"status": "success", "message": "設定を再読み込みしました"}

@app.post("/config/update")
async def update_config(config_data: dict):
    """設定を更新"""
    try:
        # 設定ファイルのパスを取得
        config_path = config_loader.config_path
        
        # 現在の設定をバックアップ
        backup_path = f"{config_path}.bak"
        with open(config_path, 'r') as f:
            current_config = f.read()
        with open(backup_path, 'w') as f:
            f.write(current_config)
        
        # 新しい設定を書き込み
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        # 設定を再読み込み
        config_loader.reload_config()
        
        # 検証
        validation = ConfigValidator.validate_all_configs()
        if not validation["valid"]:
            # 検証に失敗した場合はバックアップから復元
            with open(backup_path, 'r') as f:
                backup_config = f.read()
            with open(config_path, 'w') as f:
                f.write(backup_config)
            config_loader.reload_config()
            return {
                "status": "error",
                "message": "設定の検証に失敗しました",
                "validation": validation
            }
        
        return {
            "status": "success",
            "message": "設定を更新しました",
            "validation": validation
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"設定の更新に失敗しました: {str(e)}"
        }

@app.get("/config/export")
async def export_config():
    """現在の設定をエクスポート"""
    return config_loader.config

# ==================== Redis関連APIエンドポイント ====================

@app.post("/create_session/")
async def create_session(
    input_data: dict,
    config: dict = {}
):
    """新しいセッションを作成"""
    session_id = StateManager.create_session(input_data, config)
    return {"session_id": session_id, "status": "created"}

@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """セッション情報を取得"""
    session = StateManager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@app.get("/session/{session_id}/results")
async def get_session_results(session_id: str):
    """セッションのすべてのノード結果を取得"""
    results = redis_manager.get_all_node_results(session_id)
    return {"session_id": session_id, "results": results}

@app.get("/session/{session_id}/stats")
async def get_session_stats(session_id: str):
    """セッション統計情報を取得"""
    stats = redis_manager.get_session_stats(session_id)
    return stats

@app.get("/redis/stats")
async def get_redis_stats():
    """Redis統計情報を取得"""
    return redis_manager.get_stats()

@app.delete("/cache/clear")
async def clear_cache(pattern: str = None):
    """キャッシュをクリア"""
    if pattern:
        deleted_count = redis_manager.clear_cache_by_pattern(pattern)
        return {"message": f"{deleted_count}件のキャッシュエントリをクリアしました", "pattern": pattern}
    else:
        # すべてのキャッシュをクリア
        deleted_count = redis_manager.clear_cache_by_pattern("*")
        return {"message": f"{deleted_count}件のキャッシュエントリをクリアしました", "pattern": "all"}

@app.get("/cache/figma/{file_key}")
async def get_cached_figma_data(file_key: str):
    """キャッシュされたFigmaデータを取得"""
    data = redis_manager.get_figma_data(file_key)
    if data is None:
        raise HTTPException(status_code=404, detail="Figmaデータがキャッシュに見つかりません")
    return data

@app.get("/cache/viewpoints/{file_hash}")
async def get_cached_viewpoints(file_hash: str):
    """キャッシュされたテスト観点を取得"""
    data = redis_manager.get_viewpoints(file_hash)
    if data is None:
        raise HTTPException(status_code=404, detail="テスト観点がキャッシュに見つかりません")
    return data

# ==================== インテリジェントキャッシュ管理APIエンドポイント ====================

@app.get("/cache/intelligent/stats")
async def get_intelligent_cache_stats():
    """インテリジェントキャッシュ統計情報を取得"""
    return intelligent_cache_manager.get_stats()

@app.delete("/cache/intelligent/clear")
async def clear_intelligent_cache():
    """インテリジェントキャッシュをクリア"""
    intelligent_cache_manager.clear_hot_cache()
    return {"message": "インテリジェントキャッシュをクリアしました"}

@app.get("/cache/intelligent/hot_keys")
async def get_hot_cache_keys():
    """ホットキャッシュキーリストを取得"""
    return {"hot_keys": intelligent_cache_manager.get_hot_cache_keys()}

# ==================== Figma圧縮APIエンドポイント ====================

@app.get("/figma/compression/stats")
async def get_figma_compression_stats():
    """Figma圧縮統計情報を取得"""
    return figma_compressor.get_compression_stats()

@app.post("/figma/compress")
async def compress_figma_data(figma_data: dict):
    """Figmaデータを圧縮"""
    compressed = figma_compressor.compress_figma_data(figma_data)
    return {"original_size": len(str(figma_data)), "compressed_size": len(str(compressed)), "data": compressed}

@app.post("/figma/decompress")
async def decompress_figma_data(compressed_data: dict):
    """Figmaデータを解凍"""
    decompressed = figma_compressor.decompress_figma_data(compressed_data)
    return {"decompressed_data": decompressed}

# ==================== テスト観点標準化APIエンドポイント ====================

@app.post("/viewpoints/standardize")
async def standardize_viewpoints(viewpoints_data: dict):
    """テスト観点を標準化"""
    standardized = viewpoints_standardizer.standardize_viewpoints(viewpoints_data)
    return {"standardized_viewpoints": standardized}

@app.post("/viewpoints/create_mapping")
async def create_viewpoint_mapping(viewpoints_data: dict):
    """観点マッピング関係を作成"""
    mapping = viewpoints_standardizer.create_viewpoint_mapping(viewpoints_data)
    return {"mapping": mapping}

@app.get("/viewpoints/templates/{component_type}")
async def get_component_templates(component_type: str):
    """コンポーネントテンプレートを取得"""
    templates = viewpoints_standardizer.get_component_templates(component_type)
    return {"templates": templates}

@app.post("/viewpoints/merge")
async def merge_viewpoints(viewpoints_list: list):
    """複数の観点ファイルをマージ"""
    merged = viewpoints_standardizer.merge_viewpoints(viewpoints_list)
    return {"merged_viewpoints": merged}

@app.post("/viewpoints/validate")
async def validate_viewpoints_comprehensive(viewpoints_data: dict):
    """観点データを包括的に検証"""
    validation = viewpoints_standardizer.validate_viewpoints(viewpoints_data)
    return {"validation": validation}

# ==================== パフォーマンスモニタリングAPIエンドポイント ====================

@app.get("/performance/stats")
async def get_performance_stats():
    """パフォーマンス統計情報を取得"""
    return {
        "redis_stats": redis_manager.get_stats(),
        "intelligent_cache_stats": intelligent_cache_manager.get_stats(),
        "figma_compression_stats": figma_compressor.get_compression_stats(),
        "cache_stats": get_cache_stats()
    }

@app.get("/performance/token_usage")
async def get_token_usage_stats():
    """トークン使用統計を取得"""
    # SmartLLMClientからトークン使用統計を取得
    client = SmartLLMClient("match_viewpoints")
    return client.get_usage_stats()

# ==================== ノードAPIエンドポイント ====================

@app.post("/run_node/fetch_and_clean_figma_json/")
async def run_node_fetch_and_clean_figma_json(
    access_token: str = Form(...),
    file_key: str = Form(...),
    enable_compression: bool = Form(True)
):
    """Figma JSONを取得してクリーニング"""
    cleaned = fetch_and_clean_figma_json(access_token, file_key, enable_compression)
    INTERMEDIATE_RESULTS['fetch_and_clean_figma_json'] = cleaned
    return JSONResponse(cleaned)

@app.post("/run_node/load_page/")
async def run_node_load_page(
    figma_yaml: str = Body(...),
    extract_frames_only: bool = Body(False)
):
    """加载页面结构并提取Frame信息"""
    try:
        # 解析Figma数据
        figma_data = json.loads(figma_yaml)
        
        # 提取所有Frame
        from nodes.load_page import extract_frames, process_figma_data
        frames = extract_frames(figma_data)
        
        # 如果只需要提取Frame（用于手动选择）
        if extract_frames_only:
            # 准备Frame选项列表（用于UI显示）
            frame_options = [
                {"value": frame["id"], "label": f"{frame['path']} ({frame['type']})"} 
                for frame in frames
            ]
            
            # 缓存原始Figma数据，以便后续处理
            figma_cache_id = cache_node_data(figma_data, "figma_data")
            
            return JSONResponse({
                "available_frames": frame_options,
                "cache_id": figma_cache_id
            })
        
        # 正常处理（不需要手动选择Frame）
        processed_data = process_figma_data(figma_data)
        
        # 缓存结果
        result_cache_id = cache_node_data(processed_data, "load_page_result")
        
        # 准备Frame选项列表（用于UI显示，虽然这里不会使用）
        frame_options = [
            {"value": frame["id"], "label": f"{frame['path']} ({frame['type']})"} 
            for frame in frames
        ]
        
        return JSONResponse({
            "content": processed_data,
            "cache_id": result_cache_id,
            "available_frames": frame_options
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理Figma数据失败: {str(e)}")

@app.post("/run_node/process_selected_frames/")
async def run_node_process_selected_frames(
    figma_cache_id: str = Form(...),
    selected_frames: list = Body(...)
):
    """处理用户选择的Frame"""
    try:
        # 从缓存获取原始Figma数据
        figma_data = redis_manager.get_cache(figma_cache_id)
        if not figma_data:
            raise HTTPException(status_code=404, detail="缓存的Figma数据未找到")
        
        # 处理选定的Frame
        from nodes.load_page import process_figma_data
        processed_data = process_figma_data(figma_data, selected_frames)
        
        # 缓存处理结果
        result_cache_id = cache_node_data(processed_data, "selected_frames_result")
        
        return JSONResponse({
            "content": processed_data,
            "cache_id": result_cache_id,
            "selected_frame_count": len(selected_frames)
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理选定Frame失败: {str(e)}")

# 添加缓存节点数据的函数
def cache_node_data(data: Any, prefix: str = "node_data") -> str:
    """缓存节点数据并返回缓存ID"""
    # 生成唯一缓存ID
    cache_id = f"{prefix}_{uuid.uuid4().hex}"
    
    # 将数据缓存到Redis
    redis_manager.set_cache(cache_id, data, ttl=3600)  # 1小时过期
    
    return cache_id

@app.post("/run_node/match_viewpoints/")
async def run_node_match_viewpoints(
    clean_json: UploadFile = None,
    clean_json_cache_id: str = Form(None),
    viewpoints_db: UploadFile = None,
    viewpoints_db_cache_id: str = Form(None),
    selected_frames: List[str] = Form(None),
    agent_name: str = Form("match_viewpoints"),
    provider: str = Form(None),
    model: str = Form(None),
    temperature: float = Form(None),
    max_tokens: int = Form(None),
    prompt_template: str = Form(None),
    few_shot_examples: str = Form(None)
):
    """テスト観点マッチングノードを実行"""
    # 从缓存或上传文件获取数据
    if clean_json_cache_id:
        clean_json_obj = redis_manager.get_cache(clean_json_cache_id)
        if not clean_json_obj:
            raise HTTPException(status_code=404, detail="缓存的页面结构数据未找到")
    elif clean_json:
        clean_json_obj = json.load(clean_json.file)
    else:
        raise HTTPException(status_code=400, detail="必须提供页面结构数据或缓存ID")
        
    if viewpoints_db_cache_id:
        viewpoints_db_obj = redis_manager.get_cache(viewpoints_db_cache_id)
        if not viewpoints_db_obj:
            raise HTTPException(status_code=404, detail="缓存的测试观点数据未找到")
    elif viewpoints_db:
        viewpoints_db_obj = json.load(viewpoints_db.file)
    else:
        raise HTTPException(status_code=400, detail="必须提供测试观点数据或缓存ID")
    
    # カスタム設定が提供されている場合、SmartLLMClientを作成
    llm_client = None
    if any([provider, model, temperature, max_tokens]):
        # カスタムクライアントを作成
        if provider and model:
            llm_client = LLMClientFactory.create_client(provider, model)
        else:
            # エージェント名を使用
            llm_client = SmartLLMClient(agent_name)
    
    # Few-shot例を解析
    few_shot = None
    if few_shot_examples:
        try:
            few_shot = json.loads(few_shot_examples)
        except:
            few_shot = None
    
    # ノードを実行
    result = match_viewpoints(
        clean_json_obj, 
        viewpoints_db_obj, 
        llm_client=llm_client,
        prompt_template=prompt_template,
        few_shot_examples=few_shot,
        agent_name=agent_name,
        selected_frames=selected_frames
    )
    
    # 缓存结果并生成缓存ID
    result_cache_id = cache_node_data(result, "match_viewpoints_result")
    
    # 保存中间结果
    INTERMEDIATE_RESULTS['match_viewpoints'] = result
    
    # 返回结果和缓存ID
    return JSONResponse({
        "content": result,
        "cache_id": result_cache_id
    })

@app.post("/run_node/generate_testcases/")
async def run_node_generate_testcases(
    component_viewpoints: UploadFile = None,
    component_viewpoints_cache_id: str = Form(None),
    agent_name: str = Form("generate_testcases"),
    provider: str = Form(None),
    model: str = Form(None),
    temperature: float = Form(None),
    max_tokens: int = Form(None),
    prompt_template: str = Form(None),
    few_shot_examples: str = Form(None),
    incremental: bool = Form(False),
    changed_component_ids: str = Form(None),
    parallel: bool = Form(True),
    max_workers: int = Form(4),
    priority: str = Form(PRIORITY_MEDIUM)
):
    """テストケース生成ノードを実行"""
    # 从缓存或上传文件获取数据
    if component_viewpoints_cache_id:
        component_viewpoints_obj = redis_manager.get_cache(component_viewpoints_cache_id)
        if not component_viewpoints_obj:
            raise HTTPException(status_code=404, detail="缓存的组件-观点映射数据未找到")
    elif component_viewpoints:
        component_viewpoints_obj = json.load(component_viewpoints.file)
    else:
        raise HTTPException(status_code=400, detail="必须提供组件-观点映射数据或缓存ID")
    
    # カスタム設定が提供されている場合、SmartLLMClientを作成
    llm_client = None
    if any([provider, model, temperature, max_tokens]):
        # カスタムクライアントを作成
        if provider and model:
            llm_client = LLMClientFactory.create_client(provider, model)
        else:
            # エージェント名を使用
            llm_client = SmartLLMClient(agent_name)
    
    # Few-shot例を解析
    few_shot = None
    if few_shot_examples:
        try:
            few_shot = json.loads(few_shot_examples)
        except:
            few_shot = None
    
    # 解析变更的组件ID
    changed_ids = None
    if changed_component_ids:
        try:
            changed_ids = json.loads(changed_component_ids)
        except:
            # 尝试以逗号分隔的字符串解析
            changed_ids = [id.strip() for id in changed_component_ids.split(",") if id.strip()]
    
    # 根据优先级分配资源
    resources = process_with_priority(
        priority=priority,
        max_workers=max_workers
    )
    
    # ノードを実行
    result = generate_testcases(
        component_viewpoints_obj, 
        llm_client=llm_client,
        prompt_template=prompt_template,
        few_shot_examples=few_shot,
        agent_name=agent_name,
        incremental=incremental,
        changed_component_ids=changed_ids,
        parallel=parallel,
        max_workers=resources["max_workers"]
    )
    
    # 缓存结果并生成缓存ID
    result_cache_id = cache_node_data(result, "generate_testcases_result")
    
    # 保存中间结果
    INTERMEDIATE_RESULTS['generate_testcases'] = result
    
    # 返回结果和缓存ID
    return JSONResponse({
        "content": result,
        "cache_id": result_cache_id
    })

@app.post("/run_node/route_infer/")
async def run_node_route_infer(
    clean_json: UploadFile = None,
    clean_json_cache_id: str = Form(None),
    agent_name: str = Form("route_infer"),
    provider: str = Form(None),
    model: str = Form(None),
    temperature: float = Form(None),
    max_tokens: int = Form(None),
    prompt_template: str = Form(None),
    few_shot_examples: str = Form(None),
    priority: str = Form(PRIORITY_HIGH)
):
    """ルート推論ノードを実行"""
    # 从缓存或上传文件获取数据
    if clean_json_cache_id:
        clean_json_obj = redis_manager.get_cache(clean_json_cache_id)
        if not clean_json_obj:
            raise HTTPException(status_code=404, detail="缓存的页面结构数据未找到")
    elif clean_json:
        clean_json_obj = json.load(clean_json.file)
    else:
        raise HTTPException(status_code=400, detail="必须提供页面结构数据或缓存ID")
    
    # カスタム設定が提供されている場合、SmartLLMClientを作成
    llm_client = None
    if any([provider, model, temperature, max_tokens]):
        # カスタムクライアントを作成
        if provider and model:
            llm_client = LLMClientFactory.create_client(provider, model)
        else:
            # エージェント名を使用
            llm_client = SmartLLMClient(agent_name)
    
    # 根据优先级分配资源
    resources = process_with_priority(priority=priority)
    
    # ノードを実行（添加超时处理）
    try:
        # 设置超时
        timeout = resources.get("timeout", 60)
        # 创建一个异步任务
        result_task = asyncio.create_task(
            asyncio.wait_for(
                asyncio.to_thread(route_infer, clean_json_obj, llm_client),
                timeout=timeout
            )
        )
        # 等待任务完成
        result = await result_task
    except asyncio.TimeoutError:
        # 超时处理
        raise HTTPException(status_code=408, detail=f"处理超时（{timeout}秒）")
    except Exception as e:
        # 其他异常处理
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")
    
    # 缓存结果并生成缓存ID
    result_cache_id = cache_node_data(result, "route_infer_result")
    
    # 保存中间结果
    INTERMEDIATE_RESULTS['route_infer'] = result
    
    # 返回结果和缓存ID
    return JSONResponse({
        "content": result,
        "cache_id": result_cache_id
    })

@app.post("/run_node/generate_cross_page_case/")
async def run_node_generate_cross_page_case(
    routes: UploadFile = None,
    routes_cache_id: str = Form(None),
    testcases: UploadFile = None,
    testcases_cache_id: str = Form(None),
    agent_name: str = Form("generate_cross_page_case"),
    provider: str = Form(None),
    model: str = Form(None),
    temperature: float = Form(None),
    max_tokens: int = Form(None),
    prompt_template: str = Form(None),
    few_shot_examples: str = Form(None),
    priority: str = Form(PRIORITY_MEDIUM)
):
    """クロスページケース生成ノードを実行"""
    # 从缓存或上传文件获取数据
    if routes_cache_id:
        routes_obj = redis_manager.get_cache(routes_cache_id)
        if not routes_obj:
            raise HTTPException(status_code=404, detail="缓存的路由信息未找到")
    elif routes:
        routes_obj = json.load(routes.file)
    else:
        raise HTTPException(status_code=400, detail="必须提供路由信息或缓存ID")
        
    if testcases_cache_id:
        testcases_obj = redis_manager.get_cache(testcases_cache_id)
        if not testcases_obj:
            raise HTTPException(status_code=404, detail="缓存的测试用例数据未找到")
    elif testcases:
        testcases_obj = json.load(testcases.file)
    else:
        raise HTTPException(status_code=400, detail="必须提供测试用例数据或缓存ID")
    
    # カスタム設定が提供されている場合、SmartLLMClientを作成
    llm_client = None
    if any([provider, model, temperature, max_tokens]):
        # カスタムクライアントを作成
        if provider and model:
            llm_client = LLMClientFactory.create_client(provider, model)
        else:
            # エージェント名を使用
            llm_client = SmartLLMClient(agent_name)
    
    # Few-shot例を解析
    few_shot = None
    if few_shot_examples:
        try:
            few_shot = json.loads(few_shot_examples)
        except:
            few_shot = None
    
    # 根据优先级分配资源
    resources = process_with_priority(priority=priority)
    
    # ノードを実行（添加超时处理）
    try:
        # 设置超时
        timeout = resources.get("timeout", 120)
        # 创建一个异步任务
        result_task = asyncio.create_task(
            asyncio.wait_for(
                asyncio.to_thread(generate_cross_page_case, routes_obj, testcases_obj, llm_client),
                timeout=timeout
            )
        )
        # 等待任务完成
        result = await result_task
    except asyncio.TimeoutError:
        # 超时处理
        raise HTTPException(status_code=408, detail=f"处理超时（{timeout}秒）")
    except Exception as e:
        # 其他异常处理
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")
    
    # 缓存结果并生成缓存ID
    result_cache_id = cache_node_data(result, "cross_page_case_result")
    
    # 保存中间结果
    INTERMEDIATE_RESULTS['generate_cross_page_case'] = result
    
    # 返回结果和缓存ID
    return JSONResponse({
        "content": result,
        "cache_id": result_cache_id
    })

@app.post("/run_node/format_output/")
async def run_node_format_output(
    testcases: UploadFile,
    output_format: str = Form('excel'),
    language: str = Form('ja'),
    agent_name: str = Form("format_output"),
    provider: str = Form(None),
    model: str = Form(None),
    temperature: float = Form(None),
    max_tokens: int = Form(None),
    prompt_template: str = Form(None),
    few_shot_examples: str = Form(None)
):
    """出力フォーマットノードを実行"""
    testcases_obj = json.load(testcases.file)
    
    # カスタム設定が提供されている場合、SmartLLMClientを作成
    llm_client = None
    if any([provider, model, temperature, max_tokens]):
        # カスタムクライアントを作成
        if provider and model:
            llm_client = LLMClientFactory.create_client(provider, model)
        else:
            # エージェント名を使用
            llm_client = SmartLLMClient(agent_name)
    
    # ノードを実行
    result = format_output(testcases_obj, output_format, language, llm_client)
    
    INTERMEDIATE_RESULTS['format_output'] = result
    
    # Excel形式の場合はバイナリレスポンス
    if output_format == 'excel' and isinstance(result, bytes):
        filename = f"testcases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return Response(
            content=result,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    return JSONResponse(result)

@app.get("/intermediate/{node_name}")
async def get_intermediate_result(node_name: str):
    """中間結果を取得"""
    if node_name not in INTERMEDIATE_RESULTS:
        raise HTTPException(status_code=404, detail=f"ノード {node_name} の中間結果が見つかりません")
    return JSONResponse(INTERMEDIATE_RESULTS[node_name])

@app.post("/parse_viewpoints/")
async def parse_viewpoints(
    viewpoints_file: UploadFile,
    file_extension: str = Form(None),
    enable_standardization: bool = Form(True)
):
    """テスト観点を解析"""
    # 一時ファイルを保存
    temp_path = save_temp_upload(viewpoints_file)
    
    # ファイル拡張子を決定
    if not file_extension:
        file_extension = os.path.splitext(viewpoints_file.filename)[1].lower()
    
    # ViewpointsParserを使用して解析
    parser = ViewpointsParser()
    try:
        viewpoints = parser.parse_file(temp_path, file_extension)
        
        # 標準化が有効な場合
        if enable_standardization:
            viewpoints = viewpoints_standardizer.standardize_viewpoints(viewpoints)
        
        return JSONResponse(viewpoints)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"テスト観点の解析に失敗しました: {str(e)}")
    finally:
        # 一時ファイルを削除
        os.remove(temp_path)

@app.get("/viewpoints/formats")
async def get_supported_viewpoint_formats():
    """サポートされているテスト観点フォーマットを取得"""
    return {
        "formats": ["json", "csv", "xlsx", "yaml"],
        "examples": {
            "json": {"button": ["クリック時の動作確認", "無効状態の確認"]},
            "csv": "component_type,viewpoint\nbutton,クリック時の動作確認\nbutton,無効状態の確認"
        }
    }

@app.get("/system/language")
async def get_system_language():
    """システム言語を取得"""
    return {"language": "ja"}

@app.post("/system/language")
async def set_system_language(language: str = Form(...)):
    """システム言語を設定"""
    if language not in ["ja", "en"]:
        raise HTTPException(status_code=400, detail="サポートされていない言語です")
    return {"language": language}

@app.post("/run_enhanced_workflow/")
async def run_enhanced_workflow(
    figma_file: UploadFile,
    viewpoints_file: UploadFile,
    agent_name: str = Form("match_viewpoints"),
    provider: str = Form(None),
    model: str = Form(None),
    temperature: float = Form(None),
    max_tokens: int = Form(None)
):
    """拡張ワークフローを実行"""
    # ファイルを読み込む
    figma_data = json.load(figma_file.file)
    viewpoints_data = json.load(viewpoints_file.file)
    
    # カスタム設定が提供されている場合、SmartLLMClientを作成
    llm_client = None
    if any([provider, model, temperature, max_tokens]):
        # カスタムクライアントを作成
        if provider and model:
            llm_client = LLMClientFactory.create_client(provider, model)
        else:
            # エージェント名を使用
            llm_client = SmartLLMClient(agent_name)
    
    # ワークフローを実行
    workflow_id, initial_state = run_enhanced_testcase_generation(
        figma_data, viewpoints_data, llm_client
    )
    
    return {
        "workflow_id": workflow_id,
        "initial_state": initial_state,
        "status": "running"
    }

@app.get("/workflow_status/{workflow_id}")
async def get_workflow_status(workflow_id: str):
    """ワークフローステータスを取得"""
    state = StateManager.get_workflow_state(workflow_id)
    if not state:
        raise HTTPException(status_code=404, detail="ワークフローが見つかりません")
    return state

@app.post("/run_enhanced_workflow_step/")
async def run_enhanced_workflow_step(
    step_name: str = Form(...),
    state_data: UploadFile = None,
    figma_file: UploadFile = None,
    viewpoints_file: UploadFile = None,
    agent_name: str = Form(None),
    provider: str = Form(None),
    model: str = Form(None),
    temperature: float = Form(None),
    max_tokens: int = Form(None)
):
    """拡張ワークフローの単一ステップを実行"""
    
    try:
        # カスタム設定が提供されている場合、SmartLLMClientを作成
        llm_client = None
        if any([provider, model, temperature, max_tokens]):
            # カスタムクライアントを作成
            if provider and model:
                llm_client = LLMClientFactory.create_client(provider, model)
            else:
                # エージェント名を使用（デフォルトはステップ名）
                agent_name = agent_name or step_name
                llm_client = SmartLLMClient(agent_name)
        
        # ステップ名に基づいて適切なノードを実行
        if step_name == "analyze_viewpoints_modules":
            if viewpoints_file is None:
                raise HTTPException(status_code=400, detail="テスト観点ファイルが必要です")
            viewpoints_data = json.load(viewpoints_file.file)
            state = {"viewpoints_file": viewpoints_data}
            from nodes.analyze_viewpoints_modules import analyze_viewpoints_modules
            result = analyze_viewpoints_modules(state, llm_client)
            
        elif step_name == "map_figma_to_viewpoints":
            if state_data is None or figma_file is None or viewpoints_file is None:
                raise HTTPException(status_code=400, detail="状態データ、Figmaファイル、テスト観点ファイルが必要です")
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
                raise HTTPException(status_code=400, detail="状態データが必要です")
            state = json.load(state_data.file)
            from nodes.map_checklist_to_figma_areas import map_checklist_to_figma_areas
            result = map_checklist_to_figma_areas(state, llm_client)
            
        elif step_name == "validate_test_purpose_coverage":
            if state_data is None:
                raise HTTPException(status_code=400, detail="状態データが必要です")
            state = json.load(state_data.file)
            from nodes.validate_test_purpose_coverage import validate_test_purpose_coverage
            result = validate_test_purpose_coverage(state, llm_client)
            
        elif step_name == "deep_understanding_and_gap_analysis":
            if state_data is None:
                raise HTTPException(status_code=400, detail="状態データが必要です")
            state = json.load(state_data.file)
            from nodes.deep_understanding_and_gap_analysis import deep_understanding_and_gap_analysis
            result = deep_understanding_and_gap_analysis(state, llm_client)
            
        elif step_name == "generate_final_testcases":
            if state_data is None:
                raise HTTPException(status_code=400, detail="状態データが必要です")
            state = json.load(state_data.file)
            from nodes.generate_final_testcases import generate_final_testcases
            result = generate_final_testcases(state, llm_client)
            
        else:
            raise HTTPException(status_code=400, detail=f"不明なステップ名: {step_name}")
        
        return JSONResponse(result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ステップ実行エラー: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)