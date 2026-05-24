@echo off
echo ============================================
echo  CodeLibManager -- PyInstaller Build
echo ============================================

cd /d "%~dp0"

echo.
echo [1/3] Cleaning old build...
if exist "dist\CodeLibManager" rmdir /s /q "dist\CodeLibManager"
if exist "build\CodeLibManager" rmdir /s /q "build\CodeLibManager"

echo [2/3] Building (--onedir mode)...
pyinstaller ^
    --onedir ^
    --name "CodeLibManager" ^
    --noconsole ^
    --exclude-module QtWebEngine ^
    --exclude-module QtPdf ^
    --exclude-module QtPdfWidgets ^
    --exclude-module QtQuick ^
    --exclude-module QtQml ^
    --exclude-module QtMultimedia ^
    --exclude-module QtNetwork ^
    --exclude-module QtSql ^
    --exclude-module QtTest ^
    --exclude-module QtXml ^
    --paths "%LOCALAPPDATA%\Programs\Python\Python312\Lib" ^
    --hidden-import json ^
    --hidden-import os ^
    --hidden-import shutil ^
    --hidden-import zipfile ^
    --hidden-import datetime ^
    --hidden-import typing ^
    --hidden-import pathlib ^
    --hidden-import sys ^
    --hidden-import collections ^
    --hidden-import argparse ^
    --hidden-import __future__ ^
    --collect-submodules xml ^
    --add-data "core;core" ^
    --add-data "cli;cli" ^
    --add-data "ui;ui" ^
    --add-data "resources;resources" ^
    --add-data "main.py;." ^
    "main.py"

if %ERRORLEVEL% NEQ 0 (
    echo Build FAILED!
    pause
    exit /b 1
)

echo.
echo [3/3] Build SUCCESS!
echo   dist\CodeLibManager\CodeLibManager.exe  -- GUI (double-click)
echo   dist\CodeLibManager\CodeLibManager.exe cli ...  -- CLI
echo.
echo To create desktop shortcut: right-click the exe ^> Send to Desktop
pause
