import os
import yaml
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

class ProviderType(Enum):
    """LLMプロバイダータイプ"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    LOCAL = "local"

@dataclass
class ModelConfig:
    """モデル設定データクラス"""
    name: str
    max_tokens: int
    cost_per_1k_tokens: float
    capabilities: List[str]
    endpoint: Optional[str] = None

@dataclass
class ProviderConfig:
    """プロバイダー設定データクラス"""
    name: str
    models: Dict[str, ModelConfig]
    api_key: str
    endpoint: str
    default_model: str

@dataclass
class AgentConfig:
    """エージェント設定データクラス"""
    provider: str
    model: str
    temperature: float
    max_tokens: int
    fallback_providers: List[str]
    custom_params: Dict[str, Any] = None

class EnhancedConfigLoader:
    """強化された設定ローダー - マルチモデル、マルチプロバイダーをサポート"""
    
    def __init__(self, config_path: str = None):
        """初期化"""
        self.config_path = config_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            "config.yaml"
        )
        self.config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """設定ファイルをロード"""
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        # 環境変数を解決
        return self._resolve_env_vars(config)
    
    def _resolve_env_vars(self, config: Any) -> Any:
        """環境変数を解決"""
        if isinstance(config, str) and config.startswith("${") and config.endswith("}"):
            env_var = config[2:-1]
            # デフォルト値があるかチェック
            if ":-" in env_var:
                env_name, default = env_var.split(":-", 1)
                return os.environ.get(env_name, default)
            return os.environ.get(env_var, "")
        elif isinstance(config, dict):
            return {k: self._resolve_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._resolve_env_vars(item) for item in config]
        return config
    
    def _validate_config(self):
        """設定の完全性を検証"""
        required_sections = ["llm_providers", "llm_agents"]
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"設定ファイルに必要なセクションがありません: {section}")
    
    def get_provider_config(self, provider_name: str) -> ProviderConfig:
        """プロバイダー設定を取得"""
        if provider_name not in self.config["llm_providers"]:
            raise ValueError(f"プロバイダー設定が見つかりません: {provider_name}")
        
        provider_data = self.config["llm_providers"][provider_name]
        
        # モデル設定を構築
        models = {}
        for model_name, model_data in provider_data["models"].items():
            models[model_name] = ModelConfig(
                name=model_data["name"],
                max_tokens=model_data["max_tokens"],
                cost_per_1k_tokens=model_data["cost_per_1k_tokens"],
                capabilities=model_data["capabilities"],
                endpoint=model_data.get("endpoint")
            )
        
        return ProviderConfig(
            name=provider_data["name"],
            models=models,
            api_key=provider_data["api_key"],
            endpoint=provider_data["endpoint"],
            default_model=provider_data["default_model"]
        )
    
    def get_agent_config(self, agent_name: str) -> AgentConfig:
        """エージェント設定を取得"""
        if agent_name not in self.config["llm_agents"]:
            raise ValueError(f"エージェント設定が見つかりません: {agent_name}")
        
        agent_data = self.config["llm_agents"][agent_name]
        
        return AgentConfig(
            provider=agent_data["provider"],
            model=agent_data["model"],
            temperature=agent_data["temperature"],
            max_tokens=agent_data["max_tokens"],
            fallback_providers=agent_data.get("fallback_providers", []),
            custom_params=agent_data.get("custom_params", {})
        )
    
    def get_llm_strategy(self) -> Dict[str, Any]:
        """LLM戦略設定を取得"""
        return self.config.get("llm_strategy", {})
    
    def get_available_providers(self) -> List[str]:
        """利用可能なプロバイダーリストを取得"""
        return list(self.config["llm_providers"].keys())
    
    def get_available_models(self, provider: str = None) -> Dict[str, List[str]]:
        """利用可能なモデルリストを取得"""
        if provider:
            provider_config = self.get_provider_config(provider)
            return {provider: list(provider_config.models.keys())}
        
        models = {}
        for provider_name in self.get_available_providers():
            provider_config = self.get_provider_config(provider_name)
            models[provider_name] = list(provider_config.models.keys())
        
        return models
    
    def validate_agent_config(self, agent_name: str) -> bool:
        """エージェント設定の有効性を検証"""
        try:
            agent_config = self.get_agent_config(agent_name)
            provider_config = self.get_provider_config(agent_config.provider)
            
            # モデルが存在するか確認
            if agent_config.model not in provider_config.models:
                return False
            
            # APIキーが設定されているか確認
            if not provider_config.api_key:
                return False
            
            return True
        except Exception:
            return False
    
    def reload_config(self):
        """設定を再ロード"""
        self.config = self._load_config()
        self._validate_config()
        return self.config

# グローバル設定ローダーインスタンス
config_loader = EnhancedConfigLoader() 