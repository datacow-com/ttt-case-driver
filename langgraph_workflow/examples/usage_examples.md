# LangGraph Workflow 使用示例

## 1. 日语化测试用例生成

### 基本流程

```bash
# 1. 启动服务
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-xxx \
  -e CLAUDE_API_KEY=sk-yyy \
  langgraph-workflow

# 2. 解析测试观点文件（支持JSON、CSV、Excel）
curl -X POST "http://localhost:8000/parse_viewpoints/" \
  -F "viewpoints_file=@viewpoints_ja.json" \
  -F "file_extension=json"

# 3. 生成测试用例
curl -X POST "http://localhost:8000/run_node/generate_testcases/" \
  -F "component_viewpoints=@component_viewpoints.json" \
  -F "provider=gpt-4o" \
  -F "api_key=sk-xxx" \
  -F "temperature=0.3"

# 4. 格式化输出为日语Excel
curl -X POST "http://localhost:8000/run_node/format_output/" \
  -F "testcases=@testcases.json" \
  -F "output_format=excel" \
  -F "language=ja" \
  --output "テストケース_20241201_143000.xlsx"
```

### 测试观点文件示例

#### JSON格式
```json
{
  "BUTTON": [
    {
      "viewpoint": "クリック可能性の検証",
      "priority": "HIGH",
      "category": "Functional",
      "checklist": [
        "ボタンが正常にクリックできることを確認",
        "クリック後の応答時間を確認"
      ],
      "expected_result": "ボタンが正常に機能する",
      "notes": "アクセシビリティ重要"
    }
  ]
}
```

#### CSV格式
```csv
コンポーネントタイプ,テスト観点（Test Viewpoint）,期待目的,チェックリスト,優先度,テストタイプ,備考
BUTTON,クリック可能性の検証,ボタンが正常に機能する,"1.ボタンがクリックできる 2.応答時間を確認",高,機能テスト,アクセシビリティ重要
INPUT,テキスト入力の検証,入力フィールドが正常に機能する,"1.正常なテキスト入力 2.文字数制限確認",高,機能テスト,セキュリティテスト含む
```

#### Excel格式
专业测试观点Excel模板，包含以下列：
- コンポーネントタイプ (Component Type)
- テスト観点（Test Viewpoint）
- 期待目的 (Expected Purpose)
- チェックリスト (Checklist)
- 優先度 (Priority)
- テストタイプ (Test Type)
- 備考 (Notes)

## 2. 语言切换

### 查看当前语言设置
```bash
curl "http://localhost:8000/system/language"
```

### 切换语言
```bash
# 切换到英语
curl -X POST "http://localhost:8000/system/language" \
  -F "language=en"

# 切换到日语
curl -X POST "http://localhost:8000/system/language" \
  -F "language=ja"
```

## 3. 支持的格式查询

### 查看支持的测试观点格式
```bash
curl "http://localhost:8000/viewpoints/formats"
```

响应示例：
```json
{
  "supported_formats": ["json", "csv", "xlsx", "xls"],
  "examples": {
    "json": "...",
    "csv": "...",
    "excel": "..."
  }
}
```

## 4. 完整工作流示例

### 日语测试用例生成完整流程

```python
import requests
import json

# 配置
BASE_URL = "http://localhost:8000"
API_KEY = "sk-xxx"

# 1. 获取Figma文件
figma_response = requests.post(f"{BASE_URL}/run_node/fetch_and_clean_figma_json/", 
    data={"access_token": "figma_token", "file_key": "figma_file_key"})
figma_data = figma_response.json()

# 2. 匹配测试观点
with open("viewpoints_ja.json", "rb") as f:
    viewpoints_response = requests.post(f"{BASE_URL}/run_node/match_viewpoints/",
        files={"clean_json": ("figma.json", json.dumps(figma_data)),
               "viewpoints_db": ("viewpoints.json", f)},
        data={"provider": "gpt-4o", "api_key": API_KEY, "language": "ja"})
matched_viewpoints = viewpoints_response.json()

# 3. 生成测试用例
with open("component_viewpoints.json", "rb") as f:
    testcases_response = requests.post(f"{BASE_URL}/run_node/generate_testcases/",
        files={"component_viewpoints": f},
        data={"provider": "gpt-4o", "api_key": API_KEY, "language": "ja"})
testcases = testcases_response.json()

# 4. 输出日语Excel
with open("testcases.json", "rb") as f:
    excel_response = requests.post(f"{BASE_URL}/run_node/format_output/",
        files={"testcases": f},
        data={"output_format": "excel", "language": "ja"})
    
    # 保存Excel文件
    with open("テストケース_生成.xlsx", "wb") as excel_file:
        excel_file.write(excel_response.content)
```

## 5. 错误处理示例

### 测试观点文件解析错误
```bash
# 上传无效格式文件
curl -X POST "http://localhost:8000/parse_viewpoints/" \
  -F "viewpoints_file=@invalid_file.txt" \
  -F "file_extension=txt"
```

错误响应：
```json
{
  "detail": "サポートされていないファイル形式: txt"
}
```

### 语言设置错误
```bash
# 设置不支持的语言
curl -X POST "http://localhost:8000/system/language" \
  -F "language=zh"
```

错误响应：
```json
{
  "detail": "サポートされていない言語です"
}
```

## 6. 专业测试观点模板使用

### 使用内置模板
系统提供了专业的测试观点模板，位于 `templates/` 目录：

- `viewpoints_template_ja.json`: 日语版专业模板
- `viewpoints_template_en.json`: 英语版专业模板
- `viewpoints_template_ja.xlsx`: 日语Excel模板结构

### 自定义模板
可以根据项目需求创建自定义测试观点模板，支持以下字段：

- `viewpoint`: 测试观点名称
- `priority`: 优先级 (HIGH/MEDIUM/LOW)
- `category`: 测试类别 (Functional/Performance/Security等)
- `checklist`: 检查清单
- `expected_result`: 预期结果
- `notes`: 备注

## 7. 输出格式示例

### 日语Excel输出
生成的Excel文件包含以下列：
- テストケースID
- ページ
- コンポーネント
- 観点
- 手順
- 期待結果
- 優先度
- カテゴリ
- チェックリスト
- 期待目的
- 備考
- 作成日

### CSV输出
```csv
テストケースID,ページ,コンポーネント,観点,手順,期待結果,優先度,カテゴリ,作成日
TC-001,ログインページ,ボタン,クリック可能性の検証,「ログイン」ボタンをクリックする,ホームページに遷移する,高,機能テスト,2024年12月01日
```

## 8. 性能优化建议

### LLM参数调优
- `temperature`: 0.1-0.3 用于测试用例生成
- `provider`: 根据需求选择最适合的LLM提供商
- `prompt_template`: 使用专业测试模板提高质量

### 批量处理
- 使用工作流批量处理多个文件
- 利用中间结果缓存避免重复计算
- 合理设置并发限制

## 9. 故障排除

### 常见问题
1. **文件格式不支持**: 检查文件扩展名和内容格式
2. **LLM调用失败**: 验证API密钥和网络连接
3. **内存不足**: 减少批量处理文件大小
4. **编码问题**: 确保文件使用UTF-8编码

### 日志查看
```bash
# 查看服务日志
docker logs langgraph-workflow

# 查看中间结果
curl "http://localhost:8000/intermediate/generate_testcases"
```