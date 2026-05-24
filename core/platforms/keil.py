"""Keil MDK-ARM 平台适配器。

实现 uvprojx 工程文件的读写操作。
"""

import os
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime

from ..platform import PlatformAdapter, PlatformError


# ── XML 命名空间工具 ──────────────────────────────────

def _extract_namespace(root):
    if '}' in (root.tag or ''):
        return root.tag.split('}', 1)[0].lstrip('{')
    return ''


def _strip_namespace(elem):
    for el in elem.iter():
        if '}' in (el.tag or ''):
            el.tag = el.tag.split('}', 1)[1]


def _restore_and_write(tree, path, ns_uri):
    if ns_uri:
        for el in tree.getroot().iter():
            if not el.tag.startswith('{'):
                el.tag = f'{{{ns_uri}}}{el.tag}'
        ET.register_namespace('', ns_uri)
    shutil.copy2(path, path + f'.bak.{datetime.now().strftime("%Y%m%d_%H%M%S")}')
    tree.write(path, encoding='utf-8', xml_declaration=True)


# ── uvprojx 操作 ─────────────────────────────────────

def _find_uvprojx(project_path: str) -> str:
    """在目录中查找 .uvprojx 文件。"""
    if not os.path.isdir(project_path):
        raise PlatformError(f"工程目录不存在: {project_path}")
    try:
        uvs = [f for f in os.listdir(project_path) if f.endswith('.uvprojx')]
    except OSError as e:
        raise PlatformError(f"无法读取工程目录 {project_path}: {e}")
    if not uvs:
        raise PlatformError(f"在 {project_path} 中未找到 .uvprojx 文件")
    return os.path.join(project_path, uvs[0])


def _create_group(uvprojx_path: str, group_name: str):
    """在 uvprojx 中创建分组（如已存在则跳过）。"""
    try:
        tree = ET.parse(uvprojx_path)
        root = tree.getroot()
        ns_uri = _extract_namespace(root)
        _strip_namespace(root)

        groups = root.find('.//Targets/Target/Groups')
        if groups is None:
            raise PlatformError("未找到 Groups 节点")

        for g in groups.findall('Group'):
            name_elem = g.find('GroupName')
            if name_elem is not None and name_elem.text == group_name:
                return

        new_group = ET.SubElement(groups, 'Group')
        ET.SubElement(new_group, 'GroupName').text = group_name
        ET.SubElement(new_group, 'Files')
        _restore_and_write(tree, uvprojx_path, ns_uri)
    except PlatformError:
        raise
    except Exception as e:
        raise PlatformError(f"创建分组失败: {e}")


def _add_file(uvprojx_path: str, group_name: str, file_path: str):
    """向 uvprojx 的指定分组添加文件（如已注册则跳过）。"""
    try:
        tree = ET.parse(uvprojx_path)
        root = tree.getroot()
        ns_uri = _extract_namespace(root)
        _strip_namespace(root)

        groups = root.find('Targets/Target/Groups')
        if groups is None:
            raise PlatformError("未找到 Targets/Target/Groups 节点")

        group = None
        for g in groups.findall('Group'):
            name_elem = g.find('GroupName')
            if name_elem is not None and name_elem.text == group_name:
                group = g
                break
        if group is None:
            group = ET.SubElement(groups, 'Group')
            ET.SubElement(group, 'GroupName').text = group_name

        files = group.find('Files')
        if files is None:
            files = ET.SubElement(group, 'Files')
        for f in files.findall('File'):
            path_elem = f.find('FilePath')
            if path_elem is not None and path_elem.text == file_path:
                return

        file_elem = ET.SubElement(files, 'File')
        filename = file_path.rsplit('\\', 1)[-1]
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        filetype = {'c': '1', 'h': '5', 's': '2', 'asm': '2',
                     'cpp': '8', 'c++': '8'}.get(ext, '0')
        ET.SubElement(file_elem, 'FileName').text = filename
        ET.SubElement(file_elem, 'FileType').text = filetype
        ET.SubElement(file_elem, 'FilePath').text = file_path
        _restore_and_write(tree, uvprojx_path, ns_uri)
    except PlatformError:
        raise
    except Exception as e:
        raise PlatformError(f"添加文件到 uvprojx 失败: {e}")


def _add_include(uvprojx_path: str, folder_path: str):
    """向 uvprojx 添加 include 路径。"""
    try:
        tree = ET.parse(uvprojx_path)
        root = tree.getroot()
        ns_uri = _extract_namespace(root)
        _strip_namespace(root)

        folder_path = folder_path.replace('/', '\\').rstrip('\\')
        if not folder_path.startswith('.\\'):
            folder_path = '.\\' + folder_path

        for ads_type in ['Cads', 'Aads', 'CPPC']:
            ads_nodes = root.findall(f'.//{ads_type}/VariousControls/IncludePath')
            for inc_node in ads_nodes:
                paths = inc_node.text.split(';') if inc_node.text else []
                paths_lower = [p.lower().rstrip('\\') for p in paths]
                if folder_path.lower() not in paths_lower:
                    paths.append(folder_path)
                    inc_node.text = ';'.join(paths)

        _restore_and_write(tree, uvprojx_path, ns_uri)
    except PlatformError:
        raise
    except Exception as e:
        raise PlatformError(f"添加 Include Path 失败: {e}")


def _remove_file(uvprojx_path: str, group_name: str, file_path: str):
    """从 uvprojx 的指定分组中移除文件。"""
    try:
        tree = ET.parse(uvprojx_path)
        root = tree.getroot()
        ns_uri = _extract_namespace(root)
        _strip_namespace(root)

        groups = root.find('Targets/Target/Groups')
        if groups is None:
            raise PlatformError("未找到 Targets/Target/Groups 节点")

        for g in groups.findall('Group'):
            name_elem = g.find('GroupName')
            if name_elem is not None and name_elem.text == group_name:
                files = g.find('Files')
                if files is not None:
                    for f in files.findall('File'):
                        path_elem = f.find('FilePath')
                        if path_elem is not None and path_elem.text == file_path:
                            files.remove(f)
                            _restore_and_write(tree, uvprojx_path, ns_uri)
                            return
                raise PlatformError(f"文件 {file_path} 在分组 '{group_name}' 中未找到")

        raise PlatformError(f"分组 '{group_name}' 未找到")
    except PlatformError:
        raise
    except Exception as e:
        raise PlatformError(f"从 uvprojx 移除文件失败: {e}")


def _remove_include(uvprojx_path: str, folder_path: str):
    """从 uvprojx 移除 include 路径。"""
    try:
        tree = ET.parse(uvprojx_path)
        root = tree.getroot()
        ns_uri = _extract_namespace(root)
        _strip_namespace(root)

        folder_path = folder_path.replace('/', '\\').rstrip('\\')
        if not folder_path.startswith('.\\'):
            folder_path = '.\\' + folder_path

        for ads_type in ['Cads', 'Aads', 'CPPC']:
            ads_nodes = root.findall(f'.//{ads_type}/VariousControls/IncludePath')
            for inc_node in ads_nodes:
                paths = inc_node.text.split(';') if inc_node.text else []
                paths_lower = [p.lower().rstrip('\\') for p in paths]
                try:
                    idx = paths_lower.index(folder_path.lower())
                    paths.pop(idx)
                    inc_node.text = ';'.join(paths) if paths else ''
                except ValueError:
                    pass

        _restore_and_write(tree, uvprojx_path, ns_uri)
    except PlatformError:
        raise
    except Exception as e:
        raise PlatformError(f"移除 Include Path 失败: {e}")


def _remove_group(uvprojx_path: str, group_name: str):
    """从 uvprojx 删除分组（分组内有文件时报错）。"""
    try:
        tree = ET.parse(uvprojx_path)
        root = tree.getroot()
        ns_uri = _extract_namespace(root)
        _strip_namespace(root)

        groups = root.find('.//Targets/Target/Groups')
        if groups is None:
            raise PlatformError("未找到 Groups 节点")

        for g in groups.findall('Group'):
            name_elem = g.find('GroupName')
            if name_elem is not None and name_elem.text == group_name:
                files = g.find('Files')
                file_count = len(files.findall('File')) if files is not None else 0
                if file_count > 0:
                    raise PlatformError(f"分组 '{group_name}' 不为空（{file_count} 个文件），请先移除文件再删除分组")
                groups.remove(g)
                _restore_and_write(tree, uvprojx_path, ns_uri)
                return

        raise PlatformError(f"分组 '{group_name}' 未找到")
    except PlatformError:
        raise
    except Exception as e:
        raise PlatformError(f"删除分组失败: {e}")


# ── 适配器类 ─────────────────────────────────────────

class KeilAdapter(PlatformAdapter):
    """Keil MDK-ARM 平台适配器。"""

    # ── PlatformAdapter 接口实现 ──

    def find_project_file(self, project_path: str) -> str:
        return _find_uvprojx(project_path)

    def register_module(self, project_file: str,
                        module_meta: dict,
                        project_path: str) -> None:
        group = module_meta.get("group", "Hardware")
        self.create_group(project_file, group)
        all_files = (module_meta.get("files", {}).get("source", []) +
                     module_meta.get("files", {}).get("header", []))
        for f in all_files:
            self.add_file(project_file, group, f".\\{group}\\{f}")
        self.add_include_path(project_file, f".\\{group}")

    # ── 工程结构原子操作 ──

    def create_group(self, project_file: str, group_name: str) -> None:
        """在工程中创建分组（已存在则跳过）。"""
        _create_group(project_file, group_name)

    def add_file(self, project_file: str, group_name: str, file_path: str) -> None:
        """向工程分组添加源文件（已注册则跳过）。"""
        _add_file(project_file, group_name, file_path)

    def remove_file(self, project_file: str, group_name: str, file_path: str) -> None:
        """从工程分组移除源文件。"""
        _remove_file(project_file, group_name, file_path)

    def add_include_path(self, project_file: str, folder_path: str) -> None:
        """向工程添加 Include 路径。"""
        _add_include(project_file, folder_path)

    def remove_include_path(self, project_file: str, folder_path: str) -> None:
        """从工程移除 Include 路径。"""
        _remove_include(project_file, folder_path)

    def remove_group(self, project_file: str, group_name: str) -> None:
        """从工程删除分组（分组为空才能删除）。"""
        _remove_group(project_file, group_name)
