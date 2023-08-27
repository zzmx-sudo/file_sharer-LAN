__all__ = [
    "HttpService"
]

import os
from typing import Union
from multiprocessing import Queue

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse, Response
from starlette.types import Scope

from ._base_service import BaseService
from model import public_types as ptype
from model.file import FileModel, DirModel
from settings import settings
from utils.logger import sharerLogger, sysLogger

class MyRequest:

    def __init__(self, scope: Scope) -> None:

        self._setup(scope)

    def _setup(self, scope: Scope) -> None:

        for key in ["client", "path"]:
            self.__dict__[key] = scope.get(key, "")
        for header_name, header_value in scope.get("headers"):
            if header_name == b"x-client":
                self.__dict__["is_client"] = "True"
                break
            # elif header_name == b"sec-ch-ua-platform":
            #     self.__dict__["client_platform"] = header_value.decode()

    def __getitem__(self, item: str) -> Union[str, tuple[str, int]]:

        return self.__dict__.get(item, "")

class HttpService(BaseService):

    def __init__(self, input_q: Queue, output_q: Queue) -> None:
        super(HttpService, self).__init__(input_q, output_q)
        self._app = None

    def _add_share(self, uuid: str, fileObj: Union[FileModel, DirModel]) -> None:
        pass

    def _remove_share(self, uuid: str) -> None:
        pass

    def run(self) -> None:

        import uvicorn
        self._app = FastAPI()
        self.watch()
        self._setup()
        uvicorn.run(
            app=self._app,
            host=settings.LOCAL_HOST,
            port=settings.WSGI_PORT
        )

    def _setup(self) -> None:

        self._setup_middleware()
        self._setup_router()

    def _setup_middleware(self) -> None:

        async def is_download_ftp_without_client(
                shareType: ptype.ShareType, request: MyRequest
        ) -> bool:
            is_client = request["is_client"]
            if shareType is ptype.ShareType.ftp and not is_client:
                return True

            return False

        @self._app.middleware("http")
        async def complete_middleware(request: Request, cell_next) -> Response:
            """
            该中间件目前完成以下功能:
            1. 无效/非法路由返回错误链接提示
            2. 访问/下载的文件/文件夹是否有效校验
            3. 访问/下载日志写入
            4. 是否用非客户端下载FTP服务文件/文件夹
            5. 文件/文件夹对象往后传递给视图
            :param request: fastapi request对象
            :param cell_next: 后续中间件/视图回调函数
            :return: Response: fastapi支持的 response对象
            """
            _request = MyRequest(request.scope)
            client_ip = _request["client"][0] if _request["client"] else "未知IP"
            uri, param = _request["path"].rsplit("/", 1)
            # client_platform = _request["client_platform"]
            if "%" in param:
                uuid_parent, uuid_child = param.split("%", 1)
                fileObj = self._sharing_dict.get(uuid_parent, {}).get(uuid_child, None)
            else:
                fileObj = self._sharing_dict.get(param, None)
            # 文件是否存在判断
            if fileObj is None or not os.path.exists(fileObj.targetPath):
                sharerLogger.warning("访问错误路径或文件/文件夹已不存在, 访问链接: %s, 用户IP: %s" % (
                    _request["path"], client_ip
                ))
                return JSONResponse({"errno": 404, "errmsg": "错误的路径或文件已不存在！"})
            # 浏览/下载记录写入日志
            if uri == "/file_list":
                sharerLogger.info("用户IP: %s, 用户访问了文件列表, 文件链接: %s" % (
                    client_ip, fileObj.targetPath,
                ))
            elif uri == "/download":
                # 用户下载时, 需进行是否为客户端判断
                if await is_download_ftp_without_client(fileObj.shareType, _request):
                    sharerLogger.warning("用户使用非客户端无法下载FTP分享的文件/文件夹, 用户IP: %s" % client_ip)
                    return JSONResponse({"errno": 400, "errmsg": "ftp分享的文件/文件夹请使用客户端进行下载"})
                else:
                    sharerLogger.info("用户IP: %s, 用户下载了文件, 文件链接: %s" % (
                        client_ip, fileObj.targetPath
                    ))
                    self._output_q.put(param)
            else:
                return JSONResponse({"errno": 404, "errmsg": "访问的链接不存在！"})

            request.scope["fileObj"] = fileObj
            response = await cell_next(request)
            return response

    def _setup_router(self) -> None:

        @self._app.get("%s/{uuid}" % ptype.FILE_LIST_URI)
        async def file_list(uuid: str, request: Request) -> dict:

            return {"hello": uuid}

        @self._app.get("%s/{uuid}" % ptype.DOWNLOAD_URI)
        async def download(uuid: str, request: Request) -> Union[dict, Response]:

            fileObj = request.scope.get("fileObj")
            fileObj: Union[None, FileModel, DirModel]
            if not fileObj:
                sysLogger.error(
                    "发生了错误, 获取不到用户访问的文件/文件夹对象, "
                    "请用uuid对比`file_sharing_backups.json`文件, "
                    "查看分享的文件/文件夹状态, uuid: %s" % uuid
                )
                return {"errno": 500, "errmsg": "系统发生错误, 文件/文件夹对象没有被正确传递"}

            if fileObj.shareType is ptype.ShareType.http:
                return FileResponse(path=fileObj.targetPath)
            elif fileObj.shareType is ptype.ShareType.ftp:
                return {"errno": 200, "errmsg": "下载已被记录"}
            else:
                sysLogger.error("未被预判的分享类型: %s, 系统发生错误" % fileObj.shareType.value)
                return {"errno": 500, "errmsg": "下载文件/文件夹失败"}