from pathlib import Path
import runpy
import re
from PyInstaller.utils.win32.versioninfo import VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct
release_version = runpy.run_path('quotaboard/__init__.py')['__version__']
installer_version = re.search(r'Name="QuotaBoard" Language="2052" Version="([^"]+)"', Path('QuotaBoard.wxs').read_text('utf-8')).group(1)
if release_version != installer_version:
    raise ValueError('Application and MSI versions differ')
version_tuple = tuple(map(int, release_version.split('.'))) + (0,)
version_resource = VSVersionInfo(ffi=FixedFileInfo(filevers=version_tuple, prodvers=version_tuple, mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0,0)), kids=[StringFileInfo([StringTable('040904B0', [StringStruct('CompanyName','Othrik'), StringStruct('FileDescription','QuotaBoard'), StringStruct('FileVersion',release_version), StringStruct('ProductName','QuotaBoard'), StringStruct('ProductVersion',release_version), StringStruct('OriginalFilename','QuotaBoard.exe')])]), VarFileInfo([VarStruct('Translation',[1033,1200])])])
import sysconfig
from pathlib import Path

# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/logo', 'assets/logo'), ('assets/QuotaBoard.ico', 'assets')] + [(str(p), '.') for p in Path(sysconfig.get_path('stdlib')).glob('codex-rejected-cas.pem')],
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
    name='QuotaBoard',
    version=version_resource,
    icon='assets/QuotaBoard.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
