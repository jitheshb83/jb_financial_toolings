# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["finance_app/main.py"],
    pathex=[],
    binaries=[],
    datas=[("finance_app/resources", "finance_app/resources")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Personal Finance",
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
    name="Personal Finance",
)

app = BUNDLE(
    coll,
    name="Personal Finance.app",
    icon="build_assets/app_icon.icns",
    bundle_identifier="online.jithonline.personalfinance",
)
