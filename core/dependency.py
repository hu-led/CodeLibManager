"""依赖解析：拓扑排序、循环检测、反向依赖查询。"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .library import LibraryContext


class CircularDependencyError(Exception):
    def __init__(self, cycle: list[str]):
        self.cycle = cycle
        super().__init__(f"检测到循环依赖: {' → '.join(cycle)}")


class MissingDependencyError(Exception):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(f"依赖的模块不存在: {', '.join(missing)}")


def topological_sort(ctx: LibraryContext, module_name: str) -> list[dict]:
    """
    Kahn 算法拓扑排序，返回按依赖顺序排列的模块信息列表（被依赖的先返回）。

    Raises:
        CircularDependencyError: 存在循环依赖
        MissingDependencyError: 依赖的模块在库中不存在
    """
    # 递归收集所有涉及的模块
    all_names = set()
    _collect_deps(ctx, module_name, all_names, set())

    # 构建邻接表 (A -> B 表示 A 依赖 B, B 先于 A)
    in_degree: dict[str, int] = {}
    adj: dict[str, list[str]] = {}  # B -> [A, ...]  (B 被哪些模块依赖)

    for name in all_names:
        in_degree[name] = 0
        adj[name] = []

    # 大小写不敏感依赖匹配
    name_lower = {n.lower(): n for n in all_names}

    for name in all_names:
        mod = ctx.load_module(name)
        deps = mod.get("dependencies", [])
        for dep in deps:
            canonical = name_lower.get(dep.lower())
            if canonical and canonical in adj:
                adj[canonical].append(name)
        in_degree[name] = sum(1 for d in deps if name_lower.get(d.lower()) in adj)

    # Kahn's algorithm
    queue = deque([n for n, d in in_degree.items() if d == 0])
    sorted_names = []

    while queue:
        node = queue.popleft()
        sorted_names.append(node)
        for dependent in adj.get(node, []):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(sorted_names) != len(all_names):
        # 存在循环依赖，找出循环路径
        remaining = all_names - set(sorted_names)
        cycle = _find_cycle(adj, in_degree, remaining)
        raise CircularDependencyError(cycle)

    # 加载每个模块的元数据
    result = []
    for name in sorted_names:
        mod = ctx.load_module(name)
        result.append({
            "name": name,
            "group": mod.get("group", "Hardware"),
            "category": mod.get("category", ""),
            "files": mod.get("files", {"source": [], "header": []}),
            "version": mod.get("version", "1.0"),
            "verified": mod.get("verified", False),
        })

    return result


def _collect_deps(ctx: LibraryContext, name: str, all_names: set, visited: set):
    """递归收集模块及其传递依赖。MissingDependencyError 直接抛出。"""
    name_lower = name.lower()
    if name_lower in visited:
        return
    visited.add(name_lower)
    mod = ctx.load_module(name)
    all_names.add(mod["name"])  # 使用注册名称（规范化大小写）
    missing = []
    for dep in mod.get("dependencies", []):
        if not ctx.module_exists(dep):
            missing.append(dep)
    if missing:
        raise MissingDependencyError(missing)
    for dep in mod.get("dependencies", []):
        _collect_deps(ctx, dep, all_names, visited)


def _find_cycle(adj: dict[str, list[str]], in_degree: dict[str, int],
                remaining: set[str]) -> list[str]:
    """在剩余节点中通过 DFS 找到一个环。"""
    for start in remaining:
        path = []
        visited = set()

        def dfs(node):
            if node in path:
                idx = path.index(node)
                return path[idx:] + [node]
            if node in visited:
                return None
            visited.add(node)
            path.append(node)
            for nxt in adj.get(node, []):
                if nxt in remaining or nxt in path:
                    result = dfs(nxt)
                    if result:
                        return result
            path.pop()
            return None

        cycle = dfs(start)
        if cycle:
            return cycle
    return list(remaining)


def reverse_dependencies(ctx: LibraryContext, module_name: str) -> list[str]:
    """查找所有依赖指定模块的其他模块（反向依赖）。"""
    all_mods = ctx.get_all_modules_meta()
    rdeps = []
    for m in all_mods:
        if m["name"].lower() == module_name.lower():
            continue
        deps = [d.lower() for d in m.get("dependencies", [])]
        if module_name.lower() in deps:
            rdeps.append(m["name"])
    return sorted(rdeps)


def build_dependency_tree(ctx: LibraryContext, module_name: str) -> dict:
    """构建模块的依赖树（用于前端展示）。"""
    mod = ctx.load_module(module_name)

    def _node(name, visited):
        if name.lower() in visited:
            return {"name": name, "verified": False, "group": "?", "dependencies": [], "_cycle": True}
        visited.add(name.lower())
        m = ctx.load_module(name)
        children = []
        for d in m.get("dependencies", []):
            children.append(_node(d, visited))
        visited.discard(name.lower())
        return {
            "name": name,
            "verified": m.get("verified", False),
            "group": m.get("group", "Hardware"),
            "dependencies": children,
        }

    visited = {module_name.lower()}
    return {
        "name": module_name,
        "verified": mod.get("verified", False),
        "group": mod.get("group", "Hardware"),
        "dependencies": [_node(d, visited) for d in mod.get("dependencies", [])],
    }
