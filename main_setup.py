"""
This is a main_setup.py script generated by py2applet

Usage:
    python main_setup.py py2app
"""

from setuptools import setup

PROJECT_PATH = "/Users/mr.cheng/GitSourceCodes/file_sharer-Desktop/"
PRODUCT_VERSION = "0.1.0"

APP = [PROJECT_PATH + "main.py"]
DATA_FILES = [
    PROJECT_PATH + "pyproject.toml",
    PROJECT_PATH + "file_sharing_backups.json",
]
OPTIONS = {
    "argv_emulation": True,
    "includes": [
        "aiofiles",
        "aiohttp",
        "fastapi",
        "psutil",
        "pyftpdlib",
        "ftplib",
        "requests",
        "toml",
        "tomli",
        "yarl",
        "settings.development",
        "settings.production",
    ],
    "iconfile": PROJECT_PATH + "static/ui/icon.icns",
    "plist": {
        "CFBundleName": "file-sharer",
        "CFBundleDisplayName": "file-sharer",
        "CFBundleVersion": PRODUCT_VERSION,
        "CFBundleIdentifier": "file-sharer",
        "NSHumanReadableCopyright": "Copyright © 2023 zzmx-sudo.",
    },
    "packages": ["PyQt5", "chardet", "cchardet", "uvicorn", "anyio"],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
    py_modules=[],
)
