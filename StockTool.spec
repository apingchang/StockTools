# PyInstaller spec for StockTool
# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# data files: config + 3 個 db
datas = [
    ('source/stocktool_config.json', '.'),
    ('source/dividend_history.db', '.'),
    ('source/eps_history.db', '.'),
    ('source/etf_history.db', '.'),
    ('source/portfolio.db', '.'),
]
# collect stocktool package data files
datas += collect_data_files('stocktool')

a = Analysis(
    ['source/StockTool.py'],
    pathex=['source'],
    binaries=[],
    datas=datas,
    hiddenimports=['stocktool'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='StockTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,        # GUI mode, no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,             # 可加 icon if 有 .ico/.png
)
