# Web与Dify集成指南

本文档说明如何将Web应用与Dify/LangGraph工作流集成，实现测试用例自动生成功能。

## 1. 功能划分

### 1.1 Web端职责

- 文件上传与管理
- 文件解析与预处理（Figma、测试观点、历史测试用例）
- 用户交互界面
- 结果展示与导出

### 1.2 Dify/LangGraph职责

- AI推理与测试用例生成
- 工作流编排与执行
- 测试覆盖率分析
- 跨页面测试场景生成

## 2. 集成流程

### 2.1 Web端实现

1. **实现文件上传与解析**
   - 上传Figma设计文件
   - 上传测试观点文件（支持JSON/CSV/Excel格式）
   - 上传历史测试用例文件（可选，支持多文件）

2. **实现文件预处理**
   - 解析Figma文件，提取页面、Frame和组件信息
   - 解析测试观点文件，标准化格式
   - 解析历史测试用例文件，标准化格式

3. **调用Dify API**
   - 调用`/api/workflow/start`启动工作流
   - 轮询`/api/workflow/status/{session_id}`获取工作流状态
   - 获取`/api/workflow/result/{session_id}`获取工作流结果

### 2.2 Dify端配置

1. **导入工作流配置**
   - 使用`config.dify-workflow.json`配置工作流

2. **配置节点参数**
   - 配置API端点和参数

## 3. API接口说明

### 3.1 启动工作流

```
POST /api/workflow/start
```

**请求体**:

```json
{
  "figma_data": {
    "access_token": "your_figma_access_token",
    "file_key": "your_figma_file_key"
  },
  "viewpoints_data": {
    "button": [
      {
        "id": "1",
        "category": "機能性",
        "item": "正常系",
        "description": "入力→送信→遷移動作の確認",
        "example": "登録ボタン押下後、確認画面へ遷移するか",
        "target_page": "/entry",
        "target_component": "登録ボタン",
        "design_link": "figma_url",
        "priority": "HIGH"
      }
    ],
    "input": [
      // ...
    ]
  },
  "historical_cases": {
    "cases": [
      {
        "id": "TC001",
        "title": "ログインボタン押下時の画面遷移確認",
        "description": "ログインボタンを押下した際に正しく遷移することを確認する",
        "preconditions": "必須項目がすべて入力されている状態",
        "steps": [
          {
            "step_number": 1,
            "action": "ログインボタンを押下する",
            "expected_result": "ホーム画面へ遷移する"
          }
        ],
        "expected_results": ["ホーム画面が表示される"],
        "target_component": "ログインボタン",
        "target_page": "/login",
        "priority": "HIGH",
        "tags": ["正常系", "画面遷移"]
      }
    ]
  },
  "config": {
    "manual_frame_selection": false,
    "enable_priority_evaluation": true,
    "enable_classification": true,
    "output_format": "markdown",
    "language": "ja"
  }
}
```

**响应**:

```json
{
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "initialized",
  "message": "工作流已启动",
  "cache_ids": {
    "figma_cache_id": "figma_data_abc123",
    "viewpoints_cache_id": "viewpoints_data_def456",
    "historical_cases_cache_id": "historical_cases_ghi789"
  }
}
```

### 3.2 获取工作流状态

```
GET /api/workflow/status/{session_id}
```

**响应**:

```json
{
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "processing",
  "progress": 65,
  "created_at": "2023-06-15T10:30:00Z",
  "updated_at": "2023-06-15T10:35:00Z"
}
```

### 3.3 获取工作流结果

```
GET /api/workflow/result/{session_id}
```

**响应**:

```json
{
  "testcases": {
    "testcases": [
      {
        "id": "TC001",
        "title": "ログインボタン押下時の画面遷移確認",
        "description": "ログインボタンを押下した際に正しく遷移することを確認する",
        "preconditions": "必須項目がすべて入力されている状態",
        "steps": [
          {
            "step_number": 1,
            "action": "ログインボタンを押下する",
            "expected_result": "ホーム画面へ遷移する"
          }
        ],
        "expected_results": ["ホーム画面が表示される"],
        "target_component": "ログインボタン",
        "target_page": "/login",
        "priority": "HIGH",
        "tags": ["正常系", "画面遷移"]
      }
    ]
  },
  "formatted_output": "# 测试用例\n\n## 登录页面\n...",
  "metadata": {
    "generated_at": "2023-06-15T10:40:00Z",
    "testcases_count": 120,
    "has_historical_analysis": true
  }
}
```

## 4. 实现示例

### 4.1 Web端调用示例（Python）

```python
import requests
import json

# 准备数据
with open('figma_token.txt', 'r') as f:
    figma_token = f.read().strip()

with open('viewpoints.json', 'r') as f:
    viewpoints_data = json.load(f)

with open('historical_cases.json', 'r') as f:
    historical_cases = json.load(f)

# 构建请求体
payload = {
    "figma_data": {
        "access_token": figma_token,
        "file_key": "your_figma_file_key"
    },
    "viewpoints_data": viewpoints_data,
    "historical_cases": historical_cases,
    "config": {
        "manual_frame_selection": False,
        "enable_priority_evaluation": True,
        "enable_classification": True,
        "output_format": "markdown",
        "language": "ja"
    }
}

# 启动工作流
response = requests.post(
    "http://localhost:8000/api/workflow/start",
    json=payload
)
result = response.json()
session_id = result["session_id"]

# 轮询工作流状态
import time
while True:
    status_response = requests.get(
        f"http://localhost:8000/api/workflow/status/{session_id}"
    )
    status = status_response.json()
    
    print(f"Status: {status['status']}, Progress: {status.get('progress', 0)}%")
    
    if status["status"] == "completed":
        break
    elif status["status"] == "failed":
        print(f"Error: {status.get('error', 'Unknown error')}")
        break
    
    time.sleep(5)

# 获取工作流结果
if status["status"] == "completed":
    result_response = requests.get(
        f"http://localhost:8000/api/workflow/result/{session_id}"
    )
    result = result_response.json()
    
    # 保存格式化输出
    with open("testcases.md", "w") as f:
        f.write(result["formatted_output"])
    
    print(f"Generated {result['metadata']['testcases_count']} test cases")
```

### 4.2 Web端调用示例（JavaScript）

```javascript
async function generateTestCases() {
  // 准备数据
  const figmaToken = document.getElementById('figma-token').value;
  const figmaFileKey = document.getElementById('figma-file-key').value;
  const viewpointsData = JSON.parse(document.getElementById('viewpoints-data').value);
  const historicalCases = JSON.parse(document.getElementById('historical-cases').value);
  
  // 构建请求体
  const payload = {
    figma_data: {
      access_token: figmaToken,
      file_key: figmaFileKey
    },
    viewpoints_data: viewpointsData,
    historical_cases: historicalCases,
    config: {
      manual_frame_selection: false,
      enable_priority_evaluation: true,
      enable_classification: true,
      output_format: 'markdown',
      language: 'ja'
    }
  };
  
  // 启动工作流
  const response = await fetch('http://localhost:8000/api/workflow/start', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
  
  const result = await response.json();
  const sessionId = result.session_id;
  
  // 显示进度
  const progressElement = document.getElementById('progress');
  progressElement.style.display = 'block';
  
  // 轮询工作流状态
  let status;
  do {
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    const statusResponse = await fetch(`http://localhost:8000/api/workflow/status/${sessionId}`);
    status = await statusResponse.json();
    
    progressElement.innerText = `Status: ${status.status}, Progress: ${status.progress || 0}%`;
    
  } while (status.status === 'processing' || status.status === 'initialized');
  
  // 获取工作流结果
  if (status.status === 'completed') {
    const resultResponse = await fetch(`http://localhost:8000/api/workflow/result/${sessionId}`);
    const result = await resultResponse.json();
    
    // 显示结果
    document.getElementById('result').innerHTML = result.formatted_output;
    document.getElementById('metadata').innerText = 
      `Generated ${result.metadata.testcases_count} test cases at ${result.metadata.generated_at}`;
  } else {
    document.getElementById('result').innerText = `Error: ${status.error || 'Unknown error'}`;
  }
}
```

## 5. 注意事项

1. **安全性**
   - 不要在前端暴露Figma访问令牌
   - 使用HTTPS进行API调用
   - 实现适当的身份验证和授权机制

2. **性能优化**
   - 大型Figma文件可能需要较长处理时间
   - 实现适当的超时和重试机制
   - 考虑使用WebSocket代替轮询获取状态更新

3. **错误处理**
   - 实现全面的错误处理和日志记录
   - 向用户提供有意义的错误消息
   - 提供重试或恢复机制
