from typing import List, Dict, Any
from utils.enhanced_config_loader import config_loader

class ConfigValidator:
    """設定検証ツール"""
    
    @staticmethod
    def validate_all_configs() -> Dict[str, Any]:
        """すべての設定を検証"""
        errors = []
        warnings = []
        
        # プロバイダー設定を検証
        provider_errors = ConfigValidator.validate_providers()
        errors.extend(provider_errors)
        
        # エージェント設定を検証
        agent_errors, agent_warnings = ConfigValidator.validate_agents()
        errors.extend(agent_errors)
        warnings.extend(agent_warnings)
        
        # 戦略設定を検証
        strategy_errors = ConfigValidator.validate_strategies()
        errors.extend(strategy_errors)
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    @staticmethod
    def validate_providers() -> List[str]:
        """プロバイダー設定を検証"""
        errors = []
        
        for provider_name in config_loader.get_available_providers():
            try:
                provider_config = config_loader.get_provider_config(provider_name)
                
                # APIキーが設定されているか確認
                if not provider_config.api_key and provider_name != "local":
                    errors.append(f"プロバイダー {provider_name} にAPIキーが設定されていません")
                
                # エンドポイントが設定されているか確認
                if not provider_config.endpoint:
                    errors.append(f"プロバイダー {provider_name} にエンドポイントが設定されていません")
                
                # デフォルトモデルが存在するか確認
                if provider_config.default_model not in provider_config.models:
                    errors.append(f"プロバイダー {provider_name} のデフォルトモデル {provider_config.default_model} が定義されていません")
                
                # モデル設定を検証
                for model_name, model_config in provider_config.models.items():
                    if model_config.max_tokens <= 0:
                        errors.append(f"プロバイダー {provider_name} のモデル {model_name} のmax_tokensは正の値である必要があります")
                    
                    if model_config.cost_per_1k_tokens < 0:
                        errors.append(f"プロバイダー {provider_name} のモデル {model_name} のcost_per_1k_tokensは負の値にできません")
                    
                    if not model_config.capabilities:
                        errors.append(f"プロバイダー {provider_name} のモデル {model_name} に機能が定義されていません")
                
            except Exception as e:
                errors.append(f"プロバイダー {provider_name} の設定エラー: {str(e)}")
        
        return errors
    
    @staticmethod
    def validate_agents() -> tuple[List[str], List[str]]:
        """エージェント設定を検証"""
        errors = []
        warnings = []
        
        for agent_name in config_loader.config["llm_agents"].keys():
            try:
                agent_config = config_loader.get_agent_config(agent_name)
                
                # プロバイダーが存在するか確認
                if agent_config.provider not in config_loader.get_available_providers():
                    errors.append(f"エージェント {agent_name} のプロバイダー {agent_config.provider} が定義されていません")
                    continue
                
                provider_config = config_loader.get_provider_config(agent_config.provider)
                
                # モデルが存在するか確認
                if agent_config.model not in provider_config.models:
                    errors.append(f"エージェント {agent_name} のモデル {agent_config.model} がプロバイダー {agent_config.provider} に定義されていません")
                
                # 温度が適切か確認
                if agent_config.temperature < 0 or agent_config.temperature > 1:
                    errors.append(f"エージェント {agent_name} の温度 {agent_config.temperature} は0～1の範囲内である必要があります")
                
                # max_tokensが適切か確認
                model_max_tokens = provider_config.models[agent_config.model].max_tokens if agent_config.model in provider_config.models else 0
                if agent_config.max_tokens > model_max_tokens:
                    warnings.append(f"エージェント {agent_name} のmax_tokens {agent_config.max_tokens} はモデルの上限 {model_max_tokens} を超えています")
                
                # フォールバックプロバイダーが存在するか確認
                for fallback_provider in agent_config.fallback_providers:
                    if fallback_provider not in config_loader.get_available_providers():
                        errors.append(f"エージェント {agent_name} のフォールバックプロバイダー {fallback_provider} が定義されていません")
                
            except Exception as e:
                errors.append(f"エージェント {agent_name} の設定エラー: {str(e)}")
        
        return errors, warnings
    
    @staticmethod
    def validate_strategies() -> List[str]:
        """戦略設定を検証"""
        errors = []
        
        strategy = config_loader.get_llm_strategy()
        
        # コスト最適化戦略を検証
        if "cost_optimization" in strategy:
            cost_opt = strategy["cost_optimization"]
            if cost_opt.get("enabled", False):
                if "max_cost_per_request" in cost_opt and cost_opt["max_cost_per_request"] <= 0:
                    errors.append("コスト最適化戦略のmax_cost_per_requestは正の値である必要があります")
                
                if "preferred_providers" in cost_opt:
                    for provider in cost_opt["preferred_providers"]:
                        if provider not in config_loader.get_available_providers():
                            errors.append(f"コスト最適化戦略の優先プロバイダー {provider} が定義されていません")
        
        # パフォーマンス最適化戦略を検証
        if "performance_optimization" in strategy:
            perf_opt = strategy["performance_optimization"]
            if perf_opt.get("enabled", False):
                if "max_response_time" in perf_opt and perf_opt["max_response_time"] <= 0:
                    errors.append("パフォーマンス最適化戦略のmax_response_timeは正の値である必要があります")
        
        # 負荷分散戦略を検証
        if "load_balancing" in strategy:
            load_bal = strategy["load_balancing"]
            if load_bal.get("enabled", False):
                if "health_check_interval" in load_bal and load_bal["health_check_interval"] <= 0:
                    errors.append("負荷分散戦略のhealth_check_intervalは正の値である必要があります")
        
        return errors
    
    @staticmethod
    def test_provider_connection(provider_name: str) -> Dict[str, Any]:
        """プロバイダー接続をテスト"""
        try:
            provider_config = config_loader.get_provider_config(provider_name)
            model = provider_config.default_model
            
            # ファクトリーをインポート
            from utils.llm_client_factory import LLMClientFactory
            
            # クライアントを作成
            client = LLMClientFactory.create_client(provider_name, model)
            
            # 簡単なプロンプトでテスト
            result = client.generate_sync("This is a test prompt. Please respond with 'OK'.")
            
            return {
                "success": True,
                "provider": provider_name,
                "model": model,
                "response": result.get("content", ""),
                "usage": result.get("usage", {})
            }
            
        except Exception as e:
            return {
                "success": False,
                "provider": provider_name,
                "error": str(e)
            }
    
    @staticmethod
    def test_agent_configuration(agent_name: str) -> Dict[str, Any]:
        """エージェント設定をテスト"""
        try:
            # ファクトリーをインポート
            from utils.llm_client_factory import SmartLLMClient
            
            # スマートクライアントを作成
            client = SmartLLMClient(agent_name)
            
            # 簡単なプロンプトでテスト
            result = client.generate_sync("This is a test prompt. Please respond with 'OK'.")
            
            return {
                "success": True,
                "agent": agent_name,
                "provider_used": result.get("provider", ""),
                "model_used": result.get("model", ""),
                "response": result.get("content", ""),
                "usage": result.get("usage", {})
            }
            
        except Exception as e:
            return {
                "success": False,
                "agent": agent_name,
                "error": str(e)
            } 