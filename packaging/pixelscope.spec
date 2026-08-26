# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


repo_root = Path(SPECPATH).resolve().parent
source_root = repo_root / "src"
icon_root = source_root / "pixelscope" / "assets" / "icons"
version_info = repo_root / "build" / "release" / "PixelScope.version.txt"
icon_data = [
    (str(icon_root / filename), "pixelscope/assets/icons")
    for filename in ("pixelscope.svg", "pixelscope.png", "pixelscope.ico")
]

analysis = Analysis(
    [str(source_root / "pixelscope" / "__main__.py")],
    pathex=[str(source_root)],
    binaries=[],
    datas=icon_data,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure, analysis.zipped_data)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="PixelScope",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(icon_root / "pixelscope.ico"),
    version=str(version_info),
)

collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    strip=False,
    upx=False,
    name="PixelScope",
)
