"""CLI 命令行接口 —— 供 AI/Claude skill 通过 subprocess 调用。

用法:
  python -m CodeLibManager.cli.main <command> [args...]
  CodeLibManager.exe cli <command> [args...]
"""

import argparse
import json
import sys
import os

# 确保可以 import core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.api import (
    list_modules, get_module_info, get_dependency_tree,
    copy_module_to_project, chain_copy_to_project,
    import_module, update_module, edit_module, verify_module, remove_module,
    add_library, remove_library, list_libraries, switch_library,
    validate_library, cleanup_broken_modules,
    add_category, rename_category, delete_category,
    add_group, rename_group, delete_group, list_groups,
    rename_library, update_library_path,
    LibraryError, PlatformError,
    get_adapter,
    CircularDependencyError, MissingDependencyError,
    load_config, save_config,
)


def _json_out(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_list_modules(args):
    result = list_modules(
        library_alias=args.library,
        category=args.category,
        status=args.status,
        search=args.search,
        summary=args.summary,
    )
    if args.json:
        _json_out(result)
    else:
        for m in result:
            status = "[Y]" if m.get("verified") else "[N]"
            if args.summary:
                print(f" {status} {m['category']:<15} {m['name']:<20} deps:{m['dep_count']}")
            else:
                desc = m.get("description", "")[:50]
                print(f" {status} {m['category']:<15} {m['name']:<20} v{m.get('version','1.0')}  deps:{m['dep_count']}  {desc}")


def cmd_info(args):
    result = get_module_info(args.library, args.module)
    if args.field:
        fields = [f.strip() for f in args.field.split(",")]
        result = {k: v for k, v in result.items() if k in fields}
    if args.json:
        _json_out(result)
    else:
        # --field 时精简文本输出
        if args.field:
            for k, v in result.items():
                if isinstance(v, list):
                    print(f"{k}: {', '.join(v) if v else '(无)'}")
                elif isinstance(v, dict):
                    print(f"{k}: {', '.join(f'{pk}={pv}' for pk, pv in v.items()) if v else '(无)'}")
                else:
                    print(f"{k}: {v}")
            return
        print(f"模块:     {result['name']}  v{result['version']}")
        print(f"分类:     {result['category']}")
        print(f"状态:     {'[Y] 已验证' if result['verified'] else '[N] 未验证'}"
              + (f" ({result['verified_date']})" if result.get('verified_date') else ""))
        print(f"分组:     {result['group']}")
        print(f"文件:     {', '.join(result['files']['source'] + result['files']['header'])}")
        deps = result['dependencies']
        print(f"依赖:     {', '.join(deps) if deps else '(无)'}")
        rdeps = result['reverse_dependencies']
        print(f"被依赖:   {', '.join(rdeps) if rdeps else '(无)'}")
        pins = result['pins']
        if pins:
            print(f"引脚:     {', '.join(f'{k}={v}' for k, v in pins.items())}")
        if result.get('notes'):
            print(f"备注:     {result['notes']}")


def cmd_tree(args):
    result = get_dependency_tree(args.library, args.module)

    if args.json:
        _json_out(result)
    else:
        def _print_tree(node, indent=0):
            prefix = "  " * indent
            status = "[Y]" if node["verified"] else "[N]"
            print(f"{prefix}{status} {node['name']} ({node['group']})")
            for child in node.get("dependencies", []):
                _print_tree(child, indent + 1)
        _print_tree(result)


def cmd_copy_to_project(args):
    result = copy_module_to_project(
        library_alias=args.library,
        module_name=args.module,
        project_path=args.project,
        dry_run=args.dry_run,
    )
    if args.json or args.dry_run:
        _json_out(result)
    else:
        print(f"已复制模块 '{result['module']}' 到工程")


def cmd_chain_copy(args):
    selected = args.select.split(",") if args.select else None
    resolutions = {}
    if args.conflicts:
        for item in args.conflicts.split(","):
            if ":" not in item:
                print(f"错误: 冲突条目 '{item}' 格式无效，应为 文件名:动作", file=sys.stderr)
                sys.exit(1)
            fn, act = item.split(":", 1)
            resolutions[fn] = act

    result = chain_copy_to_project(
        library_alias=args.library,
        module_name=args.module,
        project_path=args.project,
        selected_modules=selected,
        dry_run=args.dry_run,
        conflict_resolutions=resolutions or None,
    )
    if args.json or args.dry_run:
        _json_out(result)
    else:
        print(f"链复制完成: {result['module']}")
        for m in result["chain"]:
            print(f"  {m['name']} → {m['group']}")


def cmd_import_module(args):
    deps = args.deps.split(",") if args.deps else []
    try:
        file_paths = [os.path.join(args.source_dir, f) for f in os.listdir(args.source_dir)
                      if os.path.splitext(f)[1].lower() in ('.c', '.h')]
    except (FileNotFoundError, NotADirectoryError, PermissionError) as e:
        print(f"错误: 无法读取源目录 '{args.source_dir}': {e}", file=sys.stderr)
        sys.exit(1)
    if not file_paths:
        print("错误: 源目录中未找到 .c 或 .h 文件", file=sys.stderr)
        sys.exit(1)
    result = import_module(
        library_alias=args.library,
        file_paths=file_paths,
        name=args.name,
        category=args.category,
        version=args.version or "1.0",
        description=args.description or "",
        dependencies=deps,
        group=args.group or "Hardware",
    )
    if args.json:
        _json_out(result)
    else:
        print(f"已导入模块: {result['name']} ({result['category']})")


def cmd_update_module(args):
    result = update_module(
        library_alias=args.library,
        name=args.module,
        source_dir=args.source_dir,
        from_project=args.from_project,
        auto_verify=not args.no_verify,
    )
    if args.json:
        _json_out(result)
    else:
        print(f"已更新模块: {result['name']}")
        print(f"  快照: {result['snapshot']}")
        if result.get("auto_verified"):
            print(f"  已自动标记为已验证")


def cmd_edit_module(args):
    add = [os.path.abspath(f) for f in args.add] if args.add else None
    rm = args.remove if args.remove else None
    deps = args.deps.split(",") if args.deps else None
    new_pins = {}
    if args.pins:
        for line in args.pins.split(","):
            if "=" in line:
                k, v = line.split("=", 1)
                new_pins[k.strip()] = v.strip()
    result = edit_module(
        library_alias=args.library,
        name=args.module,
        new_name=args.new_name,
        new_category=args.new_category,
        new_version=args.new_version,
        new_description=args.new_description,
        new_group=args.new_group,
        new_pins=new_pins or None,
        new_verified=args.new_verified,
        new_dependencies=deps,
        add_files=add,
        remove_files=rm,
    )
    if args.json:
        _json_out(result)
    else:
        print(f"已编辑模块: {result['name']}")
        if result.get("old_name"):
            print(f"  已重命名: {result['old_name']} → {result['name']}")
        if result.get("snapshot"):
            print(f"  快照: {result['snapshot']}")
        print(f"  文件: {', '.join(result['files']['source'] + result['files']['header'])}")


def cmd_verify(args):
    result = verify_module(
        library_alias=args.library,
        name=args.module,
        status=args.status,
        notes=args.notes or "",
    )
    if args.json:
        _json_out(result)
    else:
        status_text = "已验证" if result["verified"] else "未验证"
        print(f"模块 '{result['name']}' 标记为: {status_text}")


def cmd_remove_module(args):
    result = remove_module(args.library, args.module, cleanup_deps=True)
    if args.json:
        _json_out(result)
    else:
        print(f"已移除模块: {result['name']} → {result['moved_to']}")
        cleaned = result.get("reverse_deps_cleaned", [])
        if cleaned:
            print(f"  已清理依赖引用: {', '.join(cleaned)}")


def cmd_add_library(args):
    result = add_library(args.alias, args.path)
    if args.json:
        _json_out(result)
    else:
        print(f"已添加库: {result['alias']} ({result['path']})")


def cmd_remove_library(args):
    remove_library(args.alias)
    if args.json:
        _json_out({"alias": args.alias, "removed": True})
    else:
        print(f"已移除库: {args.alias}")


def cmd_list_libraries(args):
    result = list_libraries()
    if args.json:
        _json_out(result)
    else:
        cfg = load_config()
        active = cfg.get("active_library", "")
        for l in result:
            mark = "*" if l["alias"] == active else " "
            print(f" {mark} {l['alias']:<20} {l['path']}")


def cmd_validate_library(args):
    issues = validate_library(args.library)
    if args.json:
        _json_out({"issues": issues, "count": len(issues)})
    else:
        if not issues:
            print("库完整性检查通过，没有问题。")
        else:
            print(f"检测到 {len(issues)} 个问题：")
            for iss in issues:
                print(f"  • {iss['message']}")


def cmd_cleanup_broken(args):
    result = cleanup_broken_modules(args.library)
    if args.json:
        _json_out(result)
    else:
        if result["count"] == 0:
            print("没有需要清理的无效条目。")
        else:
            print(f"已清理 {result['count']} 个无效模块条目:")
            for c in result["cleaned"]:
                print(f"  • {c['name']}: {c['reason']}")


def cmd_switch_library(args):
    try:
        result = switch_library(args.alias)
    except LibraryError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        _json_out(result)
    else:
        print(f"已切换到库: {result['alias']}")


def cmd_add_category(args):
    try:
        result = add_category(args.library, args.category)
    except LibraryError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        _json_out(result)
    else:
        print(f"已添加分类: {result['name']}")


def cmd_rename_category(args):
    try:
        result = rename_category(args.library, args.old, args.new)
    except LibraryError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        _json_out(result)
    else:
        updated = result.get("modules_updated", 0)
        print(f"已重命名分类: {result['old_name']} → {result['new_name']}")
        if updated:
            print(f"  已更新 {updated} 个模块的索引/元数据")


def cmd_delete_category(args):
    try:
        result = delete_category(args.library, args.category)
    except LibraryError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        _json_out(result)
    else:
        print(f"已删除分类: {result['name']}")


def cmd_add_group(args):
    try:
        result = add_group(args.library, args.group)
    except LibraryError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        _json_out(result)
    else:
        print(f"已添加分组: {result['name']}")


def cmd_rename_group(args):
    try:
        result = rename_group(args.library, args.old, args.new)
    except LibraryError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        _json_out(result)
    else:
        updated = result.get("modules_updated", 0)
        print(f"已重命名分组: {result['old_name']} → {result['new_name']}")
        if updated:
            print(f"  已更新 {updated} 个模块的 group 字段")


def cmd_delete_group(args):
    try:
        result = delete_group(args.library, args.group)
    except LibraryError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        _json_out(result)
    else:
        print(f"已删除分组: {result['name']}")


def cmd_list_groups(args):
    result = list_groups(args.library)
    if args.json:
        _json_out(result)
    else:
        if not result:
            print("(无分组)")
        else:
            for g in result:
                print(g)


def cmd_rename_library(args):
    try:
        result = rename_library(args.old_alias, args.new_alias)
    except LibraryError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        _json_out(result)
    else:
        print(f"已重命名库: {result['old_alias']} → {result['new_alias']}")


def cmd_update_library_path(args):
    try:
        result = update_library_path(args.alias, args.new_path)
    except LibraryError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        _json_out(result)
    else:
        print(f"已更新库路径: {result['alias']} → {result['new_path']}")


# ─── project 子命令 ───────────────────────────────────

def _resolve_project(project_path: str):
    """通用入口：自动检测平台 → 找到工程文件。"""
    adapter = get_adapter(project_path)
    return adapter, adapter.find_project_file(project_path)


def cmd_project_create_group(args):
    adapter, proj_file = _resolve_project(args.project)
    try:
        adapter.create_group(proj_file, args.group)
    except AttributeError:
        print(f"错误: 当前平台适配器不支持创建分组", file=sys.stderr)
        sys.exit(1)
    if args.json:
        _json_out({"project": args.project, "project_file": proj_file, "group": args.group})
    else:
        print(f"分组 '{args.group}': {proj_file}")


def cmd_project_add_file(args):
    adapter, proj_file = _resolve_project(args.project)
    try:
        adapter.add_file(proj_file, args.group, args.file_path)
    except AttributeError:
        print(f"错误: 当前平台适配器不支持添加文件", file=sys.stderr)
        sys.exit(1)
    if args.json:
        _json_out({"project": args.project, "project_file": proj_file, "group": args.group, "file": args.file_path})
    else:
        print(f"已注册: {args.file_path} → 分组 '{args.group}' ({proj_file})")


def cmd_project_remove_file(args):
    adapter, proj_file = _resolve_project(args.project)
    try:
        adapter.remove_file(proj_file, args.group, args.file_path)
    except AttributeError:
        print(f"错误: 当前平台适配器不支持移除文件", file=sys.stderr)
        sys.exit(1)
    if args.json:
        _json_out({"project": args.project, "project_file": proj_file, "group": args.group, "file": args.file_path})
    else:
        print(f"已移除: {args.file_path} ← 分组 '{args.group}' ({proj_file})")


def cmd_project_add_include(args):
    adapter, proj_file = _resolve_project(args.project)
    try:
        adapter.add_include_path(proj_file, args.folder)
    except AttributeError:
        print(f"错误: 当前平台适配器不支持添加 Include 路径", file=sys.stderr)
        sys.exit(1)
    if args.json:
        _json_out({"project": args.project, "project_file": proj_file, "folder": args.folder})
    else:
        print(f"Include 路径已添加: {args.folder} ({proj_file})")


def cmd_project_remove_group(args):
    adapter, proj_file = _resolve_project(args.project)
    try:
        adapter.remove_group(proj_file, args.group)
    except AttributeError:
        print(f"错误: 当前平台适配器不支持删除分组", file=sys.stderr)
        sys.exit(1)
    if args.json:
        _json_out({"project": args.project, "project_file": proj_file, "group": args.group})
    else:
        print(f"分组已删除: '{args.group}' ({proj_file})")


def cmd_project_remove_include(args):
    adapter, proj_file = _resolve_project(args.project)
    try:
        adapter.remove_include_path(proj_file, args.folder)
    except AttributeError:
        print(f"错误: 当前平台适配器不支持移除 Include 路径", file=sys.stderr)
        sys.exit(1)
    if args.json:
        _json_out({"project": args.project, "project_file": proj_file, "folder": args.folder})
    else:
        print(f"Include 路径已移除: {args.folder} ({proj_file})")


def cmd_project_add_define(args):
    adapter, proj_file = _resolve_project(args.project)
    try:
        adapter.add_define(proj_file, args.define)
    except AttributeError:
        print(f"错误: 当前平台适配器不支持添加 Define", file=sys.stderr)
        sys.exit(1)
    if args.json:
        _json_out({"project": args.project, "project_file": proj_file, "define": args.define})
    else:
        print(f"Define 已添加: {args.define} ({proj_file})")


def cmd_project_remove_define(args):
    adapter, proj_file = _resolve_project(args.project)
    try:
        adapter.remove_define(proj_file, args.define)
    except AttributeError:
        print(f"错误: 当前平台适配器不支持移除 Define", file=sys.stderr)
        sys.exit(1)
    if args.json:
        _json_out({"project": args.project, "project_file": proj_file, "define": args.define})
    else:
        print(f"Define 已移除: {args.define} ({proj_file})")


def main():
    parser = argparse.ArgumentParser(
        description="CodeLibManager CLI — 复用代码库管理器命令行接口"
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # list-modules
    p_list = sub.add_parser("list-modules", help="列出模块")
    p_list.add_argument("--library", help="库别名")
    p_list.add_argument("--category", help="按分类过滤")
    p_list.add_argument("--status", choices=["all", "verified", "unverified"], default="all")
    p_list.add_argument("--search", help="按名称/描述模糊搜索")
    p_list.add_argument("--summary", action="store_true", help="精简输出（减少 token）")
    p_list.add_argument("--json", action="store_true", help="JSON 格式输出")
    p_list.set_defaults(func=cmd_list_modules)

    # info
    p_info = sub.add_parser("info", help="查看模块详情")
    p_info.add_argument("module", help="模块名")
    p_info.add_argument("--library", help="库别名")
    p_info.add_argument("--field", help="只输出指定字段（逗号分隔，如 dependencies,pins）")
    p_info.add_argument("--json", action="store_true")
    p_info.set_defaults(func=cmd_info)

    # tree
    p_tree = sub.add_parser("tree", help="查看模块依赖树")
    p_tree.add_argument("module", help="模块名")
    p_tree.add_argument("--library", help="库别名")
    p_tree.add_argument("--json", action="store_true")
    p_tree.set_defaults(func=cmd_tree)

    # copy-to-project
    p_copy = sub.add_parser("copy-to-project", help="复制模块到工程")
    p_copy.add_argument("module", help="模块名")
    p_copy.add_argument("project", help="工程路径")
    p_copy.add_argument("--library", help="库别名")
    p_copy.add_argument("--dry-run", action="store_true", help="仅预览")
    p_copy.add_argument("--json", action="store_true")
    p_copy.set_defaults(func=cmd_copy_to_project)

    # chain-copy
    p_chain = sub.add_parser("chain-copy", help="模块链复制到工程")
    p_chain.add_argument("module", help="入口模块名")
    p_chain.add_argument("project", help="工程路径")
    p_chain.add_argument("--library", help="库别名")
    p_chain.add_argument("--select", help="只复制指定模块（逗号分隔）")
    p_chain.add_argument("--conflicts", help="冲突处理: file:skip|overwrite|rename,...")
    p_chain.add_argument("--dry-run", action="store_true", help="仅预览依赖链和冲突")
    p_chain.add_argument("--json", action="store_true")
    p_chain.set_defaults(func=cmd_chain_copy)

    # import-module
    p_import = sub.add_parser("import-module", help="导入新模块")
    p_import.add_argument("source_dir", help="模块源目录")
    p_import.add_argument("--library", help="库别名")
    p_import.add_argument("--name", required=True, help="模块名")
    p_import.add_argument("--category", required=True, help="分类")
    p_import.add_argument("--version", default="1.0")
    p_import.add_argument("--description", default="")
    p_import.add_argument("--deps", help="依赖模块（逗号分隔）")
    p_import.add_argument("--group", default="Hardware", help="工程分组")
    p_import.add_argument("--json", action="store_true")
    p_import.set_defaults(func=cmd_import_module)

    # update-module
    p_update = sub.add_parser("update-module", help="更新模块")
    p_update.add_argument("module", help="模块名")
    p_update.add_argument("source_dir", help="新源文件目录（--from-project 时为工程根路径）")
    p_update.add_argument("--library", help="库别名")
    p_update.add_argument("--from-project", action="store_true",
                           help="从工程目录反向同步（source_dir/<group>/<file>）")
    p_update.add_argument("--no-verify", action="store_true", help="不自动标记验证")
    p_update.add_argument("--json", action="store_true")
    p_update.set_defaults(func=cmd_update_module)

    # edit-module
    p_edit = sub.add_parser("edit-module", help="编辑模块元数据和文件")
    p_edit.add_argument("module", help="模块名")
    p_edit.add_argument("--library", help="库别名")
    p_edit.add_argument("--new-name", help="新名称")
    p_edit.add_argument("--new-category", help="新分类")
    p_edit.add_argument("--new-version", help="新版本号")
    p_edit.add_argument("--new-description", help="新描述")
    p_edit.add_argument("--new-group", help="新工程分组")
    p_edit.add_argument("--pins", help="引脚，逗号分隔: PA0=SERVO,PA1=LED")
    p_edit.add_argument("--new-verified",
                        type=lambda v: v.lower() in ("true", "1", "yes"),
                        help="验证状态 (true/false)")
    p_edit.add_argument("--deps", help="依赖模块（逗号分隔）")
    p_edit.add_argument("--add", nargs="*", help="要添加的文件路径")
    p_edit.add_argument("--remove", nargs="*", help="要移除的文件名")
    p_edit.add_argument("--json", action="store_true")
    p_edit.set_defaults(func=cmd_edit_module)

    # verify
    p_verify = sub.add_parser("verify", help="标记模块验证状态")
    p_verify.add_argument("module", help="模块名")
    p_verify.add_argument("--library", help="库别名")
    p_verify.add_argument("--status", required=True, choices=["passed", "failed"],
                           help="验证结果")
    p_verify.add_argument("--notes", help="备注说明")
    p_verify.add_argument("--json", action="store_true")
    p_verify.set_defaults(func=cmd_verify)

    # remove-module
    p_remove = sub.add_parser("remove-module", help="移除模块")
    p_remove.add_argument("module", help="模块名")
    p_remove.add_argument("--library", help="库别名")
    p_remove.add_argument("--json", action="store_true")
    p_remove.set_defaults(func=cmd_remove_module)

    # add-library
    p_addlib = sub.add_parser("add-library", help="注册新库")
    p_addlib.add_argument("alias", help="库别名")
    p_addlib.add_argument("path", help="库根路径")
    p_addlib.add_argument("--json", action="store_true")
    p_addlib.set_defaults(func=cmd_add_library)

    # remove-library
    p_rmlib = sub.add_parser("remove-library", help="注销库")
    p_rmlib.add_argument("alias", help="库别名")
    p_rmlib.add_argument("--json", action="store_true")
    p_rmlib.set_defaults(func=cmd_remove_library)

    # list-libraries
    p_libs = sub.add_parser("list-libraries", help="列出已注册的库")
    p_libs.add_argument("--json", action="store_true")
    p_libs.set_defaults(func=cmd_list_libraries)

    # validate-library
    p_val = sub.add_parser("validate-library", help="检测库完整性问题")
    p_val.add_argument("--library", default=None, help="目标库别名（默认活跃库）")
    p_val.add_argument("--json", action="store_true")
    p_val.set_defaults(func=cmd_validate_library)

    # cleanup-broken
    p_clean = sub.add_parser("cleanup-broken", help="清理所有无效模块索引条目")
    p_clean.add_argument("--library", default=None, help="目标库别名（默认活跃库）")
    p_clean.add_argument("--json", action="store_true")
    p_clean.set_defaults(func=cmd_cleanup_broken)

    # switch-library
    p_switch = sub.add_parser("switch-library", help="切换活跃库")
    p_switch.add_argument("alias", help="库别名")
    p_switch.add_argument("--json", action="store_true")
    p_switch.set_defaults(func=cmd_switch_library)

    # add-category
    p_addcat = sub.add_parser("add-category", help="添加分类（在库根创建空文件夹）")
    p_addcat.add_argument("category", help="分类名")
    p_addcat.add_argument("--library", help="库别名")
    p_addcat.add_argument("--json", action="store_true")
    p_addcat.set_defaults(func=cmd_add_category)

    # rename-category
    p_rencat = sub.add_parser("rename-category", help="重命名分类（联动更新索引和模块元数据）")
    p_rencat.add_argument("old", help="旧分类名")
    p_rencat.add_argument("new", help="新分类名")
    p_rencat.add_argument("--library", help="库别名")
    p_rencat.add_argument("--json", action="store_true")
    p_rencat.set_defaults(func=cmd_rename_category)

    # delete-category
    p_delcat = sub.add_parser("delete-category", help="删除空分类文件夹")
    p_delcat.add_argument("category", help="分类名")
    p_delcat.add_argument("--library", help="库别名")
    p_delcat.add_argument("--json", action="store_true")
    p_delcat.set_defaults(func=cmd_delete_category)

    # add-group
    p_addgrp = sub.add_parser("add-group", help="添加工程分组词条")
    p_addgrp.add_argument("group", help="分组名")
    p_addgrp.add_argument("--library", help="库别名")
    p_addgrp.add_argument("--json", action="store_true")
    p_addgrp.set_defaults(func=cmd_add_group)

    # rename-group
    p_rengrp = sub.add_parser("rename-group", help="重命名工程分组（联动更新所有模块）")
    p_rengrp.add_argument("old", help="旧分组名")
    p_rengrp.add_argument("new", help="新分组名")
    p_rengrp.add_argument("--library", help="库别名")
    p_rengrp.add_argument("--json", action="store_true")
    p_rengrp.set_defaults(func=cmd_rename_group)

    # delete-group
    p_delgrp = sub.add_parser("delete-group", help="删除未使用的工程分组")
    p_delgrp.add_argument("group", help="分组名")
    p_delgrp.add_argument("--library", help="库别名")
    p_delgrp.add_argument("--json", action="store_true")
    p_delgrp.set_defaults(func=cmd_delete_group)

    # list-groups
    p_lsgrp = sub.add_parser("list-groups", help="列出库的工程分组")
    p_lsgrp.add_argument("--library", help="库别名")
    p_lsgrp.add_argument("--json", action="store_true")
    p_lsgrp.set_defaults(func=cmd_list_groups)

    # rename-library
    p_renlib = sub.add_parser("rename-library", help="重命名库别名（不涉及物理路径）")
    p_renlib.add_argument("old_alias", help="旧别名")
    p_renlib.add_argument("new_alias", help="新别名")
    p_renlib.add_argument("--json", action="store_true")
    p_renlib.set_defaults(func=cmd_rename_library)

    # update-library-path
    p_uppath = sub.add_parser("update-library-path", help="更新库物理路径（不移动文件）")
    p_uppath.add_argument("alias", help="库别名")
    p_uppath.add_argument("new_path", help="新路径")
    p_uppath.add_argument("--json", action="store_true")
    p_uppath.set_defaults(func=cmd_update_library_path)

    # project-* （工程结构管理，自动检测平台）
    p_proj = sub.add_parser("project-create-group", help="在工程中创建分组")
    p_proj.add_argument("project", help="工程根目录路径")
    p_proj.add_argument("group", help="分组名")
    p_proj.add_argument("--json", action="store_true")
    p_proj.set_defaults(func=cmd_project_create_group)

    p_proj = sub.add_parser("project-add-file", help="向工程分组注册文件")
    p_proj.add_argument("project", help="工程根目录路径")
    p_proj.add_argument("group", help="分组名")
    p_proj.add_argument("file_path", help="文件相对路径（如 .\\Hardware\\LED.c）")
    p_proj.add_argument("--json", action="store_true")
    p_proj.set_defaults(func=cmd_project_add_file)

    p_proj = sub.add_parser("project-remove-file", help="从工程分组移除文件")
    p_proj.add_argument("project", help="工程根目录路径")
    p_proj.add_argument("group", help="分组名")
    p_proj.add_argument("file_path", help="文件相对路径")
    p_proj.add_argument("--json", action="store_true")
    p_proj.set_defaults(func=cmd_project_remove_file)

    p_proj = sub.add_parser("project-add-include", help="向工程添加 Include 路径")
    p_proj.add_argument("project", help="工程根目录路径")
    p_proj.add_argument("folder", help="文件夹相对路径（如 .\\Hardware）")
    p_proj.add_argument("--json", action="store_true")
    p_proj.set_defaults(func=cmd_project_add_include)

    p_proj = sub.add_parser("project-remove-include", help="从工程移除 Include 路径")
    p_proj.add_argument("project", help="工程根目录路径")
    p_proj.add_argument("folder", help="文件夹相对路径")
    p_proj.add_argument("--json", action="store_true")
    p_proj.set_defaults(func=cmd_project_remove_include)

    p_proj = sub.add_parser("project-add-define", help="向工程添加预处理器定义")
    p_proj.add_argument("project", help="工程根目录路径")
    p_proj.add_argument("define", help="预处理器定义（如 DEBUG）")
    p_proj.add_argument("--json", action="store_true")
    p_proj.set_defaults(func=cmd_project_add_define)

    p_proj = sub.add_parser("project-remove-define", help="从工程移除预处理器定义")
    p_proj.add_argument("project", help="工程根目录路径")
    p_proj.add_argument("define", help="预处理器定义（如 DEBUG）")
    p_proj.add_argument("--json", action="store_true")
    p_proj.set_defaults(func=cmd_project_remove_define)

    p_proj = sub.add_parser("project-remove-group", help="从工程删除空分组")
    p_proj.add_argument("project", help="工程根目录路径")
    p_proj.add_argument("group", help="分组名")
    p_proj.add_argument("--json", action="store_true")
    p_proj.set_defaults(func=cmd_project_remove_group)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except (LibraryError, PlatformError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except CircularDependencyError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except MissingDependencyError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"未预期的错误: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
