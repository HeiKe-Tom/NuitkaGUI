import os
import time
from pathlib import Path
from typing import Optional

import loguru
from PySide6.QtWidgets import QApplication, QFileDialog

from src.model.basic_model import BasicModel
from src.signal_bus import SignalBus
from src.utils.singleton import singleton
from src.utils.thread_utils import RunInThread
from src.utils.window_explorer_utils import WindowExplorerUtils
from src.view.basic_view import BasicView


@singleton
class BasicPresenter:

    def __init__(self):
        self._view = BasicView()
        self._model = BasicModel()

        self._window_explorer_utils = WindowExplorerUtils()
        self._signal_bus = SignalBus()

        self._start_time: float | None = None

        self.bind()

    # ==========================
    # 基础属性
    # ==========================

    @property
    def view(self) -> BasicView:
        return self._view

    @property
    def model(self) -> BasicModel:
        return self._model

    # ==========================
    # 工具方法
    # ==========================

    def _safe_path(self, value) -> Optional[Path]:
        if isinstance(value, Path):
            return value
        if isinstance(value, str) and value.strip():
            return Path(value)
        return None

    def _ensure_output_dir(self, path: Path):
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            loguru.logger.error(f'创建输出目录失败: {e}')
            self._view.show_error_infobar('错误', '创建输出目录失败')

    def _get_output_dir_path(self) -> Path:
        if not self._model.source_script_path:
            return Path.cwd() / 'output'
        return self._model.source_script_path.parent / 'output'

    # ==========================
    # 业务逻辑
    # ==========================

    def _source_script_changed(self, drop_file_url: str):

        drop_file_path = Path(drop_file_url)

        if not drop_file_path.exists():
            self._view.show_warning_infobar('错误', f'文件不存在: {drop_file_url}')
            self._model.source_script_path = None
            return

        if drop_file_path.suffix != '.py':
            self._view.show_warning_infobar('错误', '只能拖入 .py 文件')
            self._model.source_script_path = None
            return

        self._model.source_script_path = drop_file_path
        self._view.source_script_path = drop_file_path

        output_dir = self._get_output_dir_path()
        self._ensure_output_dir(output_dir)

        self._model.output_dir = output_dir
        self._view.output_dir = output_dir

        self._view.show_success_infobar('成功', f'已选择文件: {drop_file_path.name}', duration=2000)

        # 查找虚拟环境 python.exe
        project_python_exe = self._window_explorer_utils.find_files_in_dir_recursive(
            drop_file_path.parent,
            'python.exe',
            WindowExplorerUtils.FileType.FILES
        )

        if project_python_exe:
            project_python_exe = project_python_exe[0]
            if Path(project_python_exe).is_relative_to(drop_file_path.parent):
                self._view.show_mask_dialog(
                    '已找到项目 Python.exe',
                    f'检测到虚拟环境, 是否使用:\n{project_python_exe}'
                )
                self._model.project_python_exe_path = project_python_exe
                self._signal_bus.update_setting_view.emit()

    def _open_file_dialog(self):

        py_file, _ = QFileDialog.getOpenFileName(
            self._view,
            '选择 Python 文件',
            '',
            'Python 文件 (*.py)'
        )

        if not py_file:
            self._view.show_warning_infobar('错误', '未选择任何文件')
            return

        self._source_script_changed(py_file)

    def _output_dir_changed(self):

        if not self._model.source_script_path:
            self._view.show_warning_infobar('错误', '请先选择 Python 文件')
            return

        output_path = QFileDialog.getExistingDirectory(self._view, '选择输出路径', '')

        if not output_path:
            default_path = self._get_output_dir_path()
            self._ensure_output_dir(default_path)

            self._view.output_dir = default_path
            self._model.output_dir = default_path

            self._view.show_warning_infobar('提示', '未选择文件夹, 已使用默认路径')
            return

        output_path = Path(output_path)
        self._ensure_output_dir(output_path)

        self._view.output_dir = output_path
        self._model.output_dir = output_path

        loguru.logger.info(f'选择输出路径为: {output_path}')

    def _icon_changed(self):

        icon_path, _ = QFileDialog.getOpenFileName(
            self._view,
            '选择图标文件',
            '',
            '图标文件 (*.ico)'
        )

        if not icon_path:
            self._model.icon_path = None
            return

        icon_path = Path(icon_path)

        self._model.icon_path = icon_path
        self._view.icon_path = icon_path

        self._view.show_success_infobar(
            '成功',
            f'已选择图标文件: {icon_path.name}',
            duration=2000
        )

    def _packaged_mode_changed(self):

        is_onefile = self._view.get_mode_radiobutton().isChecked()
        self._model.packaged_mode = 'onefile' if is_onefile else 'standalone'

    def _start(self):

        if not self._model.source_script_path:
            self._view.show_warning_infobar('错误', '请先选择 Python 文件')
            return

        self._start_time = time.time()

        def start():
            return self._model.start()

        def finished(is_success: bool):

            if not is_success:
                self._view.show_error_infobar('错误', '打包任务失败')
                self._view.finish_state_tooltip('失败', '打包任务失败')
                return

            duration = time.time() - self._start_time if self._start_time else 0

            self._view.show_success_infobar(
                '完成',
                f'打包完成, 总耗时: {duration:.2f}s',
                duration=-1,
                is_closable=True
            )

            self._view.finish_state_tooltip('就绪', '打包完成')

            if self._model.output_dir:
                os.startfile(self._model.output_dir)

            QApplication.alert(self._view)

        self._start_thread = RunInThread()
        self._start_thread.set_start_func(start)
        self._start_thread.set_finished_func(finished)
        self._start_thread.start()

        self._view.show_state_tooltip('运行中...', '正在打包, 请稍等')

    # ==========================
    # 信号绑定
    # ==========================

    def bind(self):

        self._view.get_mask().droped_file_url.connect(self._source_script_changed)
        self._view.get_source_script_btn().clicked.connect(self._open_file_dialog)
        self._view.get_output_path_btn().clicked.connect(self._output_dir_changed)
        self._view.get_icon_btn().clicked.connect(self._icon_changed)
        self._view.get_mode_radiobutton().checkedChanged.connect(self._packaged_mode_changed)
        self._view.get_start_btn().clicked.connect(self._start)


if __name__ == '__main__':
    app = QApplication([])
    presenter = BasicPresenter()
    presenter.view.show()
    app.exec()
