from typing import Dict, Any
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

def generate_cache_key(clean_json: Dict, viewpoints_db: Dict, agent_name: str) -> str:
    """キャッシュキーを生成する"""
    content = {
        "clean_json": clean_json,
        "viewpoints_db": viewpoints_db,
        "agent_name": agent_name
    }
    return hashlib.md5(json.dumps(content, sort_keys=True).encode()).hexdigest()

@cache_llm_call(ttl=3600)  # キャッシュLLM呼び出し結果（1時間）
def match_viewpoints(clean_json: Dict[str, Any], viewpoints_db: Dict[str, Any], 
                     llm_client=None, prompt_template: str = None, few_shot_examples: list = None,
                     agent_name: str = "match_viewpoints") -> Dict[str, Any]:
    """
    コンポーネントをテスト観点にマッチングする
    
    Args:
        clean_json: クリーンなFigmaデータ
        viewpoints_db: テスト観点データベース
        llm_client: LLMクライアント（指定されていない場合は作成）
        prompt_template: カスタムプロンプトテンプレート
        few_shot_examples: Few-shot学習例
        agent_name: エージェント名（設定から読み込むため）
        
    Returns:
        コンポーネントと観点のマッピング
    """
    # キャッシュキーを生成
    cache_key = generate_cache_key(clean_json, viewpoints_db, agent_name)
    
    # キャッシュをチェック
    cached_result = cache_manager.get(cache_key)
    if cached_result is not None:
        return cached_result
    
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
        "components": clean_json,
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