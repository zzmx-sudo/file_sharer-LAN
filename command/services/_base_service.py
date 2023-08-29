__all__ = [
    "BaseService"
]

import time
from typing import Union
from threading import Thread
from multiprocessing import Queue

from model.sharing import SharingModel
from model.file import FileModel, DirModel
from exceptions import NotImplException, OperationException

class BaseService:

    def __init__(self, input_q: Queue, output_q: Queue) -> None:

        self._sharing_dict = SharingModel()
        self._input_q = input_q
        self._output_q = output_q
        self._watch_thread = None

    def watch(self) -> None:

        self._watch_thread = Thread(target=self._watch)
        self._watch_thread.setDaemon(True)
        self._watch_thread.start()

    def _watch(self) -> None:

        while True:
            if not self._input_q.empty():
                command_type, command_msg = self._input_q.get()
                if command_type == "add":
                    self._add_share(command_msg)
                elif command_type == "remove":
                    self._remove_share(command_msg)
            else:
                time.sleep(0.5)

    def _add_share(self, fileObj: Union[FileModel, DirModel]) -> None:

        raise NotImplException("实现service对象的类必须有定义`_add_share`方法")

    def _remove_share(self, uuid: str) -> None:

        raise NotImplException("实现service对象的类必须有定义`_remove_share`方法")

    def run(self) -> None:

        if self._watch_thread is None:
            raise OperationException("在service运行前必须先开启watch线程")

        raise NotImplException("实现service对象的类必须有定义`run`方法")