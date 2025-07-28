# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('adb.exe', '.'), ('AdbWinApi.dll', '.'), ('AdbWinUsbApi.dll', '.'), ('app.ico', '.'), ('avcodec-61.dll', '.'), ('avformat-61.dll', '.'), ('avutil-59.dll', '.'), ('icon.png', '.'), ('libusb-1.0.dll', '.'), ('scrcpy.exe', '.'), ('scrcpy-server', '.'), ('SDL2.dll', '.'), ('swresample-5.dll', '.'), ('templates', 'templates/'), ('config.json', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TikTokADBController',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app.ico'],
    hide_console='hide-early',
)
