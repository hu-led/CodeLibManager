"""代码库管理：LibraryContext + 加载/保存/搜索。"""

import json
import os
from datetime import date


class LibraryError(Exception):
    """库操作相关错误。"""
    pass


def _suggest(target: str, candidates: list[str], max_distance: int = 2) -> list[str]:
    """返回与 target 编辑距离 ≤ max_distance 的候选列表，按距离排序。"""
    t = target.lower()
    results = []
    for c in candidates:
        d = _levenshtein(t, c.lower())
        if d <= max_distance:
            results.append((d, c))
    results.sort(key=lambda x: x[0])
    return [c for _, c in results[:3]]


def _levenshtein(a: str, b: str) -> int:
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = list(range(m + 1))
    curr = [0] * (m + 1)
    for i in range(1, n + 1):
        curr[0] = i
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev, curr = curr, prev
    return prev[m]


class LibraryContext:
    """封装一个代码库的路径与基本 I/O 操作。"""

    def __init__(self, root_path: str):
        self.root = os.path.abspath(root_path)
        self.modules_json_path = os.path.join(self.root, "modules.json")
        if not os.path.isdir(self.root):
            raise LibraryError(f"库目录不存在: {self.root}")

    # ── 索引 ──────────────────────────────────────────

    def load_index(self) -> list[dict]:
        if not os.path.exists(self.modules_json_path):
            return []
        try:
            with open(self.modules_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise LibraryError(f"读取 modules.json 失败: {e}")

    def save_index(self, data: list[dict]):
        with open(self.modules_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def find_entry(self, name: str) -> dict:
        idx = self.load_index()
        for entry in idx:
            if entry["name"].lower() == name.lower():
                return entry
        # 模糊匹配建议
        suggestions = _suggest(name, [e["name"] for e in idx])
        msg = f"模块 '{name}' 未在索引中找到"
        if suggestions:
            msg += f"，你是不是想找: {', '.join(suggestions)}"
        raise LibraryError(msg)

    # ── 模块元数据 ────────────────────────────────────

    def get_module_dir(self, entry: dict) -> str:
        return os.path.join(self.root, entry["path"])

    def load_module(self, name: str) -> dict:
        entry = self.find_entry(name)
        mod_path = os.path.join(self.get_module_dir(entry), "module.json")
        if not os.path.exists(mod_path):
            raise LibraryError(f"module.json 缺失: {mod_path}")
        try:
            with open(mod_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise LibraryError(f"读取 {name}/module.json 失败: {e}")

    def save_module(self, name: str, data: dict):
        entry = self.find_entry(name)
        mod_path = os.path.join(self.get_module_dir(entry), "module.json")
        with open(mod_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ── 辅助 ──────────────────────────────────────────

    def list_categories(self) -> list[str]:
        idx = self.load_index()
        cats = set(e.get("category", "") for e in idx)
        # 合并磁盘上实际存在的文件夹（排除隐藏/特殊目录）
        skip = {".snapshots", "_trash", "__pycache__", ".git", ".codelib.json"}
        try:
            for name in os.listdir(self.root):
                full = os.path.join(self.root, name)
                if os.path.isdir(full) and not name.startswith(".") and name not in skip:
                    cats.add(name)
        except OSError:
            pass
        return sorted(c for c in cats if c)

    def module_exists(self, name: str) -> bool:
        try:
            self.find_entry(name)
            return True
        except LibraryError:
            return False

    def get_all_modules_meta(self) -> list[dict]:
        """返回所有模块的合并信息（索引 + module.json 关键字段）。"""
        idx = self.load_index()
        results = []
        for entry in idx:
            broken = False
            try:
                mod = self.load_module(entry["name"])
            except LibraryError:
                mod = {}
                broken = True
            # 额外检查：模块文件夹是否还在
            if not broken and not os.path.isdir(self.get_module_dir(entry)):
                broken = True
            results.append({
                "name": entry["name"],
                "category": entry.get("category", ""),
                "path": entry.get("path", ""),
                "description": mod.get("description", entry.get("description", "")),
                "version": mod.get("version", "1.0"),
                "group": mod.get("group", "Hardware"),
                "verified": mod.get("verified", False),
                "verified_date": mod.get("verified_date"),
                "dependencies": mod.get("dependencies", []),
                "dep_count": len(mod.get("dependencies", [])),
                "files": mod.get("files", {"source": [], "header": []}),
                "pins": mod.get("pins", {}),
                "known_issues": mod.get("known_issues", []),
                "notes": mod.get("notes", ""),
                "broken": broken,
            })
        return results

    def validate(self) -> list[dict]:
        """检测库完整性问题，返回问题列表。"""
        issues = []
        try:
            idx = self.load_index()
        except Exception:
            return issues

        for entry in idx:
            name = entry["name"]
            mod_dir = self.get_module_dir(entry)

            if not os.path.isdir(mod_dir):
                issues.append({
                    "type": "missing_dir",
                    "module": name,
                    "message": f"模块 '{name}' 的文件夹不存在: {mod_dir}",
                })
                continue

            mod_json = os.path.join(mod_dir, "module.json")
            if not os.path.exists(mod_json):
                issues.append({
                    "type": "missing_metadata",
                    "module": name,
                    "message": f"模块 '{name}' 的 module.json 缺失",
                })
                continue

            try:
                mod = self.load_module(name)
            except Exception:
                continue

            for f in mod.get("files", {}).get("source", []) + mod.get("files", {}).get("header", []):
                if not os.path.exists(os.path.join(mod_dir, f)):
                    issues.append({
                        "type": "missing_file",
                        "module": name,
                        "message": f"模块 '{name}' 缺少文件: {f}",
                    })

        return issues

    def snapshot_dir(self) -> str:
        p = os.path.join(self.root, ".snapshots")
        os.makedirs(p, exist_ok=True)
        return p

    def trash_dir(self) -> str:
        p = os.path.join(self.root, "_trash")
        os.makedirs(p, exist_ok=True)
        return p

    # ── 库配置 (.codelib.json) ─────────────────────────

    @property
    def codelib_config_path(self) -> str:
        return os.path.join(self.root, ".codelib.json")

    def load_codelib_config(self) -> dict:
        """读 .codelib.json，不存在则自动初始化。"""
        if os.path.exists(self.codelib_config_path):
            try:
                with open(self.codelib_config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        data = {"groups": ["Hardware", "System"]}
        self.save_codelib_config(data)
        return data

    def save_codelib_config(self, data: dict):
        os.makedirs(os.path.dirname(self.codelib_config_path), exist_ok=True)
        with open(self.codelib_config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def list_groups(self) -> list[str]:
        return self.load_codelib_config().get("groups", [])
