from typing import Dict, Any
import json
import sys
import os
import hashlib

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.llm_client import LLMClient
from state_management import StateManager
from utils.cache_manager import cache_llm_call, cache_manager

def generate_cache_key(state: Dict[str, Any]) -> str:
    """生成缓存键"""
    figma_data = state.get("figma_data", {})
    viewpoints_file = state.get("viewpoints_file", {})
    modules_analysis = state.get("modules_analysis", {})
    
    content = {
        "figma_data": figma_data,
        "viewpoints_file": viewpoints_file,
        "modules_analysis": modules_analysis
    }
    return hashlib.md5(json.dumps(content, sort_keys=True).encode()).hexdigest()

@cache_llm_call(ttl=3600)  # 缓存LLM调用结果1小时
def map_figma_to_viewpoints(state: Dict[str, Any], llm_client: LLMClient) -> Dict[str, Any]:
    """
    第二步：将Figma文件与测试观点模块进行映射（带缓存）
    """
    # 生成缓存键
    cache_key = generate_cache_key(state)
    
    # 检查缓存
    cached_result = cache_manager.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    figma_data = state["figma_data"]
    viewpoints_file = state["viewpoints_file"]
    modules_analysis = state["modules_analysis"]
    
    prompt = f"""
    你是一个专业的UI/UX分析师。请分析Figma文件，与测试观点模块进行映射：

    Figma文件结构：
    {json.dumps(figma_data, ensure_ascii=False, indent=2)}

    测试观点模块：
    {json.dumps(modules_analysis, ensure_ascii=False, indent=2)}

    请进行以下分析：
    1. Figma中是否包含测试观点文件中的所有模块
    2. 每个模块在Figma中的具体页面和组件位置
    3. 是否存在测试观点中提到的功能在Figma中缺失
    4. Figma中是否有测试观点未覆盖的功能
    5. 分析页面结构和组件层次关系

    请以JSON格式输出映射结果：
    {{
        "module_mapping": [
            {{
                "viewpoint_module": "测试观点模块名",
                "figma_pages": ["相关页面名称"],
                "figma_components": ["相关组件ID和名称"],
                "coverage_status": "FULL_COVERAGE/PARTIAL_COVERAGE/MISSING",
                "missing_features": ["缺失的功能描述"],
                "extra_features": ["额外功能描述"],
                "component_hierarchy": "组件层次结构"
            }}
        ],
        "coverage_gaps": ["覆盖缺口列表"],
        "recommendations": ["改进建议"],
        "mapping_quality_score": "映射质量评分(0-100)"
    }}
    """
    
    try:
        mapping_result = llm_client.generate(prompt)
        # 尝试解析JSON结果
        if isinstance(mapping_result, str):
            mapping_result = json.loads(mapping_result)
        
        # 更新状态
        updated_state = StateManager.update_state(state, {
            "figma_viewpoints_mapping": mapping_result
        })
        
        # 记录日志
        updated_state = StateManager.log_step(updated_state, 
            "map_figma_to_viewpoints", 
            f"成功映射 {len(mapping_result.get('module_mapping', []))} 个模块")
        
        # 缓存结果
        cache_manager.set(cache_key, updated_state, ttl=3600)
        
        return updated_state
        
    except Exception as e:
        # 错误处理
        error_result = {
            "module_mapping": [],
            "coverage_gaps": [],
            "recommendations": ["映射过程中出现错误"],
            "mapping_quality_score": 0
        }
        
        updated_state = StateManager.update_state(state, {
            "figma_viewpoints_mapping": error_result
        })
        
        updated_state = StateManager.log_step(updated_state, 
            "map_figma_to_viewpoints", 
            f"映射失败: {str(e)}")
        
        # 缓存错误结果
        cache_manager.set(cache_key, updated_state, ttl=1800)
        
        return updated_state