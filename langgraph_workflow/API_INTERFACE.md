# Web与Dify接口标准

本文档描述了Web应用与Dify/LangGraph之间的接口标准，明确定义了数据交换格式和API调用方式。

## 1. 功能分割

### 1.1 Web端职责

- 文件上传与管理
- 文件解析与预处理
- 用户交互界面
- 结果展示与导出

### 1.2 Dify/LangGraph职责

- AI推理与测试用例生成
- 工作流编排与执行
- 测试覆盖率分析
- 跨页面测试场景生成

## 2. API接口

### 2.1 工作流管理

#### 启动工作流

```
POST /api/workflow/start
```

**请求体**:

```json
{
  "figma_data": {
    "pages": [...],
    "frames": [...],
    "components": [...],
    "component_categories": {...},
    "relationships": {...}
  },
  "viewpoints_data": {
    "button": [...],
    "input": [...],
    ...
  },
  "historical_cases": {
    "cases": [...],
    "stats": {...}
  },
  "config": {
    "manual_frame_selection": false,
    "enable_priority_evaluation": true,
    "enable_classification": true
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

#### 获取工作流状态

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

#### 获取工作流结果

```
GET /api/workflow/result/{session_id}
```

**响应**:

```json
{
  "testcases": [...],
  "formatted_output": "# 测试用例\n\n## 登录页面\n...",
  "metadata": {
    "generated_at": "2023-06-15T10:40:00Z",
    "testcases_count": 120,
    "has_historical_analysis": true
  }
}
```

## 3. 数据格式标准

### 3.1 Figma数据格式

```json
{
  "pages": [
    {
      "id": "page_123",
      "name": "登录页面",
      "type": "PAGE",
      "children_count": 15
    }
  ],
  "frames": [
    {
      "id": "frame_456",
      "name": "登录表单",
      "type": "FRAME",
      "path": "登录页面/登录表单",
      "page_id": "page_123",
      "children_count": 8,
      "has_interactive": true
    }
  ],
  "components": [
    {
      "id": "comp_789",
      "name": "登录按钮",
      "type": "BUTTON",
      "path": "登录页面/登录表单/登录按钮",
      "parent_id": "frame_456",
      "frame_id": "frame_456",
      "page_id": "page_123",
      "properties": {
        "text": "登录",
        "interactions": [{"type": "CLICK", "action": "NAVIGATE"}]
      }
    }
  ],
  "component_categories": {
    "BUTTON": ["comp_789"],
    "INTERACTIVE": ["comp_789"]
  },
  "relationships": {
    "comp_789": {
      "children": [],
      "parent": "frame_456",
      "siblings": ["comp_790", "comp_791"]
    }
  }
}
```

### 3.2 测试观点数据格式

```json
{
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
      "priority": "HIGH",
      "classifications": {
        "functional_type": ["normal_flow"],
        "test_type": ["functional"],
        "ux_dimension": ["usability"],
        "technical_aspect": ["navigation"]
      }
    }
  ],
  "input": [
    {
      "id": "2",
      "category": "機能性",
      "item": "異常系",
      "description": "入力値検証の確認",
      "example": "不正な値を入力した場合にエラーメッセージが表示されるか",
      "target_page": "/entry",
      "target_component": "メールアドレス",
      "design_link": "figma_url",
      "priority": "MEDIUM",
      "classifications": {
        "functional_type": ["error_handling"],
        "test_type": ["validation"],
        "ux_dimension": ["error_prevention"],
        "technical_aspect": ["input_validation"]
      }
    }
  ]
}
```

### 3.3 历史测试用例数据格式

```json
{
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
  ],
  "stats": {
    "total_cases": 120,
    "file_count": 3,
    "component_types": {
      "button": 45,
      "input": 35,
      "checkbox": 10
    },
    "action_types": {
      "click": 50,
      "input": 40,
      "validation": 30
    },
    "category_types": {
      "functional": 80,
      "usability": 25,
      "security": 15
    }
  }
}
```

## 4. 实现说明

### 4.1 Web端实现要点

1. **文件解析**
   - 实现Figma文件解析
   - 实现测试观点文件解析（支持多种格式）
   - 实现历史测试用例文件解析

2. **数据标准化**
   - 将解析结果转换为标准格式
   - 验证数据完整性和有效性

3. **API调用**
   - 调用Dify API启动工作流
   - 定期轮询工作流状态
   - 获取并展示工作流结果

### 4.2 Dify端实现要点

1. **数据处理**
   - 接收标准化的数据
   - 缓存数据以供工作流使用

2. **工作流执行**
   - 异步处理工作流
   - 状态管理与进度跟踪
   - 错误处理与恢复

3. **结果生成**
   - 生成标准格式的测试用例
   - 提供多种输出格式

## 5. 安全与性能考虑

1. **数据安全**
   - 敏感数据不应在API响应中返回
   - 使用缓存ID代替直接传输大量数据

2. **性能优化**
   - 使用异步处理避免阻塞
   - 实现缓存策略减少重复计算
   - 支持大文件分块处理

3. **错误处理**
   - 提供详细的错误信息
   - 支持部分失败的情况
   - 实现重试机制
