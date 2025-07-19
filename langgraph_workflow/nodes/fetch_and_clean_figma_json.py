import requests
from typing import Any, Dict, Set
from fastapi import HTTPException

def fetch_figma_json(access_token: str, file_key: str) -> Dict[str, Any]:
    url = f"https://api.figma.com/v1/files/{file_key}"
    headers = {"X-Figma-Token": access_token}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Figma API error: {resp.text}")
    return resp.json()

def clean_figma_json(figma_json: Dict[str, Any], keep_types: Set[str] = None) -> Dict[str, Any]:
    if keep_types is None:
        keep_types = {"FRAME", "COMPONENT", "INSTANCE", "BUTTON", "TEXT", "RECTANGLE", "GROUP"}
    def filter_node(node):
        if node.get("type") not in keep_types:
            return None
        filtered = {k: v for k, v in node.items() if k in ("id", "name", "type", "children", "characters", "componentId", "text", "absoluteBoundingBox", "interaction")}
        if "children" in filtered:
            filtered["children"] = [c for c in (filter_node(child) for child in node.get("children", [])) if c]
        return filtered
    doc = figma_json.get("document", {})
    cleaned = filter_node(doc)
    return cleaned

def fetch_and_clean_figma_json(access_token: str, file_key: str) -> Dict[str, Any]:
    raw_json = fetch_figma_json(access_token, file_key)
    cleaned = clean_figma_json(raw_json)
    return cleaned
