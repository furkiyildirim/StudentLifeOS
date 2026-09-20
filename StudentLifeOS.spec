# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import importlib.util
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

PROJECT = Path(SPEC).resolve().parent

datas = []
binaries = []
hiddenimports = []

# Include schema.sql only if it exists.
schema = PROJECT / "schema.sql"
if schema.exists():
    datas.append((str(schema), "."))

# Optional modules: only add them when actually installed.
OPTIONAL_IMPORTS = [
    "google.generativeai",
    "fitz",
    "mutagen",
    "requests",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtWebEngineCore",
]

for module in OPTIONAL_IMPORTS:
    try:
        if importlib.util.find_spec(module) is not None:
            hiddenimports.append(module)
    except (ImportError, ModuleNotFoundError, ValueError):
        pass

# llama_cpp is optional. Do not call collect_all() unless it is installed.
try:
    if importlib.util.find_spec("llama_cpp") is not None:
        from PyInstaller.utils.hooks import collect_all
        d, b, h = collect_all("llama_cpp")
        datas += d
        binaries += b
        hiddenimports += h
except (ImportError, ModuleNotFoundError, ValueError):
    pass

# Add resources to the bundle when the folder exists.
resources = PROJECT / "resources"
if resources.exists():
    datas.append((str(resources), "resources"))

# Optional version information.
version_file = PROJECT / "version.txt"
icon_file = resources / "icons" / "icon.ico"

analysis = Analysis(
    [str(PROJECT / "app.py")],
    pathex=[str(PROJECT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe_kwargs = dict(
    name="StudentLifeOS",
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

# Only pass optional PyInstaller arguments when their files exist.
if version_file.exists():
    exe_kwargs["version"] = str(version_file)
if icon_file.exists():
    exe_kwargs["icon"] = str(icon_file)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    **exe_kwargs,
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Student Life OS",
)
