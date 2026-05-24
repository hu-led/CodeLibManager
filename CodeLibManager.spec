# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['json', 'os', 'shutil', 'zipfile', 'datetime', 'typing', 'pathlib', 'sys', 'collections', 'argparse', '__future__']
hiddenimports += collect_submodules('xml')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('core', 'core'), ('cli', 'cli'), ('ui', 'ui'), ('resources', 'resources'), ('main.py', '.')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['QtWebEngine', 'QtPdf', 'QtPdfWidgets', 'QtQuick', 'QtQml', 'QtMultimedia', 'QtNetwork', 'QtSql', 'QtTest', 'QtXml'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CodeLibManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CodeLibManager',
)
