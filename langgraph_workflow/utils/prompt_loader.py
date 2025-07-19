import yaml
from typing import Dict, Any, Optional
import os

PROMPT_TEMPLATE_PATH = os.environ.get("PROMPT_TEMPLATE_PATH", "prompt_templates.yaml")

class PromptManager:
    def __init__(self, path: Optional[str] = None):
        self.path = path or PROMPT_TEMPLATE_PATH
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, Any]:
        with open(self.path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def get_prompt(self, node: str, version: str = None) -> Dict[str, Any]:
        # 版本管理可扩展，当前只支持单版本
        return self.templates.get(node, {})

    def list_versions(self, node: str) -> list:
        # 预留多版本支持
        return ["default"]
