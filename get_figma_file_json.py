import requests
import json
import os
import sys

ACCESS_TOKEN = "figd_BnC3jmqlxuRzcdVfYuHg-YfNteOT8pp-G5Gqt0Ze"
FILE_KEY = "52jDe7Im5bAr6J8Fl9sFn4"
FIGMA_API_URL = f"https://api.figma.com/v1/files/{FILE_KEY}"
headers = {"X-Figma-Token": ACCESS_TOKEN}

def fetch_figma_file():
    response = requests.get(FIGMA_API_URL, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None

def get_page_list(figma_json):
    return [page.get('name', 'page') for page in figma_json.get('document', {}).get('children', [])]

def get_page_by_name(figma_json, page_name):
    for page in figma_json.get('document', {}).get('children', []):
        if page.get('name', 'page') == page_name:
            return page
    return None

def get_groups_in_page(page_json):
    groups = []
    def find_groups(node):
        if node.get('type') == 'GROUP':
            groups.append(node)
        for child in node.get('children', []):
            find_groups(child)
    find_groups(page_json)
    return groups

def save_json_to_file(obj, filename):
    safe_file_name = filename.replace('/', '_').replace('\\', '_').replace(' ', '_')
    with open(safe_file_name, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"Saved {safe_file_name}")

def save_group(group, file_prefix):
    name = group.get('name', 'group')
    filename = f"{file_prefix}_group_{name}.json"
    save_json_to_file(group, filename)

def save_all_groups(page_json, file_prefix):
    groups = get_groups_in_page(page_json)
    for group in groups:
        save_group(group, file_prefix)

def save_page(page_json, file_prefix):
    filename = f"{file_prefix}_page.json"
    save_json_to_file(page_json, filename)

def get_top_layers_in_page(page_json):
    """
    返回页面下所有顶级 FRAME/COMPONENT/INSTANCE（不要求#开头，兼容主流设计命名）
    """
    valid_types = {"FRAME", "COMPONENT", "INSTANCE"}
    return [child for child in page_json.get('children', []) if child.get('type') in valid_types]

def save_top_layer(page_json, layer_name, file_prefix):
    top_layers = get_top_layers_in_page(page_json)
    for layer in top_layers:
        if layer.get('name') == layer_name:
            safe_name = layer_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
            save_json_to_file(layer, f"{file_prefix}_{safe_name}.json")
            print(f"已保存顶级图层: {layer_name}")
            return
    print(f"未找到顶级图层: {layer_name}")

def save_all_top_layers(page_json, file_prefix):
    top_layers = get_top_layers_in_page(page_json)
    for layer in top_layers:
        layer_name = layer.get('name', 'layer')
        safe_name = layer_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
        save_json_to_file(layer, f"{file_prefix}_{safe_name}.json")
    print(f"已保存全部顶级FRAME/COMPONENT/INSTANCE图层，共{len(top_layers)}个")

def main():
    # 命令行参数说明
    usage = '''\n用法: python get_figma_file_json.py <action> [参数]\n\n支持的action:\n  list_pages\n  list_groups <页面名>\n  save_group <页面名> <分组名>\n  save_all_groups <页面名>\n  save_page <页面名>\n  list_top_groups <页面名>\n  save_top_group <页面名> <分组名>\n'''
    if len(sys.argv) < 2:
        print(usage)
        return
    action = sys.argv[1]
    figma_json = fetch_figma_file()
    if not figma_json:
        return
    file_prefix = figma_json.get('name', 'figma_file')
    if action == 'list_pages':
        pages = get_page_list(figma_json)
        print("页面列表:")
        for p in pages:
            print("-", p)
    elif action == 'list_groups':
        if len(sys.argv) < 3:
            print("缺少页面名参数")
            return
        page_name = sys.argv[2]
        page = get_page_by_name(figma_json, page_name)
        if not page:
            print(f"未找到页面: {page_name}")
            return
        groups = get_groups_in_page(page)
        print(f"页面 {page_name} 的分组:")
        for g in groups:
            print("-", g.get('name', 'group'))
    elif action == 'save_group':
        if len(sys.argv) < 4:
            print("缺少页面名或分组名参数")
            return
        page_name = sys.argv[2]
        group_name = sys.argv[3]
        page = get_page_by_name(figma_json, page_name)
        if not page:
            print(f"未找到页面: {page_name}")
            return
        groups = get_groups_in_page(page)
        for g in groups:
            if g.get('name') == group_name:
                save_group(g, file_prefix + '_' + page_name)
                return
        print(f"未找到分组: {group_name}")
    elif action == 'save_all_groups':
        if len(sys.argv) < 3:
            print("缺少页面名参数")
            return
        page_name = sys.argv[2]
        page = get_page_by_name(figma_json, page_name)
        if not page:
            print(f"未找到页面: {page_name}")
            return
        save_all_groups(page, file_prefix + '_' + page_name)
    elif action == 'save_page':
        if len(sys.argv) < 3:
            print("缺少页面名参数")
            return
        page_name = sys.argv[2]
        page = get_page_by_name(figma_json, page_name)
        if not page:
            print(f"未找到页面: {page_name}")
            return
        save_page(page, file_prefix + '_' + page_name)
    elif action == 'list_top_groups':
        if len(sys.argv) < 3:
            print("缺少页面名参数")
            return
        page_name = sys.argv[2]
        page = get_page_by_name(figma_json, page_name)
        if not page:
            print(f"未找到页面: {page_name}")
            return
        top_layers = get_top_layers_in_page(page)
        print(f"页面 {page_name} 的顶级图层（FRAME/COMPONENT/INSTANCE）:")
        if not top_layers:
            print("(无)")
        for layer in top_layers:
            print("-", layer.get('name', 'layer'))
    elif action == 'save_top_group':
        if len(sys.argv) < 4:
            print("缺少页面名或图层名参数")
            return
        page_name = sys.argv[2]
        layer_name = sys.argv[3]
        page = get_page_by_name(figma_json, page_name)
        if not page:
            print(f"未找到页面: {page_name}")
            return
        save_top_layer(page, layer_name, file_prefix + '_' + page_name)
    elif action == 'save_all_top_groups':
        if len(sys.argv) < 3:
            print("缺少页面名参数")
            return
        page_name = sys.argv[2]
        page = get_page_by_name(figma_json, page_name)
        if not page:
            print(f"未找到页面: {page_name}")
            return
        save_all_top_layers(page, file_prefix + '_' + page_name)
    elif action == 'debug_top_children':
        if len(sys.argv) < 3:
            print("缺少页面名参数")
            return
        page_name = sys.argv[2]
        page = get_page_by_name(figma_json, page_name)
        if not page:
            print(f"未找到页面: {page_name}")
            return
        print(f"页面 {page_name} 的所有顶级 children:")
        for child in page.get('children', []):
            print(f"- name: {child.get('name','')}, type: {child.get('type','')}")
    else:
        print("未知action")
        print(usage)

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
