from typing import Dict, Any, List, Optional
from utils.prompt_loader import PromptManager
from utils.cache_manager import cache_llm_call, cache_manager
from utils.llm_client_factory import SmartLLMClient
import hashlib
import json

def build_prompt(system_prompt: str, few_shot_examples: list, current_input: str) -> str:
    """プロンプトを構築する"""
    prompt = system_prompt + '\n'
    for ex in few_shot_examples:
        prompt += f"Example Input:\n{ex['input']}\nExample Output:\n{ex['output']}\n"
    prompt += f"Current Input:\n{current_input}\nOutput:"
    return prompt

def generate_cache_key(clean_json: Dict, viewpoints_db: Dict, agent_name: str, selected_frames: Optional[List[str]] = None) -> str:
    """キャッシュキーを生成する"""
    content = {
        "clean_json": clean_json,
        "viewpoints_db": viewpoints_db,
        "agent_name": agent_name,
        "selected_frames": selected_frames
    }
    return hashlib.md5(json.dumps(content, sort_keys=True).encode()).hexdigest()

@cache_llm_call(ttl=3600)  # キャッシュLLM呼び出し結果（1時間）
def match_viewpoints(clean_json: Dict[str, Any], viewpoints_db: Dict[str, Any], 
                     llm_client=None, prompt_template: str = None, few_shot_examples: list = None,
                     agent_name: str = "match_viewpoints", selected_frames: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    コンポーネントをテスト観点にマッチングする
    
    Args:
        clean_json: クリーンなFigmaデータ
        viewpoints_db: テスト観点データベース
        llm_client: LLMクライアント（指定されていない場合は作成）
        prompt_template: カスタムプロンプトテンプレート
        few_shot_examples: Few-shot学習例
        agent_name: エージェント名（設定から読み込むため）
        selected_frames: 选定的Frame ID列表（可选）
        
    Returns:
        コンポーネントと観点のマッピング
    """
    # キャッシュキーを生成
    cache_key = generate_cache_key(clean_json, viewpoints_db, agent_name, selected_frames)
    
    # キャッシュをチェック
    cached_result = cache_manager.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    # 如果指定了选定的Frame，过滤组件
    if selected_frames and "components" in clean_json:
        filtered_json = filter_by_selected_frames(clean_json, selected_frames)
    else:
        filtered_json = clean_json
    
    # LLMクライアントを準備
    if llm_client is None:
        llm_client = SmartLLMClient(agent_name)
    
    # プロンプトマネージャーからテンプレートを取得
    prompt_manager = PromptManager()
    node_prompt = prompt_manager.get_prompt('match_viewpoints')
    system_prompt = prompt_template or node_prompt.get('system_prompt', '')
    few_shot = few_shot_examples or node_prompt.get('few_shot_examples', [])
    
    # 入力データを準備
    current_input = json.dumps({
        "components": filtered_json,
        "viewpoints": viewpoints_db
    }, ensure_ascii=False)
    
    # プロンプトを構築
    prompt = build_prompt(system_prompt, few_shot, current_input)
    
    # LLMを呼び出し
    result = llm_client.generate_sync(prompt)
    
    # 結果を解析
    try:
        if isinstance(result, dict) and "content" in result:
            content = result["content"]
            parsed_result = json.loads(content)
        else:
            parsed_result = json.loads(result)
    except Exception:
        # JSONとして解析できない場合は生のテキストを返す
        parsed_result = {"raw_result": result if isinstance(result, str) else str(result)}
    
    # 結果をキャッシュ
    cache_manager.set(cache_key, parsed_result, ttl=3600)
    
    return parsed_result

def filter_by_selected_frames(figma_data: Dict[str, Any], selected_frames: List[str]) -> Dict[str, Any]:
    """根据选定的Frame过滤组件"""
    if not selected_frames or "components" not in figma_data:
        return figma_data
    
    # 复制原始数据
    filtered_data = figma_data.copy()
    
    # 如果数据中有frames字段，过滤frames
    if "frames" in filtered_data:
        filtered_data["frames"] = [
            frame for frame in filtered_data["frames"] 
            if frame.get("id") in selected_frames
        ]
    
    # 如果有relationships字段，保持不变
    # 这里我们不过滤relationships，因为可能会破坏组件间的关系
    
    # 如果有components字段，过滤components
    # 注意：这里我们保留所有组件，因为测试观点匹配需要所有组件信息
    # 实际上，我们在后续处理中会根据Frame过滤组件
    
    return filtered_data