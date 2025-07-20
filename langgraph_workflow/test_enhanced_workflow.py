import json
import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from enhanced_workflow import run_enhanced_testcase_generation
from utils.llm_client import LLMClient

def test_enhanced_workflow():
    """测试增强工作流"""
    
    # 模拟Figma数据
    figma_data = {
        "pages": [
            {
                "name": "登录页面",
                "components": [
                    {"type": "INPUT", "name": "用户名输入框", "id": "input_1"},
                    {"type": "INPUT", "name": "密码输入框", "id": "input_2"},
                    {"type": "BUTTON", "name": "登录按钮", "id": "button_1"}
                ]
            },
            {
                "name": "搜索页面", 
                "components": [
                    {"type": "INPUT", "name": "搜索框", "id": "input_3"},
                    {"type": "BUTTON", "name": "搜索按钮", "id": "button_2"}
                ]
            }
        ]
    }
    
    # 模拟测试观点文件
    viewpoints_file = {
        "登录/注册": [
            {
                "viewpoint": "支持正常登录/注册流程",
                "expected_purpose": "验证账号系统基本可用性",
                "checklist": [
                    "账号密码正确能登录",
                    "注册页面验证项完整",
                    "错误提示显示正确"
                ],
                "priority": "HIGH",
                "category": "Functional",
                "test_id": "TP-001"
            }
        ],
        "搜索": [
            {
                "viewpoint": "搜索功能能准确响应",
                "expected_purpose": "保证用户搜索关键字可找到目标餐厅",
                "checklist": [
                    "输入关键词后返回相关餐厅",
                    "支持模糊匹配",
                    "显示推荐列表"
                ],
                "priority": "HIGH",
                "category": "Functional",
                "test_id": "TP-002"
            }
        ]
    }
    
    # 配置LLM客户端
    llm_client = LLMClient(
        provider='gpt-4o',
        api_key=os.environ.get('OPENAI_API_KEY', ''),
        temperature=0.2
    )
    
    print("开始测试增强工作流...")
    
    try:
        # 运行工作流
        result = run_enhanced_testcase_generation(figma_data, viewpoints_file, llm_client)
        
        # 输出结果
        print("=== 增强工作流测试结果 ===")
        print(f"模块分析: {len(result.get('modules_analysis', {}).get('modules', []))} 个模块")
        print(f"Figma映射: {len(result.get('figma_viewpoints_mapping', {}).get('module_mapping', []))} 个映射")
        print(f"Checklist映射: {len(result.get('checklist_mapping', []))} 个项目")
        print(f"测试目的验证: {len(result.get('test_purpose_validation', []))} 个验证")
        print(f"最终测试用例: {len(result.get('final_testcases', []))} 个用例")
        print(f"工作流日志: {len(result.get('workflow_log', []))} 条记录")
        
        # 保存结果到文件
        with open('test_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print("测试结果已保存到 test_result.json")
        
        # 验证核心功能
        validate_test_results(result)
        
    except Exception as e:
        print(f"测试失败: {str(e)}")
        return False
    
    return True

def validate_test_results(result):
    """验证测试结果"""
    print("\n=== 验证测试结果 ===")
    
    # 验证模块分析
    modules_analysis = result.get('modules_analysis', {})
    if modules_analysis and 'modules' in modules_analysis:
        print("✅ 模块分析完成")
    else:
        print("❌ 模块分析失败")
    
    # 验证Figma映射
    figma_mapping = result.get('figma_viewpoints_mapping', {})
    if figma_mapping and 'module_mapping' in figma_mapping:
        print("✅ Figma映射完成")
    else:
        print("❌ Figma映射失败")
    
    # 验证Checklist映射
    checklist_mapping = result.get('checklist_mapping', [])
    if checklist_mapping:
        print("✅ Checklist映射完成")
    else:
        print("❌ Checklist映射失败")
    
    # 验证测试目的验证
    test_purpose_validation = result.get('test_purpose_validation', [])
    if test_purpose_validation:
        print("✅ 测试目的验证完成")
    else:
        print("❌ 测试目的验证失败")
    
    # 验证质量分析
    quality_analysis = result.get('quality_analysis', {})
    if quality_analysis:
        print("✅ 质量分析完成")
    else:
        print("❌ 质量分析失败")
    
    # 验证最终测试用例
    final_testcases = result.get('final_testcases', [])
    if final_testcases:
        print("✅ 最终测试用例生成完成")
    else:
        print("❌ 最终测试用例生成失败")
    
    # 验证工作流日志
    workflow_log = result.get('workflow_log', [])
    if workflow_log:
        print("✅ 工作流日志记录完成")
    else:
        print("❌ 工作流日志记录失败")

def test_individual_nodes():
    """测试单个节点"""
    print("\n=== 测试单个节点 ===")
    
    # 模拟数据
    figma_data = {
        "pages": [
            {
                "name": "登录页面",
                "components": [
                    {"type": "INPUT", "name": "用户名输入框", "id": "input_1"},
                    {"type": "INPUT", "name": "密码输入框", "id": "input_2"},
                    {"type": "BUTTON", "name": "登录按钮", "id": "button_1"}
                ]
            }
        ]
    }
    
    viewpoints_file = {
        "登录/注册": [
            {
                "viewpoint": "支持正常登录/注册流程",
                "expected_purpose": "验证账号系统基本可用性",
                "checklist": [
                    "账号密码正确能登录",
                    "注册页面验证项完整"
                ],
                "priority": "HIGH",
                "category": "Functional"
            }
        ]
    }
    
    # 配置LLM客户端
    llm_client = LLMClient(
        provider='gpt-4o',
        api_key=os.environ.get('OPENAI_API_KEY', ''),
        temperature=0.2
    )
    
    try:
        # 测试节点1：分析测试观点模块
        print("测试节点1: analyze_viewpoints_modules")
        from nodes.analyze_viewpoints_modules import analyze_viewpoints_modules
        state = {"viewpoints_file": viewpoints_file}
        result1 = analyze_viewpoints_modules(state, llm_client)
        print(f"✅ 节点1完成，分析 {len(result1.get('modules_analysis', {}).get('modules', []))} 个模块")
        
        # 测试节点2：Figma映射
        print("测试节点2: map_figma_to_viewpoints")
        from nodes.map_figma_to_viewpoints import map_figma_to_viewpoints
        state = {
            "figma_data": figma_data,
            "viewpoints_file": viewpoints_file,
            "modules_analysis": result1.get('modules_analysis', {})
        }
        result2 = map_figma_to_viewpoints(state, llm_client)
        print(f"✅ 节点2完成，映射 {len(result2.get('figma_viewpoints_mapping', {}).get('module_mapping', []))} 个模块")
        
        # 测试节点3：Checklist映射
        print("测试节点3: map_checklist_to_figma_areas")
        from nodes.map_checklist_to_figma_areas import map_checklist_to_figma_areas
        state.update(result2)
        result3 = map_checklist_to_figma_areas(state, llm_client)
        print(f"✅ 节点3完成，映射 {len(result3.get('checklist_mapping', []))} 个checklist项目")
        
        # 测试节点4：测试目的验证
        print("测试节点4: validate_test_purpose_coverage")
        from nodes.validate_test_purpose_coverage import validate_test_purpose_coverage
        state.update(result3)
        result4 = validate_test_purpose_coverage(state, llm_client)
        print(f"✅ 节点4完成，验证 {len(result4.get('test_purpose_validation', []))} 个测试观点")
        
        # 测试节点5：深度理解
        print("测试节点5: deep_understanding_and_gap_analysis")
        from nodes.deep_understanding_and_gap_analysis import deep_understanding_and_gap_analysis
        state.update(result4)
        result5 = deep_understanding_and_gap_analysis(state, llm_client)
        print(f"✅ 节点5完成，识别 {len(result5.get('quality_analysis', {}).get('blind_spots', []))} 个盲点")
        
        # 测试节点6：生成最终测试用例
        print("测试节点6: generate_final_testcases")
        from nodes.generate_final_testcases import generate_final_testcases
        state.update(result5)
        result6 = generate_final_testcases(state, llm_client)
        print(f"✅ 节点6完成，生成 {len(result6.get('final_testcases', []))} 个测试用例")
        
        print("✅ 所有节点测试完成")
        
    except Exception as e:
        print(f"❌ 节点测试失败: {str(e)}")

def test_api_endpoints():
    """测试API端点"""
    print("\n=== 测试API端点 ===")
    
    # 这里可以添加API端点测试代码
    # 由于需要运行FastAPI服务器，这里只提供测试框架
    print("API端点测试需要启动FastAPI服务器")
    print("可以使用以下命令启动服务器:")
    print("uvicorn main:app --reload --host 0.0.0.0 --port 8000")
    print("然后使用curl或Postman测试以下端点:")
    print("- POST /run_enhanced_workflow/")
    print("- POST /run_enhanced_workflow_step/")
    print("- GET /workflow_status/{workflow_id}")

if __name__ == "__main__":
    print("开始执行增强工作流测试...")
    
    # 检查环境变量
    if not os.environ.get('OPENAI_API_KEY'):
        print("警告: 未设置OPENAI_API_KEY环境变量")
        print("请设置环境变量: export OPENAI_API_KEY='your-api-key'")
    
    # 运行测试
    success = test_enhanced_workflow()
    
    if success:
        # 测试单个节点
        test_individual_nodes()
        
        # 测试API端点
        test_api_endpoints()
        
        print("\n🎉 所有测试完成！")
    else:
        print("\n❌ 测试失败") 