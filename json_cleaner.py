import json

# 保留字段列表（你可以根据需要修改）
PRESERVED_KEYS = {
    "id", "name", "type", "characters", "style", "interactions",
    "absoluteBoundingBox", "fills", "strokes", "strokeWeight", "cornerRadius"
}

# 判断是否为需要关注的组件类型（可自定义）
INTERESTED_TYPES = {
    "FRAME", "GROUP", "TEXT", "VECTOR", "RECTANGLE", "BUTTON"
}

# 递归函数：筛选出简化后的结构
def extract_essential_info(node):
    if node.get("type") not in INTERESTED_TYPES and "children" not in node:
        return None

    # 提取重要字段
    simplified_node = {key: node[key] for key in PRESERVED_KEYS if key in node}
    simplified_node["type"] = node.get("type")

    # 递归处理 children
    if "children" in node:
        simplified_children = []
        for child in node["children"]:
            child_info = extract_essential_info(child)
            if child_info:
                simplified_children.append(child_info)
        if simplified_children:
            simplified_node["children"] = simplified_children

    return simplified_node

# 读取原始 figma JSON
with open("Bolt.fig..fig._Design__prototype_edit_profile.json", "r", encoding="utf-8") as f:
    raw_data = json.load(f)

# 起点是 document 的 children，通常是页面结构
if "document" in raw_data:
    root_node = raw_data["document"]
else:
    root_node = raw_data  # 如果直接是 node 数据

# 提取简化数据
simplified_result = extract_essential_info(root_node)

# 输出到新文件
with open("figma_simplified.json", "w", encoding="utf-8") as f:
    json.dump(simplified_result, f, indent=2, ensure_ascii=False)

print("✅ 简化后的 JSON 已保存为 figma_simplified.json")
