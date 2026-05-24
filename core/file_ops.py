"""平台无关的文件操作：复制、冲突检测。"""

import os
import shutil
from typing import Optional


def copy_module_files(module_meta: dict,
                      source_dir: str,
                      project_path: str) -> list[str]:
    """复制模块文件到工程目录。返回已复制的目标文件路径列表。"""
    group = module_meta.get("group", "Hardware")
    target_dir = os.path.join(project_path, group)
    os.makedirs(target_dir, exist_ok=True)

    all_files = (module_meta.get("files", {}).get("source", []) +
                 module_meta.get("files", {}).get("header", []))
    copied = []

    for f in all_files:
        src = os.path.join(source_dir, f)
        dst = os.path.join(target_dir, f)
        if not os.path.exists(src):
            raise FileNotFoundError(f"源文件不存在: {src}")
        if os.path.exists(dst):
            backup = dst + ".bak"
            shutil.copy2(dst, backup)
        shutil.copy2(src, dst)
        copied.append(dst)

    return copied


def check_file_conflicts(chain: list[dict], project_path: str) -> list[dict]:
    """检查链复制时的文件冲突。返回冲突列表。"""
    conflicts = []
    seen: dict[str, str] = {}  # filename -> module_name

    for mod in chain:
        group = mod.get("group", "Hardware")
        all_files = (mod.get("files", {}).get("source", []) +
                     mod.get("files", {}).get("header", []))
        for f in all_files:
            dst = os.path.join(project_path, group, f)
            if f in seen and seen[f].lower() != mod["name"].lower():
                conflicts.append({
                    "file": f,
                    "module_a": seen[f],
                    "module_b": mod["name"],
                    "group": group,
                })
            elif os.path.exists(dst) and f not in seen:
                conflict_mod = _guess_owning_module(dst, chain)
                if conflict_mod.lower() != mod["name"].lower():
                    conflicts.append({
                        "file": f,
                        "module_a": conflict_mod or "(工程已有)",
                        "module_b": mod["name"],
                        "group": group,
                    })
            if f not in seen:
                seen[f] = mod["name"]

    return conflicts


def _guess_owning_module(filepath: str, chain: list[dict]) -> Optional[str]:
    """猜测已存在文件可能属于链中的哪个模块。"""
    filename = os.path.basename(filepath)
    for mod in chain:
        all_files = (mod.get("files", {}).get("source", []) +
                     mod.get("files", {}).get("header", []))
        if filename in all_files:
            return mod["name"]
    return None
