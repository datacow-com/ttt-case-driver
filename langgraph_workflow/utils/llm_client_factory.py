from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
import asyncio
import aiohttp
import json
import time
from utils.enhanced_config_loader import config_loader, AgentConfig, ProviderConfig
from utils.performance_monitor import performance_monitor

class BaseLLMClient(ABC):
    """LLMクライアント基底クラス"""
    
    def __init__(self, provider_config: ProviderConfig, model: str):
        self.provider_config = provider_config
        self.model = model
        self.model_config = provider_config.models[model]
    
    @abstractmethod
    async def generate_async(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """非同期テキスト生成"""
        pass
    
    @abstractmethod
    def generate_sync(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """同期テキスト生成"""
        pass
    
    def estimate_cost(self, tokens: int) -> float:
        """コスト見積もり"""
        return (tokens / 1000) * self.model_config.cost_per_1k_tokens
    
    def estimate_tokens(self, text: str) -> int:
        """トークン数の見積もり"""
        # 簡易見積もり：1単語あたり約1.3トークン
        return int(len(text.split()) * 1.3)

class OpenAIClient(BaseLLMClient):
    """OpenAIクライアント"""
    
    def __init__(self, provider_config: ProviderConfig, model: str):
        super().__init__(provider_config, model)
        self.api_key = provider_config.api_key
        self.endpoint = provider_config.endpoint
    
    async def generate_async(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """非同期OpenAI呼び出し"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.2),
            "max_tokens": kwargs.get("max_tokens", self.model_config.max_tokens)
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.endpoint}/chat/completions",
                headers=headers,
                json=data
            ) as response:
                result = await response.json()
                if response.status != 200:
                    raise Exception(f"OpenAI APIエラー: {result}")
                
                return {
                    "content": result["choices"][0]["message"]["content"],
                    "usage": result["usage"],
                    "model": self.model,
                    "provider": "openai"
                }
    
    def generate_sync(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """同期OpenAI呼び出し"""
        import openai
        openai.api_key = self.api_key
        openai.api_base = self.endpoint
        
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.2),
            max_tokens=kwargs.get("max_tokens", self.model_config.max_tokens)
        )
        
        return {
            "content": response.choices[0].message.content,
            "usage": response.usage,
            "model": self.model,
            "provider": "openai"
        }

class AnthropicClient(BaseLLMClient):
    """Anthropicクライアント"""
    
    def __init__(self, provider_config: ProviderConfig, model: str):
        super().__init__(provider_config, model)
        self.api_key = provider_config.api_key
        self.endpoint = provider_config.endpoint
    
    async def generate_async(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """非同期Anthropic呼び出し"""
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        data = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", self.model_config.max_tokens),
            "temperature": kwargs.get("temperature", 0.2),
            "messages": [{"role": "user", "content": prompt}]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.endpoint}/v1/messages",
                headers=headers,
                json=data
            ) as response:
                result = await response.json()
                if response.status != 200:
                    raise Exception(f"Anthropic APIエラー: {result}")
                
                return {
                    "content": result["content"][0]["text"],
                    "usage": result.get("usage", {}),
                    "model": self.model,
                    "provider": "anthropic"
                }
    
    def generate_sync(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """同期Anthropic呼び出し"""
        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)
        
        response = client.messages.create(
            model=self.model,
            max_tokens=kwargs.get("max_tokens", self.model_config.max_tokens),
            temperature=kwargs.get("temperature", 0.2),
            messages=[{"role": "user", "content": prompt}]
        )
        
        return {
            "content": response.content[0].text,
            "usage": response.usage,
            "model": self.model,
            "provider": "anthropic"
        }

class GoogleClient(BaseLLMClient):
    """Google Geminiクライアント"""
    
    def __init__(self, provider_config: ProviderConfig, model: str):
        super().__init__(provider_config, model)
        self.api_key = provider_config.api_key
        self.endpoint = provider_config.endpoint
    
    async def generate_async(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """非同期Google呼び出し"""
        url = f"{self.endpoint}/v1beta/models/{self.model}:generateContent"
        params = {"key": self.api_key}
        
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": kwargs.get("temperature", 0.2),
                "maxOutputTokens": kwargs.get("max_tokens", self.model_config.max_tokens)
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, params=params, json=data) as response:
                result = await response.json()
                if response.status != 200:
                    raise Exception(f"Google APIエラー: {result}")
                
                return {
                    "content": result["candidates"][0]["content"]["parts"][0]["text"],
                    "usage": result.get("usageMetadata", {}),
                    "model": self.model,
                    "provider": "google"
                }
    
    def generate_sync(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """同期Google呼び出し"""
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        
        model_instance = genai.GenerativeModel(self.model)
        response = model_instance.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=kwargs.get("temperature", 0.2),
                max_output_tokens=kwargs.get("max_tokens", self.model_config.max_tokens)
            )
        )
        
        return {
            "content": response.text,
            "usage": {},
            "model": self.model,
            "provider": "google"
        }

class LocalClient(BaseLLMClient):
    """ローカルモデルクライアント"""
    
    def __init__(self, provider_config: ProviderConfig, model: str):
        super().__init__(provider_config, model)
        self.endpoint = self.model_config.endpoint or "http://localhost:11434"
    
    async def generate_async(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """非同期ローカルモデル呼び出し"""
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.2),
                "num_predict": kwargs.get("max_tokens", self.model_config.max_tokens)
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.endpoint}/api/generate", json=data) as response:
                result = await response.json()
                if response.status != 200:
                    raise Exception(f"ローカルモデルAPIエラー: {result}")
                
                return {
                    "content": result["response"],
                    "usage": {"total_tokens": result.get("eval_count", 0)},
                    "model": self.model,
                    "provider": "local"
                }
    
    def generate_sync(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """同期ローカルモデル呼び出し"""
        import requests
        
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.2),
                "num_predict": kwargs.get("max_tokens", self.model_config.max_tokens)
            }
        }
        
        response = requests.post(f"{self.endpoint}/api/generate", json=data)
        if response.status_code != 200:
            raise Exception(f"ローカルモデルAPIエラー: {response.text}")
        
        result = response.json()
        return {
            "content": result["response"],
            "usage": {"total_tokens": result.get("eval_count", 0)},
            "model": self.model,
            "provider": "local"
        }

class LLMClientFactory:
    """LLMクライアントファクトリー"""
    
    _clients = {
        "openai": OpenAIClient,
        "anthropic": AnthropicClient,
        "google": GoogleClient,
        "local": LocalClient
    }
    
    @classmethod
    def create_client(cls, provider: str, model: str) -> BaseLLMClient:
        """LLMクライアントを作成"""
        if provider not in cls._clients:
            raise ValueError(f"サポートされていないプロバイダー: {provider}")
        
        provider_config = config_loader.get_provider_config(provider)
        client_class = cls._clients[provider]
        return client_class(provider_config, model)
    
    @classmethod
    def create_agent_client(cls, agent_name: str) -> BaseLLMClient:
        """エージェント設定に基づいてクライアントを作成"""
        agent_config = config_loader.get_agent_config(agent_name)
        return cls.create_client(agent_config.provider, agent_config.model)

class SmartLLMClient:
    """スマートLLMクライアント - 自動フォールバックと負荷分散をサポート"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.agent_config = config_loader.get_agent_config(agent_name)
        self.strategy = config_loader.get_llm_strategy()
        self._clients = {}
        self._init_clients()
    
    def _init_clients(self):
        """利用可能なすべてのクライアントを初期化"""
        # メインクライアント
        self._clients[self.agent_config.provider] = LLMClientFactory.create_client(
            self.agent_config.provider, 
            self.agent_config.model
        )
        
        # フォールバッククライアント
        for fallback_provider in self.agent_config.fallback_providers:
            if fallback_provider not in self._clients:
                provider_config = config_loader.get_provider_config(fallback_provider)
                self._clients[fallback_provider] = LLMClientFactory.create_client(
                    fallback_provider,
                    provider_config.default_model
                )
    
    async def generate_async(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """スマート非同期生成"""
        start_time = time.time()
        
        # メインクライアントを試す
        try:
            result = await self._clients[self.agent_config.provider].generate_async(
                prompt, **kwargs
            )
            
            # パフォーマンス統計を記録
            response_time = time.time() - start_time
            performance_monitor.record_llm_call(
                model=self.agent_config.model,
                tokens_used=result.get("usage", {}).get("total_tokens", 0),
                response_time=response_time,
                success=True
            )
            
            return result
            
        except Exception as e:
            # メインクライアントが失敗した場合、フォールバックを試す
            for fallback_provider in self.agent_config.fallback_providers:
                try:
                    result = await self._clients[fallback_provider].generate_async(
                        prompt, **kwargs
                    )
                    
                    # フォールバック統計を記録
                    response_time = time.time() - start_time
                    performance_monitor.record_llm_call(
                        model=f"{fallback_provider}-fallback",
                        tokens_used=result.get("usage", {}).get("total_tokens", 0),
                        response_time=response_time,
                        success=True
                    )
                    
                    return result
                    
                except Exception:
                    continue
            
            # すべてのクライアントが失敗
            response_time = time.time() - start_time
            performance_monitor.record_llm_call(
                model=self.agent_config.model,
                tokens_used=0,
                response_time=response_time,
                success=False
            )
            
            raise Exception(f"すべてのLLMプロバイダーが失敗しました: {str(e)}")
    
    def generate_sync(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """スマート同期生成"""
        start_time = time.time()
        
        # メインクライアントを試す
        try:
            result = self._clients[self.agent_config.provider].generate_sync(
                prompt, **kwargs
            )
            
            # パフォーマンス統計を記録
            response_time = time.time() - start_time
            performance_monitor.record_llm_call(
                model=self.agent_config.model,
                tokens_used=result.get("usage", {}).get("total_tokens", 0),
                response_time=response_time,
                success=True
            )
            
            return result
            
        except Exception as e:
            # メインクライアントが失敗した場合、フォールバックを試す
            for fallback_provider in self.agent_config.fallback_providers:
                try:
                    result = self._clients[fallback_provider].generate_sync(
                        prompt, **kwargs
                    )
                    
                    # フォールバック統計を記録
                    response_time = time.time() - start_time
                    performance_monitor.record_llm_call(
                        model=f"{fallback_provider}-fallback",
                        tokens_used=result.get("usage", {}).get("total_tokens", 0),
                        response_time=response_time,
                        success=True
                    )
                    
                    return result
                    
                except Exception:
                    continue
            
            # すべてのクライアントが失敗
            response_time = time.time() - start_time
            performance_monitor.record_llm_call(
                model=self.agent_config.model,
                tokens_used=0,
                response_time=response_time,
                success=False
            )
            
            raise Exception(f"すべてのLLMプロバイダーが失敗しました: {str(e)}")
            
    def get_usage_stats(self) -> Dict[str, Any]:
        """使用統計を取得"""
        return performance_monitor.get_token_usage_stats()
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """パフォーマンス統計を取得"""
        return performance_monitor.get_performance_stats() 