from typing import Dict, Any
import yaml

def load_page(yaml_file_path: str) -> Dict[str, Any]:
    """
    解析页面结构YAML，返回页面结构对象
    """
    with open(yaml_file_path, 'r', encoding='utf-8') as f:
        page_structure = yaml.safe_load(f)
    return page_structure
