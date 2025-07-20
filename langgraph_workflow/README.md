# LangGraph Agent Workflow for Figma Testcase Generation

## Overview

LangGraph Workflow is an automated pipeline for generating structured test cases from Figma design files. It leverages multiple LLM providers (OpenAI, Anthropic, Gemini, etc.) and supports integration with Dify custom workflows. The system is modular, with each node responsible for a specific step in the test case generation process, and exposes a FastAPI-based HTTP API for orchestration.

## Directory Structure

```
langgraph_workflow/
  main.py                # FastAPI entrypoint, exposes HTTP API endpoints for each node
  workflow.py            # Main workflow logic (batch orchestration)
  requirements.txt       # Python dependencies
  Dockerfile             # Containerization for deployment
  config.yaml            # Configurable agent and node parameters
  config.dify-workflow.json # Dify workflow integration config
  prompt_templates.yaml  # Prompt templates and few-shot examples for LLMs
  nodes/                 # Node implementations (each step in the workflow)
    load_page.py             # Parse Figma YAML structure
    match_viewpoints.py      # Match components to test viewpoints
    generate_testcases.py    # Generate component-level test cases via LLM
    route_infer.py           # Infer page routing/flow chains
    generate_cross_page_case.py # Generate cross-page flow test cases
    format_output.py         # Format output (CSV/Markdown/YAML)
    fetch_and_clean_figma_json.py # Fetch and clean Figma JSON via API
  utils/
    config_loader.py     # Load and resolve config with env overrides
    llm_client.py        # LLM API client abstraction (OpenAI, Claude, Gemini, etc.)
    param_utils.py       # File upload helpers
    prompt_loader.py     # Prompt template loader
    db.py                # (Optional) Postgres session/result persistence
  README.md
```

## Quick Start

1. **Build Docker Image**

```bash
cd langgraph_workflow
docker build -t langgraph-workflow .
```

2. **Run the Service**

```bash
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-xxx \
  -e CLAUDE_API_KEY=sk-yyy \
  -e GEMINI_API_KEY=sk-zzz \
  langgraph-workflow
```

3. **API Endpoints**

Each node in the workflow is exposed as an HTTP endpoint. Example endpoints:

- `POST /run_node/fetch_and_clean_figma_json/`  
  - Form: `access_token`, `file_key`  
  - Fetch and clean Figma file JSON via API
- `POST /run_node/match_viewpoints/`  
  - Files: `clean_json`, `viewpoints_db`  
  - Match components to test viewpoints
- `POST /run_node/generate_testcases/`  
  - File: `component_viewpoints`  
  - Optional Form: `provider`, `api_key`, `endpoint`, `temperature`, `prompt_template`, `few_shot_examples`  
  - Generate component-level test cases
- `POST /run_node/route_infer/`  
  - File: `clean_json`  
  - Infer page routing/flow chains
- `POST /run_node/generate_cross_page_case/`  
  - Files: `routes`, `testcases`  
  - Optional Form: `provider`, `api_key`, `endpoint`, `temperature`, `prompt_template`, `few_shot_examples`  
  - Generate cross-page flow test cases
- `POST /run_node/format_output/`  
  - File: `testcases`  
  - Form: `output_format` (csv/md/yaml)  
  - Format output for download or display
- `GET /intermediate/{node_name}`  
  - Retrieve intermediate results by node name

> For batch workflow, see `run_workflow` in `workflow.py` or integrate via Dify using `config.dify-workflow.json`.

## Workflow Description

The workflow consists of the following steps:

1. **Fetch and Clean Figma JSON**: Download and clean the Figma file JSON using API credentials.
2. **Load Page Structure**: Parse the Figma YAML/JSON to extract the page/component structure.
3. **Match Viewpoints**: For each component, match relevant test viewpoints from a provided database.
4. **Generate Test Cases**: Use LLMs to generate structured test cases for each component-viewpoint pair, with support for prompt templates and few-shot examples.
5. **Route Inference**: Analyze the page/component structure to infer navigation and flow chains.
6. **Generate Cross-Page Cases**: Use LLMs to generate end-to-end test cases that span multiple pages/routes.
7. **Format Output**: Output the generated test cases in CSV, Markdown, or YAML format for downstream consumption.

Each step can be invoked independently via API, or orchestrated as a batch via the workflow script or Dify integration.

## Configuration

- All node and agent parameters are configured in `config.yaml`.
- Each node can use a different LLM provider, API key, endpoint, and temperature.
- Output format and custom options (e.g., case ID prefix, language) are configurable.
- Environment variables can override config values (e.g., API keys, storage URLs).

## Persistence & Session Management

- Intermediate results are stored in-memory for API access (`/intermediate/{node_name}`).
- For production, `utils/db.py` provides Postgres-based session and node result persistence:
  - `workflow_sessions`: stores session input/config
  - `node_results`: stores per-node input/output
  - `feedback`: stores user feedback per node/session
- Configure Postgres via `POSTGRES_URL` in environment or `config.yaml`.

## Prompt Templates & Customization

- Prompt templates and few-shot examples are managed in `prompt_templates.yaml`.
- Each node can use its own prompt and example set, supporting easy LLM prompt engineering.
- Extend or override prompts by editing this file or using the `PromptManager` utility.

## Extending the Workflow

- Add new nodes by implementing a Python module in `nodes/` and exposing an API endpoint in `main.py`.
- Integrate new LLM providers by extending `utils/llm_client.py`.
- Customize workflow orchestration in `workflow.py` or via Dify integration.

## Notes

- The default `LLMClient` is a stub; connect it to real LLM APIs for production use.
- Dify integration is supported via `config.dify-workflow.json` for no-code workflow orchestration.
- For advanced use, see each node's Python docstrings and the Dify config for parameter mapping.
