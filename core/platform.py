"""平台适配器抽象接口。

所有嵌入式平台的工程操作必须实现 PlatformAdapter 接口。
"""

import os
from typing import Optional


class PlatformError(Exception):
    """平台工程操作相关错误。"""
    pass


class PlatformAdapter:
    """平台适配器抽象基类。

    每个具体平台（Keil MDK、MRS2 等）需继承并实现以下方法。
    """

    def find_project_file(self, project_path: str) -> str:
        """在工程目录中定位工程文件，返回绝对路径。

        Raises:
            PlatformError: 未找到或工程目录不存在。
        """
        raise NotImplementedError

    def register_module(self, project_file: str,
                        module_meta: dict,
                        project_path: str) -> None:
        """将模块注册到工程中。

        自动完成：创建分组 → 注册每个源文件 → 添加 include 路径。

        Args:
            project_file: 工程文件绝对路径（由 find_project_file 返回）。
            module_meta: 模块元数据（module.json 内容）。
            project_path: 工程根目录路径。
        """
        raise NotImplementedError


# ── 适配器注册表 ──────────────────────────────────────

_ADAPTERS: list[type[PlatformAdapter]] = []


def register_adapter(cls: type[PlatformAdapter]):
    """注册一个平台适配器类。"""
    _ADAPTERS.append(cls)


def get_adapter(project_path: str) -> PlatformAdapter:
    """自动检测工程平台类型，返回对应的适配器实例。

    依次尝试每个已注册的适配器的 find_project_file，
    第一个成功找到工程文件的即为匹配的适配器。

    Raises:
        PlatformError: 所有适配器均无法识别该工程。
    """
    for adapter_cls in _ADAPTERS:
        try:
            adapter = adapter_cls()
            adapter.find_project_file(project_path)
            return adapter
        except PlatformError:
            continue
    raise PlatformError(
        f"无法识别工程类型: {project_path}\n"
        f"已注册的适配器: {', '.join(c.__name__ for c in _ADAPTERS) or '(无)'}"
    )
