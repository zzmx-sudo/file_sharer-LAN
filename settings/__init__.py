__all__ = [
    "settings"
]

import os
import json
import importlib
from typing import Any

from exceptions import OperationException
from settings import _base

empty = object()
class configurable(object): pass

class FuseSettings:

    _wrapper = empty

    def __init__(self, mode: str) -> None:

        self.__mode = mode

    def _setup(self) -> None:

        _wrapper = configurable()
        if self.__mode == "develop":
            _wrapper.SETTINGS_MODE = "settings.development"
        elif self.__mode == "prod":
            _wrapper.SETTINGS_MODE = "settings.production"
        else:
            raise OperationException(f"不被允许的环境模式参数: {self.__mode}")

        for setting in dir(_base):
            if setting.isupper():
                setattr(_wrapper, setting, getattr(_base, setting))
        self._wrapper = _wrapper

        mod = importlib.import_module(self.SETTINGS_MODE)
        lock_settings = [
            "BASE_DIR",
            "SYSTEM",
            "IS_WINDOWS",
            "LOCAL_HOST"
        ]

        for setting in dir(mod):
            if setting.isupper():
                if setting in lock_settings:
                    raise OperationException(f"不可修改的参数: {setting}")
                elif setting == "LOGS_PATH":
                    self._check_logs_path(getattr(mod, setting))

                setattr(self._wrapper, setting, getattr(mod, setting))

    def __getattr__(self, item: str) -> Any:
        if self._wrapper is empty:
            self._setup()
        val = getattr(self._wrapper, item)
        self.__dict__[item] = val

        return val

    def __setattr__(self, key: str, value: Any) -> None:
        if key == "_wrapper":
            self.__dict__.clear()
        elif key == "LOGS_PATH":
            self._check_logs_path(value)
            self.__dict__.pop(key, None)
        else:
            self.__dict__.pop(key, None)

        super(FuseSettings, self).__setattr__(key, value)

    def __delattr__(self, item: str) -> None:
        super(FuseSettings, self).__delattr__(item)
        self.__dict__.pop(item, None)

    def __repr__(self) -> str:
        if self._wrapper is empty:
            return "<FuseSettings [Unevaluated]>"
        else:
            return f"<FuseSettings Custom fetch to {self.SETTINGS_MODE}>"

    @staticmethod
    def _check_logs_path(logs_path: str) -> None:

        if not os.path.isdir(logs_path):
            raise OperationException(f"配置的日志文件夹路径不存在, LOGS_PATH: {logs_path}")

    def load(self) -> None:
        settings_file = os.path.join(self.BASE_DIR, "settings.json")
        if not os.path.exists(settings_file):
            return
        with open(settings_file) as f:
            try:
                settings_config = json.loads(f.read())
            except json.JSONDecodeError:
                return
        if not isinstance(settings_config, dict):
            return

        self.__dict__["SAVE_SYSTEM_LOG"] = settings_config.get("saveSystemLog", True)
        self.__dict__["SAVE_SHARER_LOG"] = settings_config.get("saveShareLog", True)
        logsPath = settings_config.get("logsPath")
        if logsPath and os.path.isdir(logsPath):
            self.__dict__["LOGS_PATH"] = logsPath
        downloadPath = settings_config.get("downloadPath")
        if downloadPath and os.path.isdir(downloadPath):
            self.__dict__["DOWNLOAD_DIR"] = downloadPath

    def dump(self) -> None:
        settings_file = os.path.join(self.BASE_DIR, "settings.json")
        with open(settings_file, "w") as f:
            json.dump({
                "saveSystemLog": self.SAVE_SYSTEM_LOG,
                "saveShareLog": self.SAVE_SHARER_LOG,
                "logsPath": self.LOGS_PATH,
                "downloadPath": self.DOWNLOAD_DIR
            }, f, indent=4, separators=(",", ": "), ensure_ascii=False)


settings = FuseSettings("develop")