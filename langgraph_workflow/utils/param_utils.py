import tempfile
import yaml
from typing import Dict, Any

def save_temp_upload(upload_file) -> str:
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(upload_file.file.read())
        return f.name

def parse_yaml_file(file_path: str) -> Dict[str, Any]:
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)
