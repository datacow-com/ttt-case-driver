import os
import yaml

def load_config(path="/Users/zhangqinghua/workspace/figma/langgraph_workflow/config.yaml"):
    with open(path, "r") as f:
        config = yaml.safe_load(f)
    # 环境变量覆盖
    def resolve_env(val):
        if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
            return os.environ.get(val[2:-1], "")
        return val
    def walk(d):
        if isinstance(d, dict):
            return {k: walk(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [walk(i) for i in d]
        else:
            return resolve_env(d)
    return walk(config)

def get_agent_config(node_name, config):
    return config["llm_agents"].get(node_name, config["llm_agents"].get("default", {}))
