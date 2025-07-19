# LangGraph Agent Workflow for Figma Testcase Generation

## 目录结构

```
langgraph_workflow/
  main.py                # FastAPI入口，HTTP API
  workflow.py            # 工作流主逻辑
  requirements.txt       # 依赖
  Dockerfile             # 容器化部署
  config.yaml            # 可配置Agent参数
  nodes/                 # 各节点实现
    load_page.py
    match_viewpoints.py
    generate_testcases.py
    route_infer.py
    generate_cross_page_case.py
    format_output.py
  utils/
    config_loader.py     # 配置加载
    llm_client.py        # LLM调用封装
```

## 快速开始

1. 构建镜像
```bash
cd langgraph_workflow
docker build -t langgraph-workflow .
```

2. 运行服务
```bash
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-xxx \
  -e CLAUDE_API_KEY=sk-yyy \
  -e GEMINI_API_KEY=sk-zzz \
  langgraph-workflow
```

3. 调用API
- POST `/run_workflow/`  
  - form-data: `figma_yaml` (file), `viewpoints_yaml` (file), `output_format` (csv/md)

## 配置说明
- 详见 `config.yaml`，每个Agent节点均可独立配置模型、API Key等参数。

## 说明
- LLMClient为占位实现，需对接实际API。
- 支持Dify自定义工作流集成。
