# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

block_cipher = None

# Collect all dependencies
datas = []
binaries = []
hiddenimports = []

datas.append(('qc_application', 'qc_application'))



# Fix pyproj data files if pyproj is used
try:
    pyproj_datas = collect_data_files('pyproj')
    datas.extend(pyproj_datas)
except Exception:
    pass  # pyproj not installed or not needed

# Add your dependencies folder
dependencies_path = os.path.join(os.getcwd(), 'dependencies')
if os.path.exists(dependencies_path):
    datas.append((dependencies_path, 'dependencies'))

# Collect PyQt5 dependencies
# Option 1: Collect ALL PyQt5 modules (larger size, safer)
pyqt5_imports = collect_submodules('PyQt5')
hiddenimports.extend(pyqt5_imports)

# Option 2: Manual list (smaller size, faster build)
# Comment out the above 2 lines and uncomment below if you want minimal build:
# hiddenimports.extend([
#     'PyQt5.QtCore',
#     'PyQt5.QtGui',
#     'PyQt5.QtWidgets',
#     'PyQt5.QtSvg',
#     'PyQt5.QtNetwork',
#     'PyQt5.sip',
# ])

# Add your application modules
hiddenimports.extend([
    'qc_application.config',
    'qc_application.gui',
    'qc_application.services',
    'qc_application.utils',
    'qc_application.workers',
])

# Fix for pkg_resources / setuptools issue
hiddenimports.extend([
    'pkg_resources.py2_warn',
    'pkg_resources.markers',
    'backports',
    'backports.zoneinfo',
])

# Database drivers - CRITICAL for your app
hiddenimports.extend([
    'psycopg2',
    'psycopg2._psycopg',
    'psycopg2.extensions',
    'psycopg2.extras',
])

# SQLAlchemy and dialects
hiddenimports.extend([
    'sqlalchemy',
    'sqlalchemy.dialects',
    'sqlalchemy.dialects.postgresql',
    'sqlalchemy.dialects.postgresql.psycopg2',
    'sqlalchemy.engine',
    'sqlalchemy.pool',
])

# Geospatial libraries (you have geopandas, rasterio, etc.)
hiddenimports.extend([
    'geopandas',
    'shapely',
    'shapely.geometry',
    'fiona',
    'fiona.schema',
    'rasterio',
    'rasterio._shim',
    'rasterio.control',
    'rasterio.sample',
    'rasterio._err',
    'rasterio._features',
    'rasterio._io',
    'rasterio.crs',
    'rasterio.dtypes',
    'rasterio.env',
    'rasterio.errors',
    'rasterio.transform',
    'rasterio.windows',
    'pyproj',
    'pyproj.datadir',
])

# Collect all rasterio submodules to be safe
try:
    rasterio_imports = collect_submodules('rasterio')
    hiddenimports.extend(rasterio_imports)
except Exception:
    pass

# Scientific libraries
hiddenimports.extend([
    'numpy',
    'pandas',
    'scipy',
    'matplotlib',
    'matplotlib.backends.backend_qt5agg',
])

# Collect setuptools to fix packaging issues
try:
    setuptools_imports = collect_submodules('setuptools')
    hiddenimports.extend(setuptools_imports)
except Exception:
    pass

# Collect additional data files
try:
    # Collect rasterio data files and GDAL data
    rasterio_datas = collect_data_files('rasterio')
    datas.extend(rasterio_datas)

    # Collect GDAL/PROJ data
    import rasterio
    rasterio_path = os.path.dirname(rasterio.__file__)
    gdal_data = os.path.join(rasterio_path, 'gdal_data')
    proj_data = os.path.join(rasterio_path, 'proj_data')

    if os.path.exists(gdal_data):
        datas.append((gdal_data, 'rasterio/gdal_data'))
    if os.path.exists(proj_data):
        datas.append((proj_data, 'rasterio/proj_data'))

except Exception as e:
    print(f"Warning: Could not collect rasterio data: {e}")

try:
    # Collect fiona data files
    fiona_datas = collect_data_files('fiona')
    datas.extend(fiona_datas)
except Exception:
    pass

try:
    # Collect shapely data files
    shapely_datas = collect_data_files('shapely')
    datas.extend(shapely_datas)
except Exception:
    pass

a = Analysis(
    ['qc_application/main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],  # Don't exclude anything - we need psycopg2!
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove problematic pkg_resources runtime hook
a.scripts = [s for s in a.scripts if 'pyi_rth_pkgres' not in s[1]]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='QCApp',
    debug=True,  # ENABLED - Shows PyInstaller debug info
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # ENABLED - Shows console window with logs/prints
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add your icon path here: icon='resources/icons/app_icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='QCApp',
)