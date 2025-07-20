from typing import Dict, Any
import json
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.llm_client import LLMClient
from state_management import StateManager

def analyze_viewpoints_modules(state: Dict[str, Any], llm_client: LLMClient) -> Dict[str, Any]:
    """
    第一步：理解测试观点文件，识别模块，检查完整性
    """
    viewpoints_file = state["viewpoints_file"]
    
    prompt = f"""
    你是一个专业的测试分析师。请分析以下测试观点文件，识别所有功能模块并检查完整性：

    测试观点文件内容：
    {json.dumps(viewpoints_file, ensure_ascii=False, indent=2)}

    请进行以下分析：
    1. 识别所有功能模块（如：登录/注册、搜索、餐厅详情等）
    2. 统计每个模块包含的测试观点数量
    3. 分析模块之间的依赖关系
    4. 检查是否存在模块遗漏
    5. 评估测试覆盖的完整性

    请以JSON格式输出分析结果：
    {{
        "modules": [
            {{
                "name": "模块名称",
                "viewpoints_count": 数量,
                "priority": "HIGH/MEDIUM/LOW",
                "dependencies": ["依赖模块"],
                "coverage_status": "COMPLETE/PARTIAL/MISSING",
                "description": "模块描述"
            }}
        ],
        "missing_modules": ["可能遗漏的模块"],
        "recommendations": ["建议补充的测试观点"],
        "overall_coverage_score": "整体覆盖度评分(0-100)",
        "analysis_summary": "分析总结"
    }}
    """
    
    try:
        analysis_result = llm_client.generate(prompt)
        # 尝试解析JSON结果
        if isinstance(analysis_result, str):
            analysis_result = json.loads(analysis_result)
        
        # 更新状态
        updated_state = StateManager.update_state(state, {
            "modules_analysis": analysis_result
        })
        
        # 记录日志
        updated_state = StateManager.log_step(updated_state, 
            "analyze_viewpoints_modules", 
            f"成功分析 {len(analysis_result.get('modules', []))} 个模块")
        
        return updated_state
        
    except Exception as e:
        # 错误处理
        error_result = {
            "modules": [],
            "missing_modules": [],
            "recommendations": ["分析过程中出现错误"],
            "overall_coverage_score": 0,
            "analysis_summary": f"分析失败: {str(e)}"
        }
        
        updated_state = StateManager.update_state(state, {
            "modules_analysis": error_result
        })
        
        updated_state = StateManager.log_step(updated_state, 
            "analyze_viewpoints_modules", 
            f"分析失败: {str(e)}")
        
        return updated_state 