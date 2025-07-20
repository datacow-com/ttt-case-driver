from typing import Dict, Any, List
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

def build_batch_prompt(components: List[Dict], system_prompt: str, few_shot_examples: list) -> str:
    """バッチ処理プロンプトを構築する"""
    prompt = system_prompt + '\n'
    
    # Few-shotの例を追加
    for ex in few_shot_examples:
        prompt += f"Example Input:\n{ex['input']}\nExample Output:\n{ex['output']}\n"
    
    # バッチ入力を追加
    prompt += "Current Input (Batch Processing):\n"
    for i, item in enumerate(components):
        comp = item['component']
        viewpoints = item['viewpoints']
        for j, viewpoint in enumerate(viewpoints):
            prompt += f"Component{i+1}-Viewpoint{j+1}: Type={comp['type']}, Name={comp.get('name', comp.get('id', ''))}, TestViewpoint={viewpoint}\n"
    
    prompt += "\nPlease generate test cases for each component-viewpoint combination, output as JSON array:"
    return prompt

def parse_batch_result(batch_result: str, components: List[Dict]) -> List[Dict[str, Any]]:
    """バッチ結果を解析する"""
    try:
        # JSON結果の解析を試みる
        if isinstance(batch_result, str):
            parsed_results = json.loads(batch_result)
        elif isinstance(batch_result, dict) and "content" in batch_result:
            parsed_results = json.loads(batch_result["content"])
        else:
            parsed_results = batch_result
        
        # 結果をコンポーネントにマッピング
        testcases = []
        result_index = 0
        
        for item in components:
            comp = item['component']
            viewpoints = item['viewpoints']
            
            for viewpoint in viewpoints:
                if result_index < len(parsed_results):
                    testcase = parsed_results[result_index]
                    testcases.append({
                        'component_id': comp.get('id', ''),
                        'component': comp,
                        'viewpoint': viewpoint,
                        'testcase': testcase
                    })
                    result_index += 1
                else:
                    # 結果が不足している場合、デフォルトのテストケースを作成
                    testcases.append({
                        'component_id': comp.get('id', ''),
                        'component': comp,
                        'viewpoint': viewpoint,
                        'testcase': f"Default test case: {viewpoint}"
                    })
        
        return testcases
    except Exception as e:
        # 解析に失敗した場合、個別処理にフォールバック
        return individual_process_components(components, None, None, None, "generate_testcases")

def individual_process_components(components: List[Dict], llm_client=None, prompt_template: str = None, 
                                 few_shot_examples: list = None, agent_name: str = "generate_testcases") -> List[Dict[str, Any]]:
    """コンポーネントを個別に処理する（既存のロジック）"""
    # LLMクライアントを準備
    if llm_client is None:
        llm_client = SmartLLMClient(agent_name)
        
    prompt_manager = PromptManager()
    node_prompt = prompt_manager.get_prompt('generate_testcases')
    system_prompt = prompt_template or node_prompt.get('system_prompt', '')
    few_shot = few_shot_examples or node_prompt.get('few_shot_examples', [])
    
    testcases = []
    for item in components:
        comp = item['component']
        for viewpoint in item['viewpoints']:
            current_input = f"Component: {comp['type']}\nName: {comp.get('name', comp.get('id', ''))}\nTest Viewpoint: {viewpoint}"
            prompt = build_prompt(system_prompt, few_shot, current_input)
            result = llm_client.generate_sync(prompt)
            
            content = result.get("content", "") if isinstance(result, dict) else result
            
            testcases.append({
                'component_id': comp.get('id', ''),
                'component': comp,
                'viewpoint': viewpoint,
                'testcase': content
            })
    return testcases

def generate_cache_key(component_viewpoints: Dict, agent_name: str) -> str:
    """キャッシュキーを生成する"""
    content = {
        "component_viewpoints": component_viewpoints,
        "agent_name": agent_name
    }
    return hashlib.md5(json.dumps(content, sort_keys=True).encode()).hexdigest()

@cache_llm_call(ttl=3600)  # キャッシュLLM呼び出し結果（1時間）
def generate_testcases(component_viewpoints: Dict[str, Any], llm_client=None, 
                      prompt_template: str = None, few_shot_examples: list = None,
                      agent_name: str = "generate_testcases") -> List[Dict[str, Any]]:
    """
    最適化されたテストケース生成、バッチ処理とキャッシュをサポート
    
    Args:
        component_viewpoints: コンポーネントと観点のマッピング
        llm_client: LLMクライアント（指定されていない場合は作成）
        prompt_template: カスタムプロンプトテンプレート
        few_shot_examples: Few-shot学習例
        agent_name: エージェント名（設定から読み込むため）
        
    Returns:
        生成されたテストケースのリスト
    """
    # キャッシュキーを生成
    cache_key = generate_cache_key(component_viewpoints, agent_name)
    
    # キャッシュをチェック
    cached_result = cache_manager.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    # LLMクライアントを準備
    if llm_client is None:
        llm_client = SmartLLMClient(agent_name)
    
    components = component_viewpoints.get('component_viewpoints', [])
    
    # データ量に基づいて処理戦略を選択
    if len(components) > 5:
        # 大量データ：バッチ処理
        result = batch_process_components(components, llm_client, prompt_template, few_shot_examples, agent_name)
    else:
        # 少量データ：個別処理
        result = individual_process_components(components, llm_client, prompt_template, few_shot_examples, agent_name)
    
    # 結果をキャッシュ
    cache_manager.set(cache_key, result, ttl=3600)
    return result

def batch_process_components(components: List[Dict], llm_client=None, prompt_template: str = None, 
                            few_shot_examples: list = None, agent_name: str = "generate_testcases") -> List[Dict[str, Any]]:
    """コンポーネントをバッチ処理し、API呼び出し回数を減らす"""
    # LLMクライアントを準備
    if llm_client is None:
        llm_client = SmartLLMClient(agent_name)
        
    prompt_manager = PromptManager()
    node_prompt = prompt_manager.get_prompt('generate_testcases')
    system_prompt = prompt_template or node_prompt.get('system_prompt', '')
    few_shot = few_shot_examples or node_prompt.get('few_shot_examples', [])
    
    # バッチプロンプトを構築
    batch_prompt = build_batch_prompt(components, system_prompt, few_shot)
    
    # 単一のLLM呼び出しですべてのテストケースを生成
    batch_result = llm_client.generate_sync(batch_prompt)
    
    # バッチ結果を解析
    return parse_batch_result(batch_result, components)