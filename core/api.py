"""统一 API —— GUI 和 CLI 共享的业务逻辑入口。

所有函数接受 LibraryContext（或通过路径创建），返回纯 Python 数据类型。
不涉及任何 GUI、print 或终端交互。
"""

import json
import os
import shutil
import zipfile
from datetime import date, datetime
from typing import Optional

from .library import LibraryContext, LibraryError
from .dependency import (
    topological_sort,
    reverse_dependencies,
    build_dependency_tree,
    CircularDependencyError,
    MissingDependencyError,
)
from .platform import PlatformError, get_adapter, register_adapter
from .platforms.keil import KeilAdapter
from .platforms.mrs2 import MRS2Adapter
from . import file_ops

# 注册平台适配器
register_adapter(KeilAdapter)
register_adapter(MRS2Adapter)

__all__ = [
    "LibraryContext", "LibraryError",
    "topological_sort", "reverse_dependencies", "build_dependency_tree",
    "CircularDependencyError", "MissingDependencyError",
    "PlatformError", "get_adapter", "check_file_conflicts",
    "list_modules", "get_module_info", "get_dependency_tree",
    "copy_module_to_project", "chain_copy_to_project",
    "import_module", "update_module", "edit_module", "verify_module", "remove_module",
    "add_library", "remove_library", "list_libraries", "switch_library",
    "validate_library", "cleanup_broken_modules",
    "add_category", "rename_category", "delete_category",
    "add_group", "rename_group", "delete_group", "list_groups",
    "rename_library", "update_library_path",
    "load_config", "save_config",
]

CONFIG_PATH = os.path.join(os.environ.get("APPDATA", ""), "CodeLibManager", "config.json")

# ── 安全校验 ─────────────────────────────────────────

def _validate_path_component(name: str, label: str = "名称"):
    """校验路径组件不含 .. 等危险字符，防止路径穿越。"""
    if not name or not name.strip():
        raise LibraryError(f"{label}不能为空")
    if ".." in name or "/" in name or "\\" in name:
        raise LibraryError(f"{label}不能包含 '..', '/' 或 '\\': {name}")
    return name.strip()


# ── 配置管理 ─────────────────────────────────────────

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            # 备份损坏的配置文件，避免数据丢失
            import time
            bak = CONFIG_PATH + f".corrupted.{int(time.time())}"
            try:
                os.rename(CONFIG_PATH, bak)
            except OSError:
                pass
    return {
        "libraries": [],
        "active_library": "",
        "window": {"width": 1200, "height": 800},
    }


def save_config(cfg: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# ── 库管理 ───────────────────────────────────────────

def list_libraries() -> list[dict]:
    cfg = load_config()
    return cfg.get("libraries", [])


def add_library(alias: str, path: str) -> dict:
    if not os.path.isdir(path):
        raise LibraryError(f"库路径不存在或不是目录: {path}")
    cfg = load_config()
    for lib in cfg.get("libraries", []):
        if lib["alias"] == alias:
            raise LibraryError(f"库别名 '{alias}' 已存在")
        if os.path.abspath(lib["path"]) == os.path.abspath(path):
            raise LibraryError(f"库路径 '{path}' 已注册为 '{lib['alias']}'")
    entry = {"alias": alias, "path": os.path.abspath(path)}
    cfg.setdefault("libraries", []).append(entry)
    cfg["active_library"] = alias
    save_config(cfg)
    return entry


def remove_library(alias: str):
    cfg = load_config()
    cfg["libraries"] = [l for l in cfg.get("libraries", []) if l["alias"] != alias]
    if cfg.get("active_library") == alias:
        cfg["active_library"] = cfg["libraries"][0]["alias"] if cfg["libraries"] else ""
    save_config(cfg)


def switch_library(alias: str) -> dict:
    """切换活跃库。"""
    cfg = load_config()
    found = False
    for l in cfg.get("libraries", []):
        if l["alias"] == alias:
            found = True
            break
    if not found:
        raise LibraryError(f"库 '{alias}' 未注册")
    cfg["active_library"] = alias
    save_config(cfg)
    return {"alias": alias, "active": True}


def validate_library(library_alias: str = None) -> list[dict]:
    """检测库完整性问题（缺失文件夹/文件/元数据）。"""
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])
    return ctx.validate()


def cleanup_broken_modules(library_alias: str = None) -> dict:
    """清理所有损坏模块（从索引中移除，清理依赖引用）。"""
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])
    issues = ctx.validate()
    cleaned = []
    names_to_remove = []
    for iss in issues:
        if iss["type"] == "missing_file":
            continue  # 只缺文件的不清理，只清理缺文件夹/元数据的
        name = iss["module"]
        try:
            ctx.find_entry(name)
        except LibraryError:
            continue
        # 清理反向依赖
        rdeps = reverse_dependencies(ctx, name)
        for rdep in rdeps:
            try:
                mod = ctx.load_module(rdep)
                mod["dependencies"] = [d for d in mod.get("dependencies", [])
                                       if d.lower() != name.lower()]
                ctx.save_module(rdep, mod)
            except LibraryError:
                pass
        names_to_remove.append(name)
        cleaned.append({"name": name, "reason": iss["message"], "rdeps_cleaned": rdeps})
    # 一次性从索引移除所有损坏条目
    if names_to_remove:
        remove_lower = {n.lower() for n in names_to_remove}
        idx = ctx.load_index()
        idx = [e for e in idx if e["name"].lower() not in remove_lower]
        ctx.save_index(idx)
    return {"cleaned": cleaned, "count": len(cleaned)}


# ── 模块浏览 ─────────────────────────────────────────

def list_modules(library_alias: str = None, category: str = None,
                 status: str = "all", search: str = None,
                 summary: bool = False) -> list[dict]:
    """列出模块。summary=True 时只返回核心字段以减少 token 消耗。"""
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])
    all_mods = ctx.get_all_modules_meta()

    # 过滤
    if category:
        all_mods = [m for m in all_mods if m["category"].lower() == category.lower()]
    if status == "verified":
        all_mods = [m for m in all_mods if m["verified"]]
    elif status == "unverified":
        all_mods = [m for m in all_mods if not m["verified"]]
    if search:
        q = search.lower()
        all_mods = [m for m in all_mods
                    if q in m["name"].lower() or q in m["description"].lower()]

    all_mods.sort(key=lambda m: (m["category"], m["name"]))

    if summary:
        return [{
            "name": m["name"],
            "category": m["category"],
            "verified": m["verified"],
            "dep_count": m["dep_count"],
        } for m in all_mods]

    return all_mods


def get_module_info(library_alias: str, name: str) -> dict:
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])
    mod = ctx.load_module(name)
    entry = ctx.find_entry(name)
    rdeps = reverse_dependencies(ctx, name)

    return {
        "name": mod["name"],
        "version": mod.get("version", "1.0"),
        "category": mod.get("category", ""),
        "description": mod.get("description", ""),
        "group": mod.get("group", "Hardware"),
        "verified": mod.get("verified", False),
        "verified_date": mod.get("verified_date"),
        "known_issues": mod.get("known_issues", []),
        "notes": mod.get("notes", ""),
        "source_project": mod.get("source_project", ""),
        "files": mod.get("files", {"source": [], "header": []}),
        "dependencies": mod.get("dependencies", []),
        "pins": mod.get("pins", {}),
        "path": entry["path"],
        "reverse_dependencies": rdeps,
    }


def get_dependency_tree(library_alias: str, name: str) -> dict:
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])
    return build_dependency_tree(ctx, name)


# ── 模块操作 ─────────────────────────────────────────

def copy_module_to_project(library_alias: str, module_name: str,
                           project_path: str, dry_run: bool = False) -> dict:
    """单模块复制到工程。"""
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])
    mod = ctx.load_module(module_name)
    entry = ctx.find_entry(module_name)
    source_dir = ctx.get_module_dir(entry)

    result = {
        "module": module_name,
        "group": mod.get("group", "Hardware"),
        "files": mod.get("files", {"source": [], "header": []}),
        "copied": [],
        "registered": [],
    }

    if dry_run:
        return result

    adapter = get_adapter(project_path)
    project_file = adapter.find_project_file(project_path)
    copied = file_ops.copy_module_files(mod, source_dir, project_path)
    adapter.register_module(project_file, mod, project_path)
    result["copied"] = copied
    result["registered"] = [f".\\{mod.get('group', 'Hardware')}\\{f}"
                            for f in (mod.get("files", {}).get("source", []) +
                                      mod.get("files", {}).get("header", []))]
    return result


def chain_copy_to_project(library_alias: str, module_name: str,
                          project_path: str,
                          selected_modules: list[str] = None,
                          dry_run: bool = False,
                          conflict_resolutions: dict = None) -> dict:
    """模块链复制到工程。

    Args:
        selected_modules: 用户勾选的模块名列表，None 表示全部。
        conflict_resolutions: {filename: 'skip'|'overwrite'|'rename'}。
    """
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])

    # 拓扑排序
    full_chain = topological_sort(ctx, module_name)

    # 筛选
    if selected_modules:
        selected_set = {s.lower() for s in selected_modules}
        full_chain = [m for m in full_chain if m["name"].lower() in selected_set]

    # 检查冲突
    conflicts = file_ops.check_file_conflicts(full_chain, project_path)

    result = {
        "module": module_name,
        "chain": full_chain,
        "conflicts": conflicts,
        "copied": [],
    }

    if dry_run:
        return result

    if conflicts and not conflict_resolutions:
        raise PlatformError("存在文件冲突但未提供解决方案")

    conflict_resolutions = conflict_resolutions or {}
    adapter = get_adapter(project_path)
    project_file = adapter.find_project_file(project_path)

    for mod_meta in full_chain:
        mname = mod_meta["name"]
        entry = ctx.find_entry(mname)
        source_dir = ctx.get_module_dir(entry)
        full_mod = ctx.load_module(mname)

        # 复制文件（处理冲突）
        all_files = (mod_meta["files"].get("source", []) +
                     mod_meta["files"].get("header", []))
        group = mod_meta.get("group", "Hardware")
        target_dir = os.path.join(project_path, group)
        os.makedirs(target_dir, exist_ok=True)

        for f in all_files:
            src = os.path.join(source_dir, f)
            dst = os.path.join(target_dir, f)
            resolution = conflict_resolutions.get(f, "skip")
            if os.path.exists(dst):
                if resolution == "skip":
                    continue
                elif resolution == "overwrite":
                    backup = dst + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    shutil.copy2(dst, backup)
                elif resolution == "rename":
                    base, ext = os.path.splitext(f)
                    f = f"{base}_{mname}{ext}"
                    dst = os.path.join(target_dir, f)
            if os.path.exists(src):
                shutil.copy2(src, dst)
                result["copied"].append(dst)

        adapter.register_module(project_file, full_mod, project_path)

    return result


def import_module(library_alias: str, file_paths: list[str],
                  name: str, category: str = "Other",
                  version: str = "1.0", description: str = "",
                  dependencies: list[str] = None,
                  group: str = "Hardware", pins: dict = None,
                  ) -> dict:
    """导入新模块到代码库。

    Args:
        file_paths: 要导入的 .c/.h 文件绝对路径列表。
    """
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])

    if ctx.module_exists(name):
        raise LibraryError(f"模块 '{name}' 已存在")

    # 校验路径安全
    name = _validate_path_component(name, "模块名")
    category = _validate_path_component(category, "分类名")

    # 创建模块目录
    cat_dir = os.path.join(ctx.root, category)
    os.makedirs(cat_dir, exist_ok=True)
    mod_dir = os.path.join(cat_dir, name)
    os.makedirs(mod_dir, exist_ok=True)

    # 复制文件（只复制 .c/.h 文件）
    source_files = []
    header_files = []
    skipped = []
    for src in file_paths:
        if not os.path.exists(src):
            skipped.append(f"{src} (不存在)")
            continue
        f = os.path.basename(src)
        ext = os.path.splitext(f)[1].lower()
        if ext not in ('.c', '.h'):
            skipped.append(f"{src} (不是 .c/.h 文件)")
            continue
        dst = os.path.join(mod_dir, f)
        shutil.copy2(src, dst)
        if ext == '.c':
            source_files.append(f)
        else:
            header_files.append(f)

    if not source_files and not header_files:
        raise LibraryError(f"没有导入任何 .c/.h 文件。跳过的文件: {', '.join(skipped) if skipped else '无有效文件'}")

    # 写入 module.json
    mod_data = {
        "name": name,
        "version": version,
        "category": category,
        "description": description,
        "files": {"source": source_files, "header": header_files},
        "dependencies": dependencies or [],
        "group": group,
        "pins": pins or {},
        "verified": False,
        "verified_date": None,
        "known_issues": [],
        "source_project": "",
    }
    # 先写 module.json，再更新索引（避免出现索引指向不存在的 module.json）
    mod_json_path = os.path.join(mod_dir, "module.json")
    with open(mod_json_path, "w", encoding="utf-8") as f:
        json.dump(mod_data, f, indent=2, ensure_ascii=False)

    idx = ctx.load_index()
    idx.append({
        "name": name,
        "category": category,
        "path": f"{category}/{name}",
        "description": description,
    })
    ctx.save_index(idx)

    return mod_data


def update_module(library_alias: str, name: str,
                  source_dir: str, from_project: bool = False,
                  auto_verify: bool = True) -> dict:
    """替换式更新模块：备份旧版、复制新文件、更新元数据。

    Args:
        from_project: True 时 source_dir 是工程根路径，文件位置为 source_dir/<group>/<file>。
        auto_verify: 是否自动标记为已验证。
    """
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])
    old_mod = ctx.load_module(name)
    entry = ctx.find_entry(name)
    mod_dir = ctx.get_module_dir(entry)
    group = old_mod.get("group", "Hardware")

    # 快照备份
    snapshot_dir = ctx.snapshot_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"{name}_{timestamp}.zip"
    zip_path = os.path.join(snapshot_dir, zip_name)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(mod_dir):
            for f in files:
                fp = os.path.join(root, f)
                zf.write(fp, os.path.relpath(fp, mod_dir))
        zf.writestr("module.json.bak", json.dumps(old_mod, indent=2, ensure_ascii=False))

    # 定位源文件
    all_files = old_mod.get("files", {}).get("source", []) + old_mod.get("files", {}).get("header", [])
    skipped_files = []

    if not from_project and not os.path.isdir(source_dir):
        raise LibraryError(f"源目录不存在或不是目录: {source_dir}")

    if from_project:
        # 从工程目录反向同步：source_dir/<group>/<file>
        for f in all_files:
            src = os.path.join(source_dir, group, f)
            dst = os.path.join(mod_dir, f)
            if os.path.exists(src):
                shutil.copy2(src, dst)
            else:
                skipped_files.append(f)
    else:
        # 从源目录复制新的 .c/.h 文件
        source_files = []
        header_files = []
        if os.path.isdir(source_dir):
            for f in os.listdir(source_dir):
                ext = os.path.splitext(f)[1].lower()
                if ext == '.c':
                    source_files.append(f)
                elif ext == '.h':
                    header_files.append(f)
                if ext in ('.c', '.h'):
                    shutil.copy2(os.path.join(source_dir, f), os.path.join(mod_dir, f))
            old_mod["files"] = {"source": source_files, "header": header_files}
        # 如果 source_dir 不是有效目录，保留原有文件列表不变

    old_mod["last_updated"] = timestamp

    if auto_verify:
        old_mod["verified"] = True
        old_mod["verified_date"] = date.today().isoformat()
        old_mod["known_issues"] = []

    ctx.save_module(name, old_mod)

    idx = ctx.load_index()
    for e in idx:
        if e["name"].lower() == name.lower():
            e["description"] = old_mod.get("description", e.get("description", ""))
            break
    ctx.save_index(idx)

    return {
        "name": name,
        "snapshot": zip_name,
        "auto_verified": auto_verify,
        "skipped_files": skipped_files,
    }


def edit_module(library_alias: str, name: str,
                new_name: str = None,
                new_category: str = None,
                new_version: str = None,
                new_description: str = None,
                new_group: str = None,
                new_pins: dict = None,
                new_verified: bool = None,
                new_dependencies: list[str] = None,
                add_files: list[str] = None,
                remove_files: list[str] = None,
                ) -> dict:
    """编辑模块元数据和文件。

    只对实际传入的参数执行变更，未传入的字段保持不变。
    - new_name: 重命名模块（同步更新索引和其他模块的依赖引用）
    - new_category: 移动模块到新分类目录
    - new_version: 版本变化时自动创建快照
    - add_files: 要添加的文件绝对路径列表
    - remove_files: 要从模块目录删除的文件名列表
    """
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])
    old_mod = ctx.load_module(name)
    entry = ctx.find_entry(name)
    old_dir = ctx.get_module_dir(entry)

    version_changed = new_version is not None and new_version != old_mod.get("version")
    name_changed = new_name is not None and new_name.lower() != name.lower()
    cat_changed = new_category is not None and new_category != old_mod.get("category", "")

    # 检查新名称不冲突
    if name_changed and ctx.module_exists(new_name):
        raise LibraryError(f"模块 '{new_name}' 已存在")

    # ── 快照 ──
    snapshot = None
    if version_changed:
        snapshot_dir = ctx.snapshot_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_name_snap = f"{name}_{timestamp}.zip"
        zip_path = os.path.join(snapshot_dir, zip_name_snap)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(old_dir):
                for f in files:
                    fp = os.path.join(root, f)
                    zf.write(fp, os.path.relpath(fp, old_dir))
            zf.writestr("module.json.bak",
                        json.dumps(old_mod, indent=2, ensure_ascii=False))
        snapshot = zip_name_snap

    # ── 目录移动 ──
    effective_name = new_name if name_changed else name
    effective_cat = new_category if cat_changed else old_mod.get("category", "")
    effective_name = _validate_path_component(effective_name, "模块名")
    effective_cat = _validate_path_component(effective_cat, "分类名")
    new_cat_dir = os.path.join(ctx.root, effective_cat)
    os.makedirs(new_cat_dir, exist_ok=True)
    new_dir = os.path.join(new_cat_dir, effective_name)

    if name_changed or cat_changed:
        if os.path.exists(old_dir):
            if os.path.exists(new_dir):
                raise LibraryError(f"目标路径已存在: {new_dir}")
            shutil.move(old_dir, new_dir)
        # 更新索引中的 path
        idx = ctx.load_index()
        for e in idx:
            if e["name"].lower() == name.lower():
                e["name"] = effective_name
                e["path"] = f"{effective_cat}/{effective_name}"
                e["category"] = effective_cat
                break
        ctx.save_index(idx)
        # 更新其他模块对旧名称的依赖引用
        if name_changed:
            for e in idx:
                if e["name"].lower() == effective_name.lower():
                    continue
                dep_mod = ctx.load_module(e["name"])
                deps = dep_mod.get("dependencies", [])
                if any(d.lower() == name.lower() for d in deps):
                    dep_mod["dependencies"] = [
                        effective_name if d.lower() == name.lower() else d for d in deps
                    ]
                    ctx.save_module(e["name"], dep_mod)

    # ── 文件变更 ──
    target_dir = new_dir if (name_changed or cat_changed) else old_dir

    if remove_files:
        for f in remove_files:
            fp = os.path.join(target_dir, f)
            if os.path.exists(fp):
                os.remove(fp)

    if add_files:
        for src in add_files:
            if not os.path.exists(src):
                continue
            dst = os.path.join(target_dir, os.path.basename(src))
            shutil.copy2(src, dst)

    # ── 重新扫描文件 ──
    source_files = []
    header_files = []
    if os.path.isdir(target_dir):
        for f in sorted(os.listdir(target_dir)):
            ext = os.path.splitext(f)[1].lower()
            if ext == '.c':
                source_files.append(f)
            elif ext == '.h':
                header_files.append(f)

    # ── 更新 module.json ──
    if new_version is not None:
        old_mod["version"] = new_version
    if new_description is not None:
        old_mod["description"] = new_description
    if new_group is not None:
        old_mod["group"] = new_group
    if new_pins is not None:
        old_mod["pins"] = new_pins
    if new_verified is not None:
        old_mod["verified"] = new_verified
        if new_verified:
            old_mod["verified_date"] = date.today().isoformat()
    if new_dependencies is not None:
        old_mod["dependencies"] = new_dependencies
    old_mod["name"] = effective_name
    old_mod["category"] = effective_cat
    old_mod["files"] = {"source": source_files, "header": header_files}
    old_mod["last_updated"] = datetime.now().strftime("%Y%m%d_%H%M%S")

    ctx.save_module(effective_name, old_mod)

    return {
        "name": effective_name,
        "old_name": name if name_changed else None,
        "snapshot": snapshot,
        "files": old_mod["files"],
    }


def verify_module(library_alias: str, name: str,
                  status: str, notes: str = "") -> dict:
    """设置模块验证状态。

    Args:
        status: 'passed' 或 'failed'
    """
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])
    mod = ctx.load_module(name)

    status = status.lower().strip()
    if status == "passed":
        mod["verified"] = True
        mod["verified_date"] = date.today().isoformat()
        mod["known_issues"] = []
        if notes:
            mod["notes"] = notes
    elif status == "failed":
        mod["verified"] = False
        mod["verified_date"] = None
        mod.setdefault("known_issues", [])
        if notes:
            mod["known_issues"].append(notes)
    else:
        raise LibraryError(f"无效状态: {status}，应为 passed 或 failed")

    ctx.save_module(name, mod)
    return {"name": name, "status": status, "verified": mod["verified"]}


def remove_module(library_alias: str, name: str,
                  cleanup_deps: bool = True) -> dict:
    """移除模块到 _trash/，并清理其他模块中对该模块的依赖引用。"""
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])
    entry = ctx.find_entry(name)
    mod_dir = ctx.get_module_dir(entry)

    # 查找反向依赖
    rdeps = reverse_dependencies(ctx, name)

    if cleanup_deps:
        for rdep in rdeps:
            mod = ctx.load_module(rdep)
            mod["dependencies"] = [d for d in mod.get("dependencies", [])
                                   if d.lower() != name.lower()]
            ctx.save_module(rdep, mod)

    # 移动文件夹（如还存在）
    moved_to = None
    if os.path.isdir(mod_dir):
        trash = ctx.trash_dir()
        dest = os.path.join(trash, name)
        if os.path.exists(dest):
            dest = os.path.join(trash, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        shutil.move(mod_dir, dest)
        moved_to = dest

    # 更新索引
    idx = ctx.load_index()
    idx = [e for e in idx if e["name"].lower() != name.lower()]
    ctx.save_index(idx)

    return {
        "name": name,
        "moved_to": moved_to,
        "reverse_deps_cleaned": rdeps if cleanup_deps else [],
    }


# ── 分类管理 ────────────────────────────────────────

def add_category(library_alias: str, name: str) -> dict:
    """在库根目录创建分类文件夹。"""
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])
    name = _validate_path_component(name, "分类名")
    cat_dir = os.path.join(ctx.root, name)
    if os.path.exists(cat_dir):
        raise LibraryError(f"分类 '{name}' 已存在")
    os.makedirs(cat_dir)
    return {"name": name, "path": cat_dir}


def rename_category(library_alias: str, old_name: str, new_name: str) -> dict:
    """重命名分类文件夹，同步更新索引和所有 module.json。"""
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])
    old_name = _validate_path_component(old_name, "原分类名")
    new_name = _validate_path_component(new_name, "新分类名")
    old_dir = os.path.join(ctx.root, old_name)
    new_dir = os.path.join(ctx.root, new_name)
    if not os.path.isdir(old_dir):
        raise LibraryError(f"分类文件夹不存在: {old_dir}")
    if os.path.exists(new_dir):
        raise LibraryError(f"目标分类 '{new_name}' 已存在")
    os.rename(old_dir, new_dir)

    # 更新索引
    idx = ctx.load_index()
    affected = []
    for e in idx:
        if e.get("category", "") == old_name:
            e["category"] = new_name
            e["path"] = f"{new_name}/{e['name']}"
            affected.append(e["name"])
    ctx.save_index(idx)

    # 更新每个受影响的 module.json
    for name in affected:
        mod = ctx.load_module(name)
        mod["category"] = new_name
        ctx.save_module(name, mod)

    return {"old": old_name, "new": new_name, "affected_modules": affected}


def delete_category(library_alias: str, name: str) -> dict:
    """删除空分类文件夹。有模块则失败并列出模块名。"""
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])
    name = _validate_path_component(name, "分类名")
    cat_dir = os.path.join(ctx.root, name)
    if not os.path.isdir(cat_dir):
        raise LibraryError(f"分类文件夹不存在: {cat_dir}")

    idx = ctx.load_index()
    occupants = [e["name"] for e in idx if e.get("category", "") == name]
    if occupants:
        raise LibraryError(
            f"分类 '{name}' 中仍有 {len(occupants)} 个模块，无法删除:\n  "
            + ", ".join(occupants)
        )
    # 检查文件夹是否真的为空（包括隐藏文件）
    contents = os.listdir(cat_dir)
    if contents:
        raise LibraryError(f"分类文件夹 '{name}' 非空，包含: {', '.join(contents)}")
    os.rmdir(cat_dir)
    return {"name": name, "deleted": True}


# ── 分组管理 ────────────────────────────────────────

def list_groups(library_alias: str) -> list[str]:
    """获取库的工程分组列表。"""
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])
    return ctx.list_groups()


def add_group(library_alias: str, name: str) -> dict:
    """添加工程分组词条。"""
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])
    config = ctx.load_codelib_config()
    groups = config.setdefault("groups", [])
    if name in groups:
        raise LibraryError(f"分组 '{name}' 已存在")
    groups.append(name)
    groups.sort()
    ctx.save_codelib_config(config)
    return {"name": name, "groups": groups}


def rename_group(library_alias: str, old_name: str, new_name: str) -> dict:
    """重命名工程分组，同步更新所有 module.json。"""
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])
    config = ctx.load_codelib_config()
    groups = config.setdefault("groups", [])
    if old_name not in groups:
        raise LibraryError(f"分组 '{old_name}' 不存在")
    if new_name in groups:
        raise LibraryError(f"分组 '{new_name}' 已存在")
    groups[groups.index(old_name)] = new_name
    groups.sort()
    ctx.save_codelib_config(config)

    # 更新所有使用旧分组的 module.json
    idx = ctx.load_index()
    affected = []
    for e in idx:
        mod = ctx.load_module(e["name"])
        if mod.get("group") == old_name:
            mod["group"] = new_name
            ctx.save_module(e["name"], mod)
            affected.append(e["name"])

    return {"old": old_name, "new": new_name, "groups": groups, "affected_modules": affected}


def delete_group(library_alias: str, name: str) -> dict:
    """删除工程分组。有模块使用则失败并列出模块名。"""
    lib = _get_library(library_alias)
    ctx = LibraryContext(lib["path"])
    config = ctx.load_codelib_config()
    groups = config.setdefault("groups", [])
    if name not in groups:
        raise LibraryError(f"分组 '{name}' 不存在")

    # 检查是否有模块在用
    idx = ctx.load_index()
    users = []
    for e in idx:
        try:
            mod = ctx.load_module(e["name"])
            if mod.get("group") == name:
                users.append(e["name"])
        except LibraryError:
            pass
    if users:
        raise LibraryError(
            f"分组 '{name}' 仍被 {len(users)} 个模块使用，无法删除:\n  "
            + ", ".join(users)
        )

    groups.remove(name)
    ctx.save_codelib_config(config)
    return {"name": name, "groups": groups, "deleted": True}


# ── 库管理 ──────────────────────────────────────────

def rename_library(alias: str, new_alias: str) -> dict:
    """重命名库别名（不涉及物理路径）。"""
    cfg = load_config()
    found = False
    for l in cfg.get("libraries", []):
        if l["alias"] == new_alias:
            raise LibraryError(f"库别名 '{new_alias}' 已存在")
        if l["alias"] == alias:
            l["alias"] = new_alias
            found = True
    if not found:
        raise LibraryError(f"库 '{alias}' 不存在")
    if cfg.get("active_library") == alias:
        cfg["active_library"] = new_alias
    save_config(cfg)
    return {"old_alias": alias, "new_alias": new_alias}


def update_library_path(alias: str, new_path: str) -> dict:
    """更新库的物理路径（不移动文件系统）。"""
    if not os.path.isdir(new_path):
        raise LibraryError(f"路径不存在: {new_path}")
    cfg = load_config()
    found = False
    for l in cfg.get("libraries", []):
        if l["alias"] == alias:
            l["path"] = os.path.abspath(new_path)
            found = True
            break
    if not found:
        raise LibraryError(f"库 '{alias}' 不存在")
    save_config(cfg)
    return {"alias": alias, "path": new_path}


# ── 内部辅助 ─────────────────────────────────────────

def _get_library(alias: str = None) -> dict:
    cfg = load_config()
    libs = cfg.get("libraries", [])
    if not libs:
        raise LibraryError("没有注册的库，请先添加库")

    target = alias or cfg.get("active_library") or libs[0]["alias"]
    for l in libs:
        if l["alias"] == target:
            return l
    raise LibraryError(f"库 '{target}' 未找到")
