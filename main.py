import os
import sys
import copy
import traceback
from multiprocessing import Queue
from typing import Union, Dict, Any, Tuple, List, Sequence

from PyQt5.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QLineEdit,
    QButtonGroup,
    QPushButton,
)
from PyQt5.Qt import QApplication, QIcon
from PyQt5 import QtGui

from static.ui.main_ui import Ui_MainWindow
from settings import settings
from utils.logger import sysLogger, sharerLogger
from command.manage import ServiceProcessManager
from model.sharing import FuseSharingModel
from model.file import FileModel, DirModel
from model.public_types import ShareType as shareType
from model.public_types import ThemeColor as themeColor
from model.public_types import DownloadStatus
from model.qt_thread import *
from model.browse import BrowseFileDictModel
from model.assert_env import AssertEnvWindow
from model.tray_icon import TrayIcon
from utils.public_func import generate_uuid, update_downloadUrl_with_hitLog


class MainWindow(QMainWindow):
    def __init__(self):
        """
        主程序窗口类初始化函数
        """
        super(MainWindow, self).__init__()

        # load ui
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self._merge_theme_radioButton()

        # setup ui_function
        from utils.ui_function import UiFunction

        self._UIClass = UiFunction
        self._ui_function = UiFunction(self)
        self._ui_function.setup()

        # load env
        self._load_settings()
        self._load_sharing_backups()

        # Initialize service process manage and watch thread
        self._create_service_manager()

        # setup attr
        self._setup_attr()

        # connect event
        self._setup_event_connect()

        # show window after assert env successful.
        # self.show()

    def show_normal(self) -> None:
        """
        环境校验完成并无异常后, 打开主窗口并显示系统托盘图标

        Returns:
            None
        """
        self.ti = TrayIcon(self)
        self.ti.show()
        self.show()

    def save_settings(self) -> None:
        """
        Expose save settings to the outside

        Returns:
            None
        """

    def reset_settings(self) -> None:
        """
        Expose reset settings to the outside

        Returns:
            None
        """

        self._cancel_settings()

    def open_all_share(self) -> None:
        """
        打开所有的共享

        Returns:
            None
        """
        open_count = 0
        for row in range(self.ui.shareListTable.rowCount()):
            status_item = self.ui.shareListTable.item(
                row, self._ui_function._share_status_col
            )
            if status_item.text() == self._ui_function._isNot_sharing_str:
                button_widget = self.ui.shareListTable.cellWidget(
                    row, self._ui_function._share_options_col
                )
                open_button = button_widget.findChild(QPushButton, "open_close")
                open_button.click()
                open_count += 1
        self._ui_function.show_info_messageBox(f"操作成功, 本次成功打开分享个数: {open_count}")

    def close_all_share(self) -> None:
        """
        关闭所有的共享

        Returns:
            None
        """
        close_count = 0
        for row in range(self.ui.shareListTable.rowCount()):
            status_item = self.ui.shareListTable.item(
                row, self._ui_function._share_status_col
            )
            if status_item.text() == self._ui_function._is_sharing_str:
                button_widget = self.ui.shareListTable.cellWidget(
                    row, self._ui_function._share_options_col
                )
                close_button = button_widget.findChild(QPushButton, "open_close")
                close_button.click()
                close_count += 1
        self._ui_function.show_info_messageBox(f"操作成功, 本次成功关闭分享个数: {close_count}")

    def create_download_record_and_start(
        self, fileDict: Union[None, Dict[str, Any]] = None
    ) -> None:
        """
        当发成下载意愿时的回调

        Args:
            fileDict: 需下载的文件/文件夹对象

        Returns:
            None
        """
        self.ui.downloadDirButton.setEnabled(False)
        if fileDict:
            if (
                self._ui_function.show_question_messageBox(
                    f"当前正要下载文件: {fileDict.get('fileName', '未知文件名')}, 确认是否下载？",
                    "确认是否下载",
                    "没错, 我就要下载它",
                    "点错了",
                )
                != 0
            ):
                self.ui.downloadDirButton.setEnabled(self._browse_data.isDir)
                return
            copy_fileDict = copy.copy(fileDict)
            copy_fileDict.update({"relativePath": copy_fileDict["fileName"]})
            update_downloadUrl_with_hitLog(copy_fileDict)
            fileList = [copy_fileDict]
            fileCount = 1
        else:
            fileList, fileCount = self._generate_fileList_recursive()
        self._append_download_fileList(fileList)

        sysLogger.info(f"加入下载成功, 此次下载文件个数: {fileCount}")
        self._ui_function.show_info_messageBox("加入下载成功")
        self.ui.removeDownloadsButton.setEnabled(True)

        self.ui.downloadDirButton.setEnabled(self._browse_data.isDir)

    def enter_dir(self, fileDict: Dict[str, Any]) -> None:
        """
        浏览文件时点击文件夹的回调

        Args:
            fileDict: 文件夹对象

        Returns:
            None
        """
        self._browse_data.currentDict = fileDict
        self._UIClass.show_file_list(self, self._browse_data.currentDict)
        self.ui.backupButton.setEnabled(True)

    def remove_share(self, fileObj: Union[FileModel, DirModel]) -> None:
        """
        移除分享记录时的回调

        Args:
            fileObj: 待移除分享记录的文件/文件夹对象

        Returns:
            None
        """
        if fileObj.isSharing:
            self._ui_function.show_info_messageBox(
                "该分享未关闭,请先关闭分享后再移除哦~", msg_color="red"
            )
            return
        self._sharing_list.remove(fileObj.rowIndex)
        self._UIClass.remove_share_row(self, fileObj.rowIndex)
        if not self._sharing_list or self._sharing_list.length == 0:
            self._service_process.close_all()
        del fileObj
        self._ui_function.show_info_messageBox("移除成功~")

    def open_share(self, fileObj: Union[FileModel, DirModel]) -> None:
        """
        打开分享时的回调

        Args:
            fileObj: 需打开分享的文件/文件夹对象

        Returns:
            None
        """
        if fileObj.isSharing:
            sysLogger.error(
                f"操作异常,重复打开分享,分享路径: {fileObj.targetPath}, 分享类型:{fileObj.shareType.value}"
            )
            return
        self._service_process.add_share(fileObj)

    def close_share(self, fileObj: Union[FileModel, DirModel]) -> None:
        """
        关闭分享时的回调

        Args:
            fileObj: 需关闭分享的文件/文件夹对象

        Returns:
            None
        """
        if not fileObj.isSharing:
            sysLogger.error(
                f"操作异常,重复取消分享,分享路径: {fileObj.targetPath}, 分享类型:{fileObj.shareType.value}"
            )
            return
        # 启动时加载历史分享记录,会调用此函数,理应不做处理,此时_service_process还未初始化
        try:
            self._service_process.remove_share(fileObj.uuid)
        except AttributeError:
            return

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """
        关闭主程序窗口的回调

        Args:
            event: 关闭主程序窗口时传入的事件对象

        Returns:
            None
        """
        result = self._ui_function.show_question_messageBox("您正在退出程序，请确认是否退出？", "是否退出？")
        if result != 0:
            self._service_process.close_all()
            self._sharing_list.dump()
            event.accept()
        else:
            event.ignore()

    def except_hook(self, type: Exception, value: str, tb: traceback) -> None:
        """
        程序发生异常时的钩子回调

        Args:
            type: 异常类型
            value: 异常的信息
            tb: 调用栈对象

        Returns:
            None
        """
        err_msg = ""
        while tb:
            filename = tb.tb_frame.f_code.co_filename
            func_name = tb.tb_frame.f_code.co_name
            line_no = tb.tb_lineno
            err_msg += f"File {filename} line {line_no} in {func_name}\n"

            tb = tb.tb_next
        err_msg += f"{type.__name__}: {value}"

        self._ui_function.show_critical_messageBox(err_msg)

    def _merge_theme_radioButton(self) -> None:
        self.ui.themeColorButtonGroup = QButtonGroup()
        self.ui.themeColorButtonGroup.addButton(self.ui.Default)
        self.ui.themeColorButtonGroup.addButton(self.ui.Red)
        self.ui.themeColorButtonGroup.addButton(self.ui.Orange)
        self.ui.themeColorButtonGroup.addButton(self.ui.Yellow)
        self.ui.themeColorButtonGroup.addButton(self.ui.Green)
        self.ui.themeColorButtonGroup.addButton(self.ui.Cyan)
        self.ui.themeColorButtonGroup.addButton(self.ui.Blue)
        self.ui.themeColorButtonGroup.addButton(self.ui.Purple)

    def _load_settings(self) -> None:
        self._cancel_settings()
        sysLogger.info("加载配置完成")

    def _load_sharing_backups(self) -> None:
        self._sharing_list = FuseSharingModel.load()
        for fileObj in self._sharing_list:
            self._UIClass.add_share_table_item(self, fileObj)

    def _create_service_manager(self) -> None:
        self._browse_record_q = Queue()
        self._watch_browse_thread = WatchResultThread(self._browse_record_q)
        self._watch_browse_thread.signal.connect(self._update_browse_number)
        self._watch_browse_thread.start()

        self._service_process = ServiceProcessManager(self._browse_record_q)

    def _update_browse_number(self, file_uuid: str) -> None:
        for fileObj in self._sharing_list:
            if (
                fileObj.uuid == file_uuid
                and fileObj.rowIndex < self.ui.shareListTable.rowCount()
            ):
                fileObj.browse_number += 1
                self.ui.shareListTable.item(fileObj.rowIndex, 3).setText(
                    str(fileObj.browse_number)
                )
                break

    def _setup_attr(self) -> None:
        from model.download import DownloadFileDictModel

        self._prev_browse_url: str = ""
        self._browse_data: BrowseFileDictModel = BrowseFileDictModel.load({})
        self._download_data: DownloadFileDictModel = DownloadFileDictModel(self)

        self._browse_thread: Union[None, LoadBrowseUrlThread] = None
        self._download_http_thread: Union[None, DownloadHttpFileThread] = None
        self._download_ftp_thread: Union[None, DownloadFtpFileThread] = None

    def _setup_event_connect(self) -> None:
        # settings elements
        self.ui.logPathButton.clicked.connect(
            lambda: self._open_folder(self.ui.logPathEdit)
        )
        self.ui.downloadPathButton.clicked.connect(
            lambda: self._open_folder(self.ui.downloadPathEdit)
        )
        self.ui.saveSettingButton.clicked.connect(lambda: self._save_settings())
        self.ui.cancelSettingButton.clicked.connect(lambda: self._cancel_settings())
        # server elements
        self.ui.sharePathButton.clicked.connect(
            lambda: self._open_folder(self.ui.sharePathEdit)
        )
        self.ui.sharePathButton.clicked.connect(lambda: self._update_file_combo())
        self.ui.createShareButton.clicked.connect(lambda: self._create_share())
        # client elements
        self.ui.shareLinkButton.clicked.connect(lambda: self._load_browse_url())
        self.ui.shareLinkEdit.returnPressed.connect(lambda: self._load_browse_url())
        self.ui.backupButton.clicked.connect(lambda: self._backup_button_clicked())
        self.ui.downloadDirButton.clicked.connect(
            lambda: self.create_download_record_and_start()
        )
        self.ui.removeDownloadsButton.clicked.connect(
            lambda: self._remove_download_list()
        )

    def _save_settings(self) -> None:
        logs_path: str = self.ui.logPathEdit.text()
        download_path: str = self.ui.downloadPathEdit.text()
        if not logs_path or not download_path:
            errmsg = "保存设置错误,日志路径或下载路径不可为空！"
            self._ui_function.show_info_messageBox(errmsg, msg_color="red")
            sysLogger.warning(errmsg + f"欲设置的日志路径: {logs_path}, 下载路径: {download_path}")
            return
        if not os.path.isdir(logs_path):
            errmsg = "保存设置错误,日志路径不存在！\n建议用按钮打开资源管理器选择路径"
            self._ui_function.show_info_messageBox(errmsg, msg_color="red")
            sysLogger.warning(errmsg.replace("\n", "") + f", 欲设置的日志路径: {logs_path}")
            return
        if not os.path.isdir(download_path):
            errmsg = "保存设置错误,下载路径不存在！\n建议用按钮打开资源管理器选择路径"
            self._ui_function.show_info_messageBox(errmsg, msg_color="red")
            sysLogger.warning(errmsg.replace("\n", "") + f", 欲设置的下载路径: {download_path}")
            return

        save_system_log: bool = self.ui.saveSystemCheck.isChecked()
        if save_system_log != settings.SAVE_SYSTEM_LOG:
            settings.SAVE_SYSTEM_LOG = save_system_log
            self._service_process.modify_settings("SAVE_SYSTEM_LOG", save_system_log)
        save_share_log: bool = self.ui.saveShareCheck.isChecked()
        if save_share_log != settings.SAVE_SHARER_LOG:
            settings.SAVE_SHARER_LOG = save_share_log
            self._service_process.modify_settings("SAVE_SHARER_LOG", save_share_log)
        if settings.LOGS_PATH != logs_path:
            settings.LOGS_PATH = logs_path
            self._service_process.modify_settings("LOGS_PATH", logs_path)
            sysLogger.reload()
            sharerLogger.reload()
        settings.DOWNLOAD_DIR = download_path
        checkedRadio = self.ui.themeColorButtonGroup.checkedButton()
        theme_color = themeColor.dispatch(checkedRadio.objectName())
        self._ui_function.save_theme(theme_color)
        settings.THEME_COLOR = theme_color
        settings.THEME_OPACITY = self.ui.opacitySlider.value()
        settings.dump()
        self._ui_function.show_info_messageBox("保存配置成功")
        sysLogger.info("保存配置成功")

    def _cancel_settings(self) -> None:
        self.ui.saveSystemCheck.setChecked(settings.SAVE_SYSTEM_LOG)
        self.ui.saveShareCheck.setChecked(settings.SAVE_SHARER_LOG)
        self.ui.logPathEdit.setText(settings.LOGS_PATH)
        self.ui.downloadPathEdit.setText(settings.DOWNLOAD_DIR)
        rollback_radioButton = getattr(self.ui, settings.THEME_COLOR.value)
        rollback_radioButton.setChecked(True)
        self.ui.opacitySlider.setValue(settings.THEME_OPACITY)
        self._ui_function.reset_theme()

    def _update_file_combo(self) -> None:
        share_path: str = self.ui.sharePathEdit.text()
        if not os.path.isdir(share_path):
            return
        self.ui.shareFileCombo.clear()
        fileList: list = os.listdir(share_path)
        for item in fileList:
            self.ui.shareFileCombo.addItem(item)

    def _create_share(self) -> None:
        def _create_share_inner() -> None:
            base_path: str = self.ui.sharePathEdit.text()
            if not os.path.isdir(base_path):
                errmsg = "分享的路径不存在！\n建议用按钮打开资源管理器选择路径"
                self._ui_function.show_info_messageBox(errmsg, msg_color="red")
                sysLogger.warning(
                    errmsg.replace("\n", "") + f", 欲分享的文件夹路径: {base_path}"
                )
                return
            target_path: str = os.path.join(
                base_path, self.ui.shareFileCombo.currentText()
            )
            # 路径整好看一点
            if settings.IS_WINDOWS:
                target_path = target_path.replace("/", "\\")
            else:
                target_path = target_path.replace("\\", "/")
            if not os.path.exists(target_path):
                errmsg = "分享的路径不存在！\n请确认后再新建"
                self._ui_function.show_info_messageBox(errmsg, msg_color="red")
                sysLogger.warning(errmsg.replace("\n", "") + f", 欲分享的路径: {target_path}")
                return
            share_type: Union[str, shareType] = self.ui.shareTypeCombo.currentText()
            share_type = shareType.ftp if share_type == "FTP" else shareType.http
            shared_row_number: Union[None, int] = self._sharing_list.contains(
                target_path, share_type
            )
            if shared_row_number is not None:
                self._ui_function.show_info_messageBox(
                    f"该路径已被分享过, 他在分享记录的第 [{shared_row_number + 1}] 行", msg_color="red"
                )
                sysLogger.warning(f"重复分享被取消, 分享的路径: {target_path}, 分享类型: {share_type}")
                return
            try:
                file_count = self._calc_file_count(target_path)
            except FileNotFoundError as e:
                self._ui_function.show_info_messageBox(
                    f"文件路径解析错误, 原始错误信息: {e}", "分享异常", msg_color="red"
                )
                sysLogger.warning(f"分享文件中含无法打开路径, 尝试打开发生的错误信息: {e}")
                return
            except Exception as e:
                self._ui_function.show_info_messageBox(
                    f"分享出现错误, 原始错误信息: {e}", "分享异常", msg_color="red"
                )
                sysLogger.warning(f"分享异常, 尝试分享发生的错误信息: {e}")
                return
            if file_count > 10000:
                self._ui_function.show_info_messageBox(
                    f"分享已被取消\n该文件夹内文件数量大于10000, 直接分享它不是一个好的选择, 请按需对文件夹进行打包后再分享",
                    "分享被取消",
                    msg_color="red",
                )
                sysLogger.warning("分享被取消, 因为分享的文件夹中文件个数超过10000, 建议打包后分享压缩文件")
                return
            elif file_count > 100:
                if (
                    self._ui_function.show_question_messageBox(
                        "文件夹内文件数量大于100, 会影响下载速度, 若无浏览文件需求, 建议打包成压缩包后再分享",
                        "文件数量大",
                        "好的, 打包后再分享",
                        "无视直接分享",
                    )
                    == 0
                ):
                    sysLogger.info("成功取消文件个数大于100的文件夹的分享")
                    return
            uuid: str = f"{share_type.value[0]}{generate_uuid()}"
            fileModel = DirModel if os.path.isdir(target_path) else FileModel
            if share_type is shareType.ftp:
                shared_fileObj = self._sharing_list.get_ftp_shared(target_path)
            else:
                shared_fileObj = None
            if shared_fileObj is None:
                fileObj = fileModel(target_path, uuid)
            else:
                fileObj = fileModel(
                    target_path,
                    uuid,
                    pwd=shared_fileObj.ftp_pwd,
                    port=shared_fileObj.ftp_port,
                    ftp_base_path=shared_fileObj.ftp_basePath,
                )
            self._sharing_list.append(fileObj)
            fileObj.isSharing = True
            self._UIClass.add_share_table_item(self, fileObj)
            self._service_process.add_share(fileObj)
            sysLogger.info(f"创建分享成功, 分享路径: {target_path}, 分享类型: {share_type}")

        self.ui.createShareButton.setEnabled(False)
        self.ui.createShareButton.setText("创建中。。。")
        _create_share_inner()
        self.ui.createShareButton.setText("新建分享")
        self.ui.createShareButton.setEnabled(True)

    def _load_browse_url(self) -> None:
        self._reload_browse_buttons()
        browse_url: str = self.ui.shareLinkEdit.text()
        if not browse_url or not browse_url.startswith("http://"):
            errmsg = "不支持的分享链接!\n请确认分享链接无误后再点击加载哦~"
            self._ui_function.show_info_messageBox(errmsg, msg_color="rgb(154, 96, 2)")
            sysLogger.warning(errmsg.replace("\n", "") + f"输入的链接地址: {browse_url}")
            return
        # 简单提高下效率
        if browse_url == self._prev_browse_url:
            if self._browse_data:
                self._load_browse_url_reload()
                self._UIClass.show_file_list(self, self._browse_data)
                sysLogger.info("相同的链接使用缓存加载完成")
            return
        self._prev_browse_url = browse_url
        self.ui.shareLinkButton.setText("加载中...")
        self.ui.shareLinkButton.setEnabled(False)
        if self._browse_thread is not None:
            self._browse_thread.run_flag = False
            self._browse_thread.quit()
        self._browse_thread = LoadBrowseUrlThread(browse_url)
        self._browse_thread.signal.connect(self._show_file_list)
        self._browse_thread.start()

    def _reload_browse_buttons(self) -> None:
        self.ui.backupButton.setEnabled(False)
        self.ui.downloadDirButton.setEnabled(False)

    def _load_browse_url_reload(self) -> None:
        self._browse_data.reload()

    def _show_file_list(self, browse_response: Dict[str, Any]) -> None:
        if (
            not browse_response
            or not isinstance(browse_response, dict)
            or not browse_response.get("errno")
        ):
            self._browse_data = BrowseFileDictModel.load({})
            self._UIClass.show_error_browse(self)
        elif browse_response.get("errno", 0) == 404:
            self._browse_data = BrowseFileDictModel.load({})
            self._UIClass.show_not_found_browse(self)
        elif browse_response.get("errno", 0) == 500:
            self._browse_data = BrowseFileDictModel.load({})
            self._UIClass.show_server_error_browse(self)
        elif browse_response.get("errno", 0) == 200:
            browse_data: dict = browse_response.get("data", {})
            if not self._verify_data(browse_data):
                self._browse_data = BrowseFileDictModel.load({})
                self._UIClass.show_server_error_browse(self)
            else:
                self._browse_data = BrowseFileDictModel.load(browse_data)
                self._UIClass.show_file_list(self, self._browse_data)
        else:
            self._browse_data = BrowseFileDictModel.load({})
            self._UIClass.show_server_error_browse(self)
        self._browse_thread = None
        self.ui.shareLinkButton.setText("点击加载")
        self.ui.shareLinkButton.setEnabled(True)
        sysLogger.info("加载文件列表完成")

    def _backup_button_clicked(self) -> None:
        self._browse_data.prev()
        self._UIClass.show_file_list(self, self._browse_data.currentDict)
        self.ui.backupButton.setEnabled(not self._browse_data.isRoot)

    def _generate_fileList_recursive(self) -> Tuple[List[Dict[str, Any]], int]:
        def _generate_fileList_recursive_inner(
            fileList: List[Dict[str, Any]], fileDict: Dict[str, Any]
        ) -> List[Dict[str, Any]]:
            copy_fileDict = copy.deepcopy(fileDict)
            dir_name = copy_fileDict["fileName"]
            for children in copy_fileDict["children"]:
                relativePath = os.path.join(dir_name, children["fileName"])
                if children["isDir"]:
                    children.update({"fileName": relativePath})
                    _generate_fileList_recursive_inner(fileList, children)
                else:
                    children.update({"relativePath": relativePath})
                    fileList.append(children)

                QApplication.processEvents()

            return fileList

        current_fileDict = self._browse_data.currentDict
        parent_fileDict = copy.copy(current_fileDict)
        update_downloadUrl_with_hitLog(parent_fileDict)
        fileList = [parent_fileDict]

        fileList = _generate_fileList_recursive_inner(fileList, parent_fileDict)
        return fileList, len(fileList) - 1

    def _append_download_fileList(self, fileList: Sequence[Dict[str, Any]]) -> None:
        self._UIClass.add_download_table_item(self, fileList)

        if fileList[0]["stareType"] == "ftp":
            if self._download_ftp_thread is None:
                self._download_ftp_thread = DownloadFtpFileThread(fileList)
                self._download_ftp_thread.signal.connect(self._update_download_status)
                self._download_ftp_thread.start()
            else:
                self._download_ftp_thread.append(fileList)
        else:
            if self._download_http_thread is None:
                self._download_http_thread = DownloadHttpFileThread(fileList)
                self._download_http_thread.signal.connect(self._update_download_status)
                self._download_http_thread.start()
            else:
                self._download_http_thread.append(fileList)

    def _open_folder(self, lineEdit: QLineEdit) -> None:
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹", "./")
        if folder_path:
            lineEdit.setText(folder_path)

    def _verify_data(self, data: Dict[str, Any]) -> bool:
        if not data or not isinstance(data, dict):
            return False
        status = True
        isDir = data.get("isDir")
        if isDir is None:
            return False
        if isDir:
            other_full_keys = [
                "uuid",
                "downloadUrl",
                "fileName",
                "stareType",
                "children",
            ]
        else:
            other_full_keys = ["uuid", "downloadUrl", "fileName", "stareType"]
        if not all(key in data for key in other_full_keys):
            return False
        if isDir:
            for child in data["children"]:
                try:
                    if len(child) != 1:
                        return False
                    for file_dict in child.values():
                        status &= self._verify_data(file_dict)
                except AttributeError:
                    return False

        return status

    def _calc_file_count(self, base_path: str, initial_count: int = 0) -> int:
        if not os.path.isdir(base_path):
            return 1
        else:
            for file_name in os.listdir(base_path):
                file_path = os.path.join(base_path, file_name)
                try:
                    initial_count += self._calc_file_count(file_path)
                except:
                    raise
                else:
                    if initial_count > 10000:
                        return initial_count

                QApplication.processEvents()

        return initial_count

    def _update_download_status(
        self, status_tuple: Tuple[Dict[str, Any], DownloadStatus, str]
    ) -> None:
        self._download_data.update_download_status(
            status_tuple, self.ui.downloadListTable
        )

    def _remove_download_list(self) -> None:
        self._download_data.remove_download_list(self.ui.downloadListTable)
        self.ui.removeDownloadsButton.setEnabled(not self._download_data.is_empty())


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(":/icons/icon.ico"))
    window = MainWindow()
    assert_window = AssertEnvWindow()
    assert_window.all_safe.connect(lambda: window.show_normal())
    sys.excepthook = window.except_hook
    sys.exit(app.exec_())
