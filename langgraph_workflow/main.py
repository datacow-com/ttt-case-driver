from typing import Dict, Any, List, Optional, Tuple, Union
import os
import json
import time
import uuid
import asyncio
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, Body, HTTPException, Query, BackgroundTasks, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from utils.redis_manager import redis_manager
from utils.cache_manager import cache_manager
from utils.viewpoints_parser import ViewpointsParser
from utils.viewpoints_standardizer import viewpoints_standardizer
from utils.config_loader import config_loader
from utils.enhanced_config_loader import enhanced_config_loader
from utils.performance_monitor import performance_monitor
from utils.intelligent_cache_manager import intelligent_cache_manager
from utils.localization import localization
from nodes.match_viewpoints import match_viewpoints
from nodes.generate_testcases import generate_testcases
from nodes.route_infer import route_infer
from nodes.generate_cross_page_case import generate_cross_page_case
from nodes.format_output import format_output
from nodes.fetch_and_clean_figma_json import fetch_and_clean_figma_json, get_compression_stats, get_cache_stats
from nodes.fetch_figma_data import fetch_figma_data
from nodes.create_semantic_correlation_map import create_semantic_correlation_map
from nodes.evaluate_testcase_quality import evaluate_testcase_quality
from nodes.optimize_testcases import optimize_testcases
from utils.retry_controller import RetryController
import logging
import tempfile
import shutil
import yaml
from utils.param_utils import parse_yaml_file

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
async def standardize_viewpoints(
    viewpoints_data: dict,
    enable_priority_evaluation: bool = True,
    enable_classification: bool = True
):
    """测试观点标准化"""
    standardized = viewpoints_standardizer.standardize_viewpoints(viewpoints_data)
    
    # 添加分析信息
    result = {
        "viewpoints": standardized,
        "metadata": {
            "total_viewpoints": sum(len(vps) for vps in standardized.values()),
            "component_types": list(standardized.keys()),
            "standardized": True,
            "priority_evaluated": enable_priority_evaluation,
            "classified": enable_classification,
            "processed_at": datetime.now().isoformat()
        }
    }
    
    # 统计优先级分布
    if enable_priority_evaluation:
        priority_stats = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for component_vps in standardized.values():
            for vp in component_vps:
                if isinstance(vp, dict) and "priority" in vp:
                    priority = vp.get("priority", "MEDIUM")
                    priority_stats[priority] = priority_stats.get(priority, 0) + 1
        result["metadata"]["priority_stats"] = priority_stats
    
    # 统计分类分布
    if enable_classification:
        classification_stats = {
            "functional_type": {},
            "test_type": {},
            "ux_dimension": {},
            "technical_aspect": {}
        }
        
        for component_vps in standardized.values():
            for vp in component_vps:
                if isinstance(vp, dict) and "classifications" in vp:
                    for dim, classes in vp.get("classifications", {}).items():
                        for cls in classes:
                            classification_stats[dim][cls] = classification_stats[dim].get(cls, 0) + 1
        
        result["metadata"]["classification_stats"] = classification_stats
    
    return result

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
async def validate_viewpoints_comprehensive(
    viewpoints_data: dict,
    validate_classifications: bool = True,
    validate_priority: bool = True
):
    """全面验证测试观点数据"""
    validation_result = viewpoints_standardizer.validate_viewpoints(viewpoints_data)
    
    # 添加验证统计信息
    validation_result["stats"] = {
        "total_viewpoints": sum(len(vps) for vps in viewpoints_data.values()),
        "component_types": len(viewpoints_data),
        "error_count": len(validation_result["errors"]),
        "warning_count": len(validation_result["warnings"]),
        "suggestion_count": len(validation_result["suggestions"]),
        "validated_classifications": validate_classifications,
        "validated_priority": validate_priority,
        "validation_time": datetime.now().isoformat()
    }
    
    # 添加优先级统计
    if validate_priority:
        priority_stats = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "INVALID": 0}
        for component_vps in viewpoints_data.values():
            for vp in component_vps:
                if isinstance(vp, dict) and "priority" in vp:
                    priority = vp.get("priority", "MEDIUM")
                    if priority in priority_stats:
                        priority_stats[priority] += 1
                    else:
                        priority_stats["INVALID"] += 1
        validation_result["priority_stats"] = priority_stats
    
    # 添加分类统计
    if validate_classifications and any("classifications" in vp for vps in viewpoints_data.values() for vp in vps if isinstance(vp, dict)):
        classification_coverage = {
            "with_classifications": 0,
            "without_classifications": 0,
            "dimension_coverage": {
                "functional_type": 0,
                "test_type": 0,
                "ux_dimension": 0,
                "technical_aspect": 0
            }
        }
        
        total_viewpoints = 0
        for component_vps in viewpoints_data.values():
            for vp in component_vps:
                if isinstance(vp, dict):
                    total_viewpoints += 1
                    if "classifications" in vp:
                        classification_coverage["with_classifications"] += 1
                        for dim in classification_coverage["dimension_coverage"]:
                            if dim in vp["classifications"] and vp["classifications"][dim]:
                                classification_coverage["dimension_coverage"][dim] += 1
                    else:
                        classification_coverage["without_classifications"] += 1
        
        # 计算覆盖率百分比
        if total_viewpoints > 0:
            classification_coverage["classification_rate"] = round(classification_coverage["with_classifications"] / total_viewpoints * 100, 2)
            for dim in classification_coverage["dimension_coverage"]:
                classification_coverage["dimension_coverage"][f"{dim}_rate"] = round(classification_coverage["dimension_coverage"][dim] / total_viewpoints * 100, 2)
        
        validation_result["classification_coverage"] = classification_coverage
    
    return validation_result

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

@app.post("/run_node/fetch_figma_data/")
async def run_node_fetch_figma_data(
    figma_access_token: str = Body(...),
    figma_file_key: str = Body(...),
    extract_frames_only: bool = Body(False)
):
    """从Figma API获取数据并处理"""
    try:
        result = fetch_figma_data(figma_access_token, figma_file_key, extract_frames_only)
        INTERMEDIATE_RESULTS['fetch_figma_data'] = result
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取Figma数据失败: {str(e)}")



@app.post("/run_node/match_viewpoints/")
async def run_node_match_viewpoints(
    clean_json: UploadFile = None,
    clean_json_cache_id: str = Form(None),
    viewpoints_db: UploadFile = None,
    viewpoints_db_cache_id: str = Form(None),
    viewpoints_processed: Dict[str, Any] = Body(None),
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
    
    # 获取测试观点数据，优先使用处理后的数据
    if viewpoints_processed:
        viewpoints_db_obj = viewpoints_processed
    elif viewpoints_db_cache_id:
        viewpoints_db_obj = redis_manager.get_cache(viewpoints_db_cache_id)
        if not viewpoints_db_obj:
            raise HTTPException(status_code=404, detail="缓存的测试观点数据未找到")
    elif viewpoints_db:
        viewpoints_db_obj = json.load(viewpoints_db.file)
    else:
        raise HTTPException(status_code=400, detail="必须提供测试观点数据")
    
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
    semantic_correlation_map_cache_id: str = Form(None),
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
    
    # 获取语义关联映射（如果有）
    semantic_correlation_map = None
    if semantic_correlation_map_cache_id:
        semantic_correlation_map = redis_manager.get_cache(semantic_correlation_map_cache_id)
    
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
            changed_ids = None
    
    # 根据优先级分配资源
    resources = PRIORITY_RESOURCES.get(priority, {"max_workers": 4, "timeout": 120})
    actual_max_workers = resources["max_workers"] if parallel else 1
    
    # 创建初始状态
    initial_state = {
        "viewpoints_file": component_viewpoints_obj.get("viewpoints", {}),
        "figma_data": component_viewpoints_obj.get("figma_data", {})
    }
    
    # 如果有语义关联映射，添加到状态
    if semantic_correlation_map:
        initial_state["semantic_correlation_map"] = semantic_correlation_map
    
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
        max_workers=actual_max_workers
    )
    
    # 缓存结果并生成缓存ID
    result_cache_id = cache_node_data(result, "generate_testcases_result")
    
    # 保存中间结果
    INTERMEDIATE_RESULTS['generate_testcases'] = result
    
    # 返回结果和缓存ID
    return JSONResponse({
        "content": result,
        "cache_id": result_cache_id,
        "metadata": {
            "testcases_count": len(result.get("testcases", [])),
            "priority": priority,
            "parallel": parallel,
            "max_workers": actual_max_workers,
            "incremental": incremental,
            "used_semantic_correlation": semantic_correlation_map is not None
        }
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
    """跨页面テストケース生成ノードを実行"""
    # 从缓存或上传文件获取数据
    if routes_cache_id:
        routes_obj = redis_manager.get_cache(routes_cache_id)
        if not routes_obj:
            raise HTTPException(status_code=404, detail="缓存的路由数据未找到")
    elif routes:
        routes_obj = json.load(routes.file)
    else:
        raise HTTPException(status_code=400, detail="必须提供路由数据或缓存ID")
    
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
    resources = PRIORITY_RESOURCES.get(priority, {"max_workers": 4, "timeout": 120})
    
    # ノードを実行
    result = generate_cross_page_case(
        routes_obj, 
        testcases_obj, 
        llm_client=llm_client,
        prompt_template=prompt_template,
        few_shot_examples=few_shot,
        agent_name=agent_name
    )
    
    # 缓存结果并生成缓存ID
    result_cache_id = cache_node_data(result, "generate_cross_page_case_result")
    
    # 保存中间结果
    INTERMEDIATE_RESULTS['generate_cross_page_case'] = result
    
    # 返回结果和缓存ID
    return JSONResponse({
        "content": result,
        "cache_id": result_cache_id,
        "metadata": {
            "priority": priority,
            "agent_name": agent_name,
            "has_priority_info": "metadata" in result and "viewpoints_analysis" in result.get("metadata", {})
        }
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

@app.post("/viewpoints/analyze_priority")
async def analyze_viewpoints_priority(
    viewpoints_data: Dict[str, Any],
    context: Dict[str, Any] = None
):
    """分析测试观点优先级"""
    if not context:
        context = {}
    
    result = {}
    
    for component_type, viewpoints in viewpoints_data.items():
        result[component_type] = []
        
        for viewpoint in viewpoints:
            if isinstance(viewpoint, dict):
                # 设置组件类型上下文
                component_context = {
                    "component_type": component_type,
                    "is_in_main_user_flow": viewpoints_standardizer._is_in_main_user_flow(component_type),
                    "has_previous_issues": context.get("has_previous_issues", False)
                }
                
                # 评估优先级
                priority = viewpoints_standardizer.evaluate_viewpoint_priority(viewpoint, component_context)
                
                # 创建带优先级的观点副本
                vp_with_priority = viewpoint.copy()
                vp_with_priority["priority"] = priority
                vp_with_priority["priority_analysis"] = {
                    "base_priority": viewpoint.get("priority", "MEDIUM"),
                    "evaluated_priority": priority,
                    "context": component_context,
                    "evaluation_time": datetime.now().isoformat()
                }
                
                result[component_type].append(vp_with_priority)
            else:
                # 对于字符串观点，先标准化再评估
                std_viewpoint = viewpoints_standardizer._standardize_viewpoint_string(str(viewpoint))
                
                # 设置组件类型上下文
                component_context = {
                    "component_type": component_type,
                    "is_in_main_user_flow": viewpoints_standardizer._is_in_main_user_flow(component_type),
                    "has_previous_issues": context.get("has_previous_issues", False)
                }
                
                # 评估优先级
                priority = viewpoints_standardizer.evaluate_viewpoint_priority(std_viewpoint, component_context)
                
                # 更新优先级
                std_viewpoint["priority"] = priority
                std_viewpoint["priority_analysis"] = {
                    "base_priority": std_viewpoint.get("priority", "MEDIUM"),
                    "evaluated_priority": priority,
                    "context": component_context,
                    "evaluation_time": datetime.now().isoformat()
                }
                
                result[component_type].append(std_viewpoint)
    
    return JSONResponse(result)

@app.post("/viewpoints/classify")
async def classify_viewpoints(
    viewpoints_data: Dict[str, Any]
):
    """对测试观点进行多维度分类"""
    result = {}
    
    for component_type, viewpoints in viewpoints_data.items():
        result[component_type] = []
        
        for viewpoint in viewpoints:
            if isinstance(viewpoint, dict):
                # 分类观点
                classifications = viewpoints_standardizer.classify_viewpoint(viewpoint)
                
                # 创建带分类的观点副本
                vp_with_classification = viewpoint.copy()
                vp_with_classification["classifications"] = classifications
                
                result[component_type].append(vp_with_classification)
            else:
                # 对于字符串观点，先标准化再分类
                std_viewpoint = viewpoints_standardizer._standardize_viewpoint_string(str(viewpoint))
                
                # 分类观点
                classifications = viewpoints_standardizer.classify_viewpoint(std_viewpoint)
                
                # 更新分类
                std_viewpoint["classifications"] = classifications
                
                result[component_type].append(std_viewpoint)
    
    return JSONResponse(result)

@app.get("/viewpoints/formats")
async def get_supported_viewpoint_formats():
    """サポートされているテスト観点フォーマットを取得"""
    return {
        "formats": ["json", "csv", "xlsx", "xls"],
        "examples": {
            "json": {"button": ["クリック時の動作確認", "無効状態の確認"]},
            "csv": "component_type,viewpoint\nbutton,クリック時の動作確認\nbutton,無効状態の確認",
            "xlsx": "Excel格式（表格形式）"
        },
        "note": "YAML格式不再支持，请使用JSON格式代替"
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
    figma_access_token: str = Form(...),
    figma_file_key: str = Form(...),
    viewpoints_data: Dict[str, Any] = Body(...),
    agent_name: str = Form("match_viewpoints"),
    provider: str = Form(None),
    model: str = Form(None),
    temperature: float = Form(None),
    max_tokens: int = Form(None)
):
    """拡張ワークフローを実行 - 使用API方式获取Figma数据"""
    try:
        # 获取Figma数据
        figma_result = fetch_figma_data(
            figma_access_token=figma_access_token,
            figma_file_key=figma_file_key
        )
        figma_data = figma_result["figma_data"]
        
        # 使用预处理的测试观点数据
        viewpoints_processed = viewpoints_data
        
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
            figma_data, viewpoints_processed, llm_client
        )
        
        return {
            "workflow_id": workflow_id,
            "initial_state": initial_state,
            "status": "running"
        }
    except Exception as e:
        logging.error(f"运行增强工作流失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"运行增强工作流失败: {str(e)}")

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

@app.post("/extract_test_patterns/")
async def extract_test_patterns(
    standardized_cases: Dict[str, Any] = Body(...),
    cache_key_prefix: str = Form(None)
):
    """从标准化历史用例中提取测试模式"""
    try:
        from nodes.extract_test_patterns import extract_test_patterns
        
        # 提取测试模式
        result = extract_test_patterns(standardized_cases, cache_key_prefix)
        
        return {
            "status": "success",
            "message": f"成功提取测试模式，共 {result['stats']['total_patterns']} 个模式",
            "pattern_library": result['pattern_library'],
            "cache_id": result['cache_id'],
            "stats": result['stats']
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"提取测试模式失败: {str(e)}")

@app.post("/analyze_differences/")
async def analyze_differences(
    figma_data: Dict[str, Any] = Body(None),
    figma_cache_id: str = Form(None),
    historical_patterns: Dict[str, Any] = Body(None),
    patterns_cache_id: str = Form(None)
):
    """分析Figma设计与历史测试模式的差异"""
    try:
        # 获取Figma数据
        figma_to_process = None
        if figma_data:
            figma_to_process = figma_data
        elif figma_cache_id:
            figma_to_process = intelligent_cache_manager.get_with_intelligence(figma_cache_id)
            if not figma_to_process:
                raise HTTPException(status_code=404, detail=f"未找到缓存的Figma数据: {figma_cache_id}")
        else:
            raise HTTPException(status_code=400, detail="未提供Figma数据或缓存ID")
        
        # 获取历史测试模式
        patterns_to_process = None
        if historical_patterns:
            patterns_to_process = historical_patterns
        elif patterns_cache_id:
            patterns_to_process = intelligent_cache_manager.get_with_intelligence(patterns_cache_id)
            if not patterns_to_process:
                raise HTTPException(status_code=404, detail=f"未找到缓存的测试模式: {patterns_cache_id}")
        else:
            raise HTTPException(status_code=400, detail="未提供历史测试模式或缓存ID")
        
        from nodes.analyze_differences import analyze_differences
        
        # 分析差异
        result = analyze_differences(figma_to_process, patterns_to_process, patterns_cache_id)
        
        return {
            "status": "success",
            "message": f"成功分析差异，发现 {result['stats']['new_component_count']} 个新组件，{result['stats']['modified_component_count']} 个修改组件",
            "difference_report": result['difference_report'],
            "cache_id": result['cache_id'],
            "stats": result['stats']
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"分析差异失败: {str(e)}")

@app.post("/evaluate_coverage/")
async def evaluate_coverage(
    viewpoints: Dict[str, Any] = Body(None),
    viewpoints_cache_id: str = Form(None),
    difference_report: Dict[str, Any] = Body(None),
    difference_cache_id: str = Form(None),
    pattern_library: Dict[str, Any] = Body(None),
    patterns_cache_id: str = Form(None)
):
    """评估测试观点覆盖率"""
    try:w
        # 获取测试观点
        viewpoints_to_process = None
        if viewpoints:
            viewpoints_to_process = viewpoints
        elif viewpoints_cache_id:
            viewpoints_to_process = intelligent_cache_manager.get_with_intelligence(viewpoints_cache_id)
            if not viewpoints_to_process:
                raise HTTPException(status_code=404, detail=f"未找到缓存的测试观点: {viewpoints_cache_id}")
        else:
            raise HTTPException(status_code=400, detail="未提供测试观点或缓存ID")
        
        # 获取差异报告
        diff_report_to_process = None
        if difference_report:
            diff_report_to_process = difference_report
        elif difference_cache_id:
            diff_report_to_process = intelligent_cache_manager.get_with_intelligence(difference_cache_id)
            if not diff_report_to_process:
                raise HTTPException(status_code=404, detail=f"未找到缓存的差异报告: {difference_cache_id}")
        else:
            raise HTTPException(status_code=400, detail="未提供差异报告或缓存ID")
        
        # 获取测试模式库
        patterns_to_process = None
        if pattern_library:
            patterns_to_process = pattern_library
        elif patterns_cache_id:
            patterns_to_process = intelligent_cache_manager.get_with_intelligence(patterns_cache_id)
            if not patterns_to_process:
                raise HTTPException(status_code=404, detail=f"未找到缓存的测试模式库: {patterns_cache_id}")
        else:
            raise HTTPException(status_code=400, detail="未提供测试模式库或缓存ID")
        
        from nodes.evaluate_coverage import evaluate_coverage
        
        # 评估覆盖率
        result = evaluate_coverage(viewpoints_to_process, diff_report_to_process, patterns_to_process, patterns_cache_id)
        
        # 计算覆盖率百分比
        coverage_score = result['stats'].get('overall_coverage_score', 0.0)
        coverage_percentage = f"{coverage_score * 100:.1f}%"
        
        return {
            "status": "success",
            "message": f"成功评估覆盖率，总体覆盖率 {coverage_percentage}，发现 {result['stats']['gap_count']} 个覆盖缺口",
            "coverage_report": result['coverage_report'],
            "cache_id": result['cache_id'],
            "stats": result['stats']
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"评估覆盖率失败: {str(e)}")

@app.post("/run_enhanced_workflow_with_history/")
async def run_enhanced_workflow_with_history(
    figma_access_token: str = Form(...),
    figma_file_key: str = Form(...),
    viewpoints_data: Dict[str, Any] = Body(...),
    historical_cases_data: Dict[str, Any] = Body(None),
    agent_name: str = Form("match_viewpoints"),
    provider: str = Form(None),
    model: str = Form(None),
    temperature: float = Form(None),
    max_tokens: int = Form(None)
):
    """运行带历史测试用例的增强工作流 - 使用API方式获取Figma数据"""
    try:
        # 获取Figma数据
        figma_result = fetch_figma_data(
            figma_access_token=figma_access_token,
            figma_file_key=figma_file_key
        )
        figma_data = figma_result["figma_data"]
        
        # 使用预处理的测试观点数据
        viewpoints_processed = viewpoints_data
        
        # 使用预处理的历史测试用例数据
        historical_cases = historical_cases_data
        
        # 创建LLM客户端
        llm_client = SmartLLMClient(
            provider=provider or config_loader.get_agent_config(agent_name).provider,
            model=model or config_loader.get_agent_config(agent_name).model,
            temperature=temperature or config_loader.get_agent_config(agent_name).temperature,
            max_tokens=max_tokens or config_loader.get_agent_config(agent_name).max_tokens
        )
        
        # 创建工作流ID
        workflow_id = f"workflow_{uuid.uuid4()}"
        
        # 运行增强工作流
        from enhanced_workflow import run_enhanced_testcase_generation
        result = run_enhanced_testcase_generation(figma_data, viewpoints_processed, llm_client, historical_cases)
        
        # 保存工作流状态
        StateManager.save_workflow_state(workflow_id, result)
        
        return {
            "status": "success",
            "message": "成功运行增强工作流",
            "workflow_id": workflow_id,
            "final_testcases": result.get('final_testcases', []),
            "workflow_log": result.get('workflow_log', [])
        }
        
    except Exception as e:
        logging.error(f"运行增强工作流失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"运行增强工作流失败: {str(e)}")

@app.post("/run_node/create_semantic_correlation_map/")
async def run_node_create_semantic_correlation_map(
    figma_data_cache_id: str = Form(None),
    viewpoints_cache_id: str = Form(None),
    historical_patterns_cache_id: str = Form(None),
    figma_data: UploadFile = None,
    viewpoints_file: UploadFile = None,
    historical_patterns: UploadFile = None,
    agent_name: str = Form("create_semantic_correlation_map"),
    provider: str = Form(None),
    model: str = Form(None),
    temperature: float = Form(None),
    max_tokens: int = Form(None),
    priority: str = Form(PRIORITY_HIGH)
):
    """创建语义关联映射节点"""
    # 从缓存或上传文件获取数据
    figma_data_obj = await get_data_from_cache_or_file(figma_data_cache_id, figma_data)
    viewpoints_obj = await get_data_from_cache_or_file(viewpoints_cache_id, viewpoints_file)
    historical_patterns_obj = await get_data_from_cache_or_file(historical_patterns_cache_id, historical_patterns)
    
    # 创建LLM客户端
    llm_client = SmartLLMClient(
        provider=provider or config_loader.get_agent_config(agent_name).provider,
        model=model or config_loader.get_agent_config(agent_name).model,
        temperature=temperature or config_loader.get_agent_config(agent_name).temperature,
        max_tokens=max_tokens or config_loader.get_agent_config(agent_name).max_tokens
    )
    
    # 创建初始状态
    initial_state = {
        "figma_data": figma_data_obj,
        "viewpoints_file": viewpoints_obj
    }
    
    if historical_patterns_obj:
        initial_state["historical_patterns"] = historical_patterns_obj
    
    # 运行节点
    result_state = create_semantic_correlation_map(initial_state, llm_client)
    
    # 缓存结果并生成缓存ID
    result_cache_id = cache_node_data(result_state["semantic_correlation_map"], "semantic_correlation_map")
    
    # 保存中间结果
    INTERMEDIATE_RESULTS['create_semantic_correlation_map'] = result_state["semantic_correlation_map"]
    
    # 返回结果和缓存ID
    return JSONResponse({
        "content": result_state["semantic_correlation_map"],
        "cache_id": result_cache_id,
        "metadata": {
            "component_mappings": len(result_state["semantic_correlation_map"]["component_test_mapping"]),
            "criterion_mappings": len(result_state["semantic_correlation_map"].get("criterion_pattern_mapping", {})),
            "navigation_mappings": len(result_state["semantic_correlation_map"]["navigation_scenario_mapping"])
        }
    })

async def get_data_from_cache_or_file(cache_id, file):
    """从缓存或上传文件获取数据"""
    if cache_id:
        data = redis_manager.get_cache(cache_id)
        if not data:
            raise HTTPException(status_code=404, detail="缓存数据未找到")
        return data
    elif file:
        content = await file.read()
        try:
            return json.loads(content)
        except:
            raise HTTPException(status_code=400, detail="无效的JSON文件")
    else:
        return None

# 添加测试用例质量评估API端点
@app.post("/run_node/evaluate_testcase_quality/")
async def run_node_evaluate_testcase_quality(
    testcases: UploadFile = None,
    testcases_cache_id: str = Form(None),
    agent_name: str = Form("evaluate_testcase_quality"),
    provider: str = Form(None),
    model: str = Form(None),
    temperature: float = Form(None),
    max_tokens: int = Form(None),
    priority: str = Form(PRIORITY_MEDIUM)
):
    """运行测试用例质量评估节点"""
    # 获取测试用例数据
    testcases_obj = None
    if testcases:
        testcases_obj = await parse_upload_file(testcases)
    elif testcases_cache_id:
        testcases_obj = get_cached_data(testcases_cache_id)
    
    if not testcases_obj:
        raise HTTPException(status_code=400, detail="未提供测试用例数据")
    
    # 创建LLM客户端
    llm_client = create_llm_client(agent_name, provider, model, temperature, max_tokens)
    
    # 创建初始状态
    initial_state = {
        "final_testcases": testcases_obj.get("testcases", []),
        "figma_data": testcases_obj.get("figma_data", {}),
        "viewpoints_file": testcases_obj.get("viewpoints_file", {})
    }
    
    # 根据优先级分配资源
    resources = PRIORITY_RESOURCES.get(priority, {"max_workers": 2, "timeout": 60})
    
    # 运行节点
    result = evaluate_testcase_quality(initial_state, llm_client)
    
    # 缓存结果并生成缓存ID
    result_cache_id = cache_node_data(result, "evaluate_testcase_quality_result")
    
    # 保存中间结果
    INTERMEDIATE_RESULTS['evaluate_testcase_quality'] = result
    
    # 返回结果和缓存ID
    return JSONResponse({
        "content": result,
        "cache_id": result_cache_id,
        "metadata": {
            "quality_metrics_count": len(result.get("quality_metrics", [])),
            "average_quality_score": result.get("overall_quality", {}).get("average_quality_score", 0),
            "improvement_needed": result.get("overall_quality", {}).get("improvement_needed", False)
        }
    })

# 添加测试用例优化API端点
@app.post("/run_node/optimize_testcases/")
async def run_node_optimize_testcases(
    testcases: UploadFile = None,
    testcases_cache_id: str = Form(None),
    quality_metrics: UploadFile = None,
    quality_metrics_cache_id: str = Form(None),
    agent_name: str = Form("optimize_testcases"),
    provider: str = Form(None),
    model: str = Form(None),
    temperature: float = Form(None),
    max_tokens: int = Form(None),
    priority: str = Form(PRIORITY_MEDIUM)
):
    """运行测试用例优化节点"""
    # 获取测试用例数据
    testcases_obj = None
    if testcases:
        testcases_obj = await parse_upload_file(testcases)
    elif testcases_cache_id:
        testcases_obj = get_cached_data(testcases_cache_id)
    
    if not testcases_obj:
        raise HTTPException(status_code=400, detail="未提供测试用例数据")
    
    # 获取质量指标数据
    quality_metrics_obj = None
    if quality_metrics:
        quality_metrics_obj = await parse_upload_file(quality_metrics)
    elif quality_metrics_cache_id:
        quality_metrics_obj = get_cached_data(quality_metrics_cache_id)
    
    if not quality_metrics_obj:
        raise HTTPException(status_code=400, detail="未提供质量指标数据")
    
    # 创建LLM客户端
    llm_client = create_llm_client(agent_name, provider, model, temperature, max_tokens)
    
    # 创建初始状态
    initial_state = {
        "final_testcases": testcases_obj.get("testcases", []),
        "quality_metrics": quality_metrics_obj.get("quality_metrics", []),
        "overall_quality": quality_metrics_obj.get("overall_quality", {}),
        "optimization_round": 0
    }
    
    # 根据优先级分配资源
    resources = PRIORITY_RESOURCES.get(priority, {"max_workers": 2, "timeout": 120})
    
    # 运行节点
    result = optimize_testcases(initial_state, llm_client)
    
    # 缓存结果并生成缓存ID
    result_cache_id = cache_node_data(result, "optimize_testcases_result")
    
    # 保存中间结果
    INTERMEDIATE_RESULTS['optimize_testcases'] = result
    
    # 返回结果和缓存ID
    return JSONResponse({
        "content": result,
        "cache_id": result_cache_id,
        "metadata": {
            "testcases_count": len(result.get("final_testcases", [])),
            "optimization_round": result.get("optimization_round", 0),
            "optimization_logs_count": len(result.get("optimization_logs", []))
        }
    })

# 添加批量测试用例质量评估和优化API端点
@app.post("/run_workflow/evaluate_and_optimize/")
async def run_workflow_evaluate_and_optimize(
    testcases: UploadFile = None,
    testcases_cache_id: str = Form(None),
    max_retries: int = Form(3),
    quality_threshold: float = Form(0.7),
    provider: str = Form(None),
    model: str = Form(None),
    temperature: float = Form(None),
    max_tokens: int = Form(None),
    priority: str = Form(PRIORITY_HIGH)
):
    """运行测试用例质量评估和优化工作流"""
    # 获取测试用例数据
    testcases_obj = None
    if testcases:
        testcases_obj = await parse_upload_file(testcases)
    elif testcases_cache_id:
        testcases_obj = get_cached_data(testcases_cache_id)
    
    if not testcases_obj:
        raise HTTPException(status_code=400, detail="未提供测试用例数据")
    
    # 创建LLM客户端
    evaluate_client = create_llm_client("evaluate_testcase_quality", provider, model, temperature, max_tokens)
    optimize_client = create_llm_client("optimize_testcases", provider, model, temperature, max_tokens)
    
    # 创建初始状态
    initial_state = {
        "final_testcases": testcases_obj.get("testcases", []),
        "figma_data": testcases_obj.get("figma_data", {}),
        "viewpoints_file": testcases_obj.get("viewpoints_file", {}),
        "optimization_round": 0
    }
    
    # 创建重试控制器
    retry_controller = RetryController(
        max_retries=max_retries,
        quality_threshold=quality_threshold
    )
    
    # 定义评估和优化函数
    def evaluate_and_optimize(state):
        # 评估测试用例质量
        evaluated_state = evaluate_testcase_quality(state, evaluate_client)
        
        # 检查是否需要优化
        if evaluated_state.get("overall_quality", {}).get("improvement_needed", False):
            # 优化测试用例
            optimized_state = optimize_testcases(evaluated_state, optimize_client)
            return optimized_state
        else:
            return evaluated_state
    
    # 使用重试控制器执行评估和优化
    result = retry_controller.execute_with_retry(evaluate_and_optimize, initial_state)
    
    # 缓存结果并生成缓存ID
    result_cache_id = cache_node_data(result, "evaluate_and_optimize_result")
    
    # 保存中间结果
    INTERMEDIATE_RESULTS['evaluate_and_optimize'] = result
    
    # 返回结果和缓存ID
    return JSONResponse({
        "content": result,
        "cache_id": result_cache_id,
        "metadata": {
            "testcases_count": len(result.get("final_testcases", [])),
            "average_quality_score": result.get("overall_quality", {}).get("average_quality_score", 0),
            "optimization_round": result.get("optimization_round", 0)
        }
    })

@app.post("/api/workflow/start")
async def start_workflow(
    data: Dict[str, Any] = Body(...)
):
    """
    统一的工作流入口点，接收Web端预处理后的数据
    
    请求体格式:
    {
        "figma_data": {
            "access_token": "...",  // Figma API访问令牌
            "file_key": "..."       // Figma文件ID
        },
        "viewpoints_data": {...},      // 预处理后的测试观点数据
        "historical_cases": {...},     // 预处理后的历史测试用例数据（可选）
        "config": {                    // 工作流配置参数
            "manual_frame_selection": false,
            "enable_priority_evaluation": true,
            "enable_classification": true,
            ...
        }
    }
    """
    try:
        # 验证必要字段
        if "figma_data" not in data:
            raise HTTPException(status_code=400, detail="缺少Figma数据")
        if "viewpoints_data" not in data:
            raise HTTPException(status_code=400, detail="缺少测试观点数据")
        
        # 提取数据
        figma_data_config = data["figma_data"]
        viewpoints_data = data["viewpoints_data"]
        historical_cases = data.get("historical_cases", {})
        config = data.get("config", {})
        
        # 验证Figma数据配置
        if "access_token" not in figma_data_config or "file_key" not in figma_data_config:
            raise HTTPException(status_code=400, detail="Figma数据配置无效，需要包含access_token和file_key")
        
        # 使用Figma API获取数据
        try:
            figma_access_token = figma_data_config["access_token"]
            figma_file_key = figma_data_config["file_key"]
            
            # 获取Figma数据
            figma_result = fetch_figma_data(
                figma_access_token=figma_access_token,
                figma_file_key=figma_file_key,
                extract_frames_only=config.get("manual_frame_selection", False)
            )
            
            # 使用返回的缓存ID
            figma_cache_id = figma_result["cache_id"]
        except Exception as e:
            logging.error(f"获取Figma数据失败: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"获取Figma数据失败: {str(e)}")
        
        # 缓存测试观点数据
        viewpoints_cache_id = cache_node_data(viewpoints_data, "viewpoints_data")
        
        # 如果有历史测试用例，缓存它们
        historical_cases_cache_id = None
        if historical_cases:
            historical_cases_cache_id = cache_node_data(historical_cases, "historical_cases")
        
        # 创建会话
        session_id = str(uuid.uuid4())
        session_data = {
            "figma_cache_id": figma_cache_id,
            "viewpoints_cache_id": viewpoints_cache_id,
            "historical_cases_cache_id": historical_cases_cache_id,
            "config": config,
            "status": "initialized",
            "created_at": datetime.now().isoformat()
        }
        
        # 存储会话数据
        redis_manager.set_cache(f"session_{session_id}", session_data, ttl=86400)  # 24小时缓存
        
        # 启动异步工作流处理
        asyncio.create_task(process_workflow(session_id))
        
        return {
            "session_id": session_id,
            "status": "initialized",
            "message": "工作流已启动",
            "cache_ids": {
                "figma_cache_id": figma_cache_id,
                "viewpoints_cache_id": viewpoints_cache_id,
                "historical_cases_cache_id": historical_cases_cache_id
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"启动工作流失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"启动工作流失败: {str(e)}")

@app.get("/api/workflow/status/{session_id}")
async def get_workflow_status(session_id: str):
    """获取工作流状态"""
    try:
        # 获取会话数据
        session_data = redis_manager.get_cache(f"session_{session_id}")
        if not session_data:
            raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
        
        # 提取状态信息
        status = {
            "session_id": session_id,
            "status": session_data.get("status", "unknown"),
            "progress": session_data.get("progress", 0),
            "updated_at": session_data.get("updated_at", ""),
            "created_at": session_data.get("created_at", ""),
            "error": session_data.get("error", None)
        }
        
        return status
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"获取工作流状态失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取工作流状态失败: {str(e)}")

@app.get("/api/workflow/result/{session_id}")
async def get_workflow_result(session_id: str):
    """获取工作流结果"""
    try:
        # 获取会话数据
        session_data = redis_manager.get_cache(f"session_{session_id}")
        if not session_data:
            raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
        
        # 检查工作流是否完成
        if session_data.get("status") != "completed":
            raise HTTPException(status_code=400, detail=f"工作流尚未完成，当前状态: {session_data.get('status', 'unknown')}")
        
        # 获取结果
        result = session_data.get("result", {})
        if not result:
            raise HTTPException(status_code=404, detail="工作流结果不存在")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"获取工作流结果失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取工作流结果失败: {str(e)}")

async def process_workflow(session_id: str):
    """异步处理工作流"""
    try:
        # 获取会话数据
        session_data = redis_manager.get_cache(f"session_{session_id}")
        if not session_data:
            logging.error(f"会话 {session_id} 不存在")
            return
        
        # 更新会话状态
        session_data["status"] = "processing"
        session_data["updated_at"] = datetime.now().isoformat()
        session_data["progress"] = 10
        redis_manager.set_cache(f"session_{session_id}", session_data, ttl=86400)
        
        # 获取缓存数据
        figma_data = redis_manager.get_cache(session_data["figma_cache_id"])
        viewpoints_data = redis_manager.get_cache(session_data["viewpoints_cache_id"])
        
        historical_cases = None
        patterns_result = None
        if session_data.get("historical_cases_cache_id"):
            historical_cases = redis_manager.get_cache(session_data["historical_cases_cache_id"])
        
        # 执行工作流处理
        config = session_data.get("config", {})
        
        # 处理手动选择Frame的情况
        if config.get("manual_frame_selection"):
            # 这里需要等待用户选择Frame
            # 暂时简化处理，假设不需要手动选择
            pass
        
        # 更新进度
        session_data["progress"] = 20
        redis_manager.set_cache(f"session_{session_id}", session_data, ttl=86400)
        
        # 匹配测试观点
        try:
            match_result = match_viewpoints(
                clean_json_cache_id=session_data["figma_cache_id"],
                viewpoints_processed=viewpoints_data
            )
            
            # 更新进度
            session_data["progress"] = 40
            redis_manager.set_cache(f"session_{session_id}", session_data, ttl=86400)
        except Exception as e:
            logging.error(f"匹配测试观点失败: {str(e)}", exc_info=True)
            raise Exception(f"匹配测试观点失败: {str(e)}")
        
        # 推断路由
        try:
            route_result = route_infer(
                clean_json_cache_id=session_data["figma_cache_id"]
            )
            
            # 更新进度
            session_data["progress"] = 50
            redis_manager.set_cache(f"session_{session_id}", session_data, ttl=86400)
        except Exception as e:
            logging.error(f"推断路由失败: {str(e)}", exc_info=True)
            raise Exception(f"推断路由失败: {str(e)}")
        
        # 处理历史测试用例
        if historical_cases:
            try:
                # 提取测试模式
                from nodes.extract_test_patterns import extract_test_patterns
                patterns_result = extract_test_patterns(historical_cases)
                
                # 分析差异
                from nodes.analyze_differences import analyze_differences
                diff_result = analyze_differences(
                    figma_cache_id=session_data["figma_cache_id"],
                    patterns_cache_id=patterns_result["cache_id"]
                )
                
                # 评估覆盖率
                from nodes.evaluate_coverage import evaluate_coverage
                coverage_result = evaluate_coverage(
                    viewpoints_cache_id=session_data["viewpoints_cache_id"],
                    difference_cache_id=diff_result["cache_id"],
                    patterns_cache_id=patterns_result["cache_id"]
                )
                
                # 更新进度
                session_data["progress"] = 60
                redis_manager.set_cache(f"session_{session_id}", session_data, ttl=86400)
            except Exception as e:
                logging.error(f"处理历史测试用例失败: {str(e)}", exc_info=True)
                # 继续执行，不中断流程
                patterns_result = None
        
        # 创建语义关联映射
        try:
            semantic_map_params = {
                "figma_data_cache_id": session_data["figma_cache_id"],
                "viewpoints_cache_id": session_data["viewpoints_cache_id"]
            }
            
            # 如果有历史测试模式，添加到参数中
            if patterns_result and "cache_id" in patterns_result:
                semantic_map_params["historical_patterns_cache_id"] = patterns_result["cache_id"]
            
            semantic_map = create_semantic_correlation_map(**semantic_map_params)
            
            # 更新进度
            session_data["progress"] = 70
            redis_manager.set_cache(f"session_{session_id}", session_data, ttl=86400)
        except Exception as e:
            logging.error(f"创建语义关联映射失败: {str(e)}", exc_info=True)
            raise Exception(f"创建语义关联映射失败: {str(e)}")
        
        # 生成测试用例
        try:
            testcases_result = generate_testcases(
                semantic_correlation_map_cache_id=semantic_map["cache_id"]
            )
            
            # 更新进度
            session_data["progress"] = 80
            redis_manager.set_cache(f"session_{session_id}", session_data, ttl=86400)
        except Exception as e:
            logging.error(f"生成测试用例失败: {str(e)}", exc_info=True)
            raise Exception(f"生成测试用例失败: {str(e)}")
        
        # 生成跨页面测试用例
        try:
            cross_page_result = generate_cross_page_case(
                routes_cache_id=route_result["cache_id"],
                testcases_cache_id=testcases_result["cache_id"]
            )
            
            # 更新进度
            session_data["progress"] = 90
            redis_manager.set_cache(f"session_{session_id}", session_data, ttl=86400)
        except Exception as e:
            logging.error(f"生成跨页面测试用例失败: {str(e)}", exc_info=True)
            raise Exception(f"生成跨页面测试用例失败: {str(e)}")
        
        # 格式化输出
        try:
            # 创建一个虚拟的UploadFile对象
            class MockUploadFile(UploadFile):
                async def read(self):
                    return json.dumps(redis_manager.get_cache(cross_page_result["cache_id"])).encode('utf-8')
            
            mock_file = MockUploadFile(
                filename="testcases.json",
                file=None,
                content_type="application/json"
            )
            
            output_result = await run_node_format_output(
                testcases=mock_file,
                output_format='markdown',
                language='ja'
            )
            
            formatted_output = output_result.get("content", {}).get("formatted_output", "")
            
            # 更新会话状态
            session_data["status"] = "completed"
            session_data["updated_at"] = datetime.now().isoformat()
            session_data["progress"] = 100
            session_data["result"] = {
                "testcases": testcases_result.get("content", {}),
                "cross_page_cases": cross_page_result.get("content", {}),
                "formatted_output": formatted_output
            }
            redis_manager.set_cache(f"session_{session_id}", session_data, ttl=86400)
            
            return session_data["result"]
        except Exception as e:
            logging.error(f"格式化输出失败: {str(e)}", exc_info=True)
            raise Exception(f"格式化输出失败: {str(e)}")
    
    except Exception as e:
        logging.error(f"处理工作流失败: {str(e)}", exc_info=True)
        session_data = redis_manager.get_cache(f"session_{session_id}")
        if session_data:
            session_data["status"] = "failed"
            session_data["error"] = str(e)
            session_data["updated_at"] = datetime.now().isoformat()
            redis_manager.set_cache(f"session_{session_id}", session_data, ttl=86400)
        return None

# 添加辅助函数
def save_temp_upload(upload_file: UploadFile) -> str:
    """将上传的文件保存到临时目录"""
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    try:
        shutil.copyfileobj(upload_file.file, temp_file)
    finally:
        upload_file.file.seek(0)  # 重置文件指针
        temp_file.close()
    return temp_file.name

# 添加缓存节点数据的函数
def cache_node_data(data: Any, prefix: str = "node_data") -> str:
    """缓存节点数据并返回缓存ID"""
    # 生成唯一缓存ID
    cache_id = f"{prefix}_{uuid.uuid4().hex}"
    
    # 将数据缓存到Redis
    redis_manager.set_cache(cache_id, data, ttl=3600)  # 1小时过期
    
    return cache_id

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)