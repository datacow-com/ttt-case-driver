import time
import openai
import anthropic
import google.generativeai as genai
from typing import Dict, Any, Optional
from utils.performance_monitor import performance_monitor

class LLMClient:
    def __init__(self, provider: str = "gpt-4o", api_key: str = None, endpoint: str = None, temperature: float = 0.2, max_tokens: int = None):
        self.provider = provider
        self.api_key = api_key
        self.endpoint = endpoint
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # 初始化客户端
        self._init_client()
    
    def _init_client(self):
        """初始化LLM客户端"""
        if self.provider.startswith("gpt"):
            # OpenAI
            if self.endpoint:
                openai.api_base = self.endpoint
            openai.api_key = self.api_key
        elif self.provider.startswith("claude"):
            # Anthropic
            self.anthropic_client = anthropic.Anthropic(api_key=self.api_key)
        elif self.provider.startswith("gemini"):
            # Google Gemini
            genai.configure(api_key=self.api_key)
    
    def generate(self, prompt: str, model: str = None) -> Dict[str, Any]:
        """生成LLM响应（带性能监控）"""
        start_time = time.time()
        success = True
        
        try:
            if not model:
                model = self.provider
            
            if model.startswith("gpt"):
                result = self._call_openai(prompt, model)
            elif model.startswith("claude"):
                result = self._call_anthropic(prompt, model)
            elif model.startswith("gemini"):
                result = self._call_gemini(prompt, model)
            else:
                # 默认模拟响应
                result = {'steps': f'【模拟】{prompt}', 'expected': '【模拟】预期结果'}
            
            # 计算响应时间
            response_time = time.time() - start_time
            
            # 估算TOKEN使用量（简化估算）
            estimated_tokens = len(prompt.split()) * 1.3  # 粗略估算
            
            # 记录性能统计
            performance_monitor.record_llm_call(
                model=model,
                tokens_used=int(estimated_tokens),
                response_time=response_time,
                success=success
            )
            
            return result
            
        except Exception as e:
            success = False
            response_time = time.time() - start_time
            
            # 记录错误
            performance_monitor.record_llm_call(
                model=model or self.provider,
                tokens_used=0,
                response_time=response_time,
                success=success
            )
            
            raise e
    
    def _call_openai(self, prompt: str, model: str) -> Dict[str, Any]:
        """调用OpenAI API"""
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一个专业的测试用例生成助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            content = response.choices[0].message.content
            return {'steps': content, 'expected': '成功生成测试用例'}
            
        except Exception as e:
            raise Exception(f"OpenAI API调用失败: {str(e)}")
    
    def _call_anthropic(self, prompt: str, model: str) -> Dict[str, Any]:
        """调用Anthropic API"""
        try:
            response = self.anthropic_client.messages.create(
                model=model,
                max_tokens=self.max_tokens or 1000,
                temperature=self.temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            content = response.content[0].text
            return {'steps': content, 'expected': '成功生成测试用例'}
            
        except Exception as e:
            raise Exception(f"Anthropic API调用失败: {str(e)}")
    
    def _call_gemini(self, prompt: str, model: str) -> Dict[str, Any]:
        """调用Google Gemini API"""
        try:
            model_instance = genai.GenerativeModel(model)
            response = model_instance.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens
                )
            )
            
            content = response.text
            return {'steps': content, 'expected': '成功生成测试用例'}
            
        except Exception as e:
            raise Exception(f"Gemini API调用失败: {str(e)}")
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """获取使用统计"""
        return performance_monitor.get_token_usage_stats()
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return performance_monitor.get_performance_stats()