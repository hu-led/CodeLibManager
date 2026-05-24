"""MounRiver Studio 2 平台适配器。

实现 .cproject (Eclipse CDT XML) 工程文件的读写操作。
MRS2 基于 Eclipse CDT，文件通过文件系统自动发现，无需显式注册。
主要操作：IncludePath 管理、Define 管理、模板初始化。
"""

import os
import shutil
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

from ..platform import PlatformAdapter, PlatformError


# ── 常量 ───────────────────────────────────────────────

# Include paths option 的 id 后缀特征
INCLUDE_PATHS_SUFFIX = "c.compiler.include.paths"
DEFS_SUFFIX = "c.compiler.defs"
ASSEMBLER_INCLUDE_SUFFIX = "assembler.include.paths"

# Eclipse 变量模式
ECLIPSE_VAR_PATTERN = '&quot;${workspace_loc:/${ProjName}/%s}&quot;'


# ── XML 工具 ──────────────────────────────────────────

def _backup_and_write(tree, path):
    shutil.copy2(path, path + f'.bak.{datetime.now().strftime("%Y%m%d_%H%M%S")}')
    tree.write(path, encoding='utf-8', xml_declaration=True)


def _find_option(root, id_suffix):
    """在 XML 树中查找第一个 id 包含 id_suffix 的 option 元素。"""
    for opt in root.iter('option'):
        oid = opt.get('id', '')
        if id_suffix in oid:
            return opt
    return None


def _get_include_option_values(opt):
    """从 include path option 中提取已有的路径值列表。"""
    values = []
    for v in opt.findall('listOptionValue'):
        val = v.get('value', '')
        if val:
            values.append(val)
    return values


def _make_include_value(folder_name):
    """为 MRS2 工程生成 Eclipse 变量格式的 include 路径。"""
    return ECLIPSE_VAR_PATTERN % folder_name


# ── .cproject 操作 ────────────────────────────────────

def _find_cproject(project_path: str) -> str:
    """在工程目录中查找 .cproject 文件。"""
    if not os.path.isdir(project_path):
        raise PlatformError(f"工程目录不存在: {project_path}")
    try:
        cps = [f for f in os.listdir(project_path) if f == '.cproject']
    except OSError as e:
        raise PlatformError(f"无法读取工程目录 {project_path}: {e}")
    if not cps:
        raise PlatformError(f"在 {project_path} 中未找到 .cproject 文件")
    return os.path.join(project_path, cps[0])


def _add_include_path(cproject_path: str, folder_name: str):
    """向 .cproject 的 C 编译器和汇编器添加 include 路径。"""
    try:
        tree = ET.parse(cproject_path)
        root = tree.getroot()

        new_value = _make_include_value(folder_name)
        modified = False

        # C 编译器 include paths
        opt = _find_option(root, INCLUDE_PATHS_SUFFIX)
        if opt is not None:
            existing = _get_include_option_values(opt)
            if new_value not in existing:
                ET.SubElement(opt, 'listOptionValue', {
                    'builtIn': 'false',
                    'value': new_value
                })
                modified = True

        # 汇编器 include paths
        asm_opt = _find_option(root, ASSEMBLER_INCLUDE_SUFFIX)
        if asm_opt is not None:
            existing_asm = _get_include_option_values(asm_opt)
            if new_value not in existing_asm:
                ET.SubElement(asm_opt, 'listOptionValue', {
                    'builtIn': 'false',
                    'value': new_value
                })
                modified = True

        if modified:
            _backup_and_write(tree, cproject_path)
    except PlatformError:
        raise
    except Exception as e:
        raise PlatformError(f"添加 Include Path 失败: {e}")


def _remove_include_path(cproject_path: str, folder_name: str):
    """从 .cproject 移除 include 路径。"""
    try:
        tree = ET.parse(cproject_path)
        root = tree.getroot()

        target_value = _make_include_value(folder_name)
        modified = False

        for suffix in [INCLUDE_PATHS_SUFFIX, ASSEMBLER_INCLUDE_SUFFIX]:
            opt = _find_option(root, suffix)
            if opt is not None:
                for v in opt.findall('listOptionValue'):
                    if v.get('value', '') == target_value:
                        opt.remove(v)
                        modified = True

        if modified:
            _backup_and_write(tree, cproject_path)
    except PlatformError:
        raise
    except Exception as e:
        raise PlatformError(f"移除 Include Path 失败: {e}")


def _add_define(cproject_path: str, define: str):
    """向 .cproject 添加预处理器定义。"""
    try:
        tree = ET.parse(cproject_path)
        root = tree.getroot()

        opt = _find_option(root, DEFS_SUFFIX)
        if opt is None:
            raise PlatformError("未找到 C compiler defines option 节点")

        existing = [v.get('value', '') for v in opt.findall('listOptionValue')]
        if define not in existing:
            ET.SubElement(opt, 'listOptionValue', {
                'builtIn': 'false',
                'value': define
            })
            _backup_and_write(tree, cproject_path)
    except PlatformError:
        raise
    except Exception as e:
        raise PlatformError(f"添加 Define 失败: {e}")


def _remove_define(cproject_path: str, define: str):
    """从 .cproject 移除预处理器定义。"""
    try:
        tree = ET.parse(cproject_path)
        root = tree.getroot()

        opt = _find_option(root, DEFS_SUFFIX)
        if opt is not None:
            for v in opt.findall('listOptionValue'):
                if v.get('value', '') == define:
                    opt.remove(v)
                    _backup_and_write(tree, cproject_path)
                    return
    except PlatformError:
        raise
    except Exception as e:
        raise PlatformError(f"移除 Define 失败: {e}")


def _get_project_name(cproject_path: str) -> str:
    """从 .project 文件获取工程名。"""
    project_dir = os.path.dirname(cproject_path)
    project_file = os.path.join(project_dir, '.project')
    if os.path.isfile(project_file):
        try:
            tree = ET.parse(project_file)
            name_el = tree.getroot().find('name')
            if name_el is not None and name_el.text:
                return name_el.text
        except Exception:
            pass
    return os.path.basename(project_dir)


# ── 适配器类 ──────────────────────────────────────────

class MRS2Adapter(PlatformAdapter):
    """MounRiver Studio 2 平台适配器。

    操作 .cproject (Eclipse CDT XML)，管理 include 路径和预处理器定义。
    文件注册不需要——Eclipse CDT 自动发现文件系统下的源文件。
    工程分组 = 文件系统目录结构。
    """

    # ── PlatformAdapter 接口实现 ──

    def find_project_file(self, project_path: str) -> str:
        return _find_cproject(project_path)

    def register_module(self, project_file: str,
                        module_meta: dict,
                        project_path: str) -> None:
        group = module_meta.get("group", "Hardware")
        group_dir = os.path.join(project_path, group)
        os.makedirs(group_dir, exist_ok=True)

        all_files = (module_meta.get("files", {}).get("source", []) +
                     module_meta.get("files", {}).get("header", []))
        for f in all_files:
            src = os.path.join(group_dir, f) if not os.path.isabs(f) else f
            if not os.path.exists(src):
                raise PlatformError(f"模块文件不存在: {src}")

        self._ensure_source_entry(project_file, group)
        self.add_include_path(project_file, group)

    def _ensure_source_entry(self, project_file: str, group: str) -> None:
        """确保 group 目录在 .cproject sourceEntries 的编译扫描范围内。"""
        try:
            tree = ET.parse(project_file)
            root = tree.getroot()
            modified = False
            for entry in root.iter('sourceEntry') or []:
                excluding = entry.get('excluding', '')
                if not excluding:
                    continue
                parts = [p.strip() for p in excluding.split('|') if p.strip()]
                if group in parts:
                    parts.remove(group)
                    entry.set('excluding', '|'.join(parts) if parts else '')
                    modified = True
            if modified:
                _backup_and_write(tree, project_file)
        except Exception:
            # sourceEntries 不存在或无法解析时，不做破坏性操作
            pass

    # ── 工程结构原子操作 ──

    def add_include_path(self, project_file: str, folder_name: str) -> None:
        """向工程添加 Include 路径（Eclipse 变量格式）。"""
        _add_include_path(project_file, folder_name)

    def remove_include_path(self, project_file: str, folder_name: str) -> None:
        """从工程移除 Include 路径。"""
        _remove_include_path(project_file, folder_name)

    def add_define(self, project_file: str, define: str) -> None:
        """向工程添加预处理器定义。"""
        _add_define(project_file, define)

    def remove_define(self, project_file: str, define: str) -> None:
        """从工程移除预处理器定义。"""
        _remove_define(project_file, define)

    def add_file(self, project_file: str, group_name: str, file_path: str) -> None:
        """MRS2 自动发现源文件，无需显式注册。"""
        project_dir = os.path.dirname(project_file)
        full_path = os.path.join(project_dir, file_path.lstrip('.\\'))
        if not os.path.exists(full_path):
            raise PlatformError(
                f"文件不存在: {full_path}\n"
                f"MRS2/Eclipse CDT 不支持自动创建文件，请先手动创建。"
            )

    def remove_file(self, project_file: str, group_name: str, file_path: str) -> None:
        """MRS2 自动发现源文件，移除即从文件系统删除。"""
        project_dir = os.path.dirname(project_file)
        full_path = os.path.join(project_dir, file_path.lstrip('.\\'))
        if os.path.isfile(full_path):
            os.remove(full_path)

    def create_group(self, project_file: str, group_name: str) -> None:
        """在工程中创建目录（即分组），已存在则跳过。"""
        project_dir = os.path.dirname(project_file)
        group_dir = os.path.join(project_dir, group_name)
        os.makedirs(group_dir, exist_ok=True)

    def remove_group(self, project_file: str, group_name: str) -> None:
        """删除工程中的目录（分组），目录为空才能删除。"""
        project_dir = os.path.dirname(project_file)
        group_dir = os.path.join(project_dir, group_name)
        if not os.path.isdir(group_dir):
            raise PlatformError(f"目录不存在: {group_dir}")
        try:
            os.rmdir(group_dir)
        except OSError:
            contents = os.listdir(group_dir)
            raise PlatformError(
                f"目录 '{group_name}' 不为空（{len(contents)} 个条目），"
                f"请先删除文件再删除目录"
            )
