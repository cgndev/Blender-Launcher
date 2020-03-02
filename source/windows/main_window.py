import sys
import threading
from pathlib import Path

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import (QEvent, QFile, QPoint, QSettings, Qt, QTextStream,
                          QThread, QTimer, pyqtSignal)
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtWidgets import (
    QAction, QApplication, QMainWindow, QMenu, QStyle, QSystemTrayIcon)

from modules._platform import get_platform
from modules.settings import *
from threads.scraper import Scraper
from ui.main_window_design import Ui_MainWindow
from widgets.download_widget import DownloadWidget
from widgets.library_widget import LibraryWidget
from windows.settings_window import SettingsWindow


class BlenderLauncher(QMainWindow, Ui_MainWindow):
    def __init__(self, app):
        super().__init__()
        self.setupUi(self)

        # Global Scope
        self.app = app
        self.favorite = None
        self.pos = self.pos()
        self.pressed = False

        # Setup Window
        self.setWindowTitle("Blender Launcher")
        self.setWindowFlags(Qt.FramelessWindowHint)

        # Setup Font
        QFontDatabase.addApplicationFont(
            ":/resources/fonts/Inter-Regular.otf")
        font = QFont("Inter", 10)
        font.setHintingPreference(QFont.PreferNoHinting)
        self.app.setFont(font)

        # Setup Style
        file = QFile(":/resources/styles/global.qss")
        file.open(QFile.ReadOnly | QFile.Text)
        stream = QTextStream(file)
        self.app.setStyleSheet(stream.readAll())

        self.SettingsButton.setProperty("HeaderButton", True)
        self.MinimizeButton.setProperty("HeaderButton", True)
        self.CloseButton.setProperty("HeaderButton", True)
        self.CloseButton.setProperty("CloseButton", True)

        # Connect Buttons
        self.SettingsButton.clicked.connect(self.show_settings_window)
        self.MinimizeButton.clicked.connect(self.showMinimized)
        self.CloseButton.clicked.connect(self.close)

        # Draw Library
        library_folder = Path(get_library_folder())
        dirs = library_folder.iterdir()

        if get_platform() == 'Windows':
            blender_exe = "blender.exe"
        elif get_platform() == 'Linux':
            blender_exe = "blender"

        for dir in dirs:
            path = library_folder / dir / blender_exe

            if path.is_file():
                self.draw_to_library(dir)

        self.update()

        # Draw Tray Icon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(
            self.style().standardIcon(QStyle.SP_TitleBarMenuButton))
        self.tray_icon.setToolTip("Blender Launcher")
        self.tray_icon.activated.connect(self.tray_icon_activated)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit)
        self.tray_menu = QMenu()
        self.tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(self.tray_menu)

        self.tray_icon_trigger = QTimer(self)
        self.tray_icon_trigger.setSingleShot(True)
        self.tray_icon_trigger.timeout.connect(self._show)

        self.show()
        self.tray_icon.show()

    def _show(self):
        self.activateWindow()
        self.show()

    def launch_favorite(self):
        if self.favorite is not None:
            self.favorite.launch()

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.tray_icon_trigger.start(QApplication.doubleClickInterval())
        elif reason == QSystemTrayIcon.DoubleClick:
            self.tray_icon_trigger.stop()
            self.launch_favorite()

    def quit(self):
        self.timer.cancel()
        self.tray_icon.hide()
        self.app.quit()

    def update(self):
        print("Updating...")
        self.timer = threading.Timer(600.0, self.update)
        self.timer.start()
        self.scraper = Scraper(self)
        self.scraper.links.connect(self.test)
        self.scraper.start()

    def test(self, links):
        old_links = []
        new_links = []

        old_links.extend(self.get_list_widget_items(
            self.LibraryStableListWidget, 'path'))
        old_links.extend(self.get_list_widget_items(
            self.LibraryDailyListWidget, 'path'))
        old_links.extend(self.get_list_widget_items(
            self.LibraryExperimentalListWidget, 'path'))

        old_links.extend(self.get_list_widget_items(
            self.DownloadsStableListWidget, 'link'))
        old_links.extend(self.get_list_widget_items(
            self.DownloadsDailyListWidget, 'link'))
        old_links.extend(self.get_list_widget_items(
            self.DownloadsExperimentalListWidget, 'link'))

        for link in links:
            if Path(link[1]).stem not in old_links:
                new_links.append(link)

        for link in new_links:
            self.draw_to_downloads(link)

    def get_list_widget_items(self, list_widget, type):
        items = []

        for i in range(list_widget.count()):
            link = list_widget.itemWidget(list_widget.item(i)).link

            if type == 'link':
                name = Path(link).stem
            elif type == 'path':
                name = Path(link).name

            items.append(name)

        return items

    def draw_to_downloads(self, link):
        branch = link[0]

        if branch == 'stable':
            list_widget = self.DownloadsStableListWidget
        elif branch == 'daily':
            list_widget = self.DownloadsDailyListWidget
        else:
            list_widget = self.DownloadsExperimentalListWidget

        item = QtWidgets.QListWidgetItem()
        widget = DownloadWidget(self, list_widget, item, link[1])
        item.setSizeHint(widget.sizeHint())
        list_widget.addItem(item)
        list_widget.setItemWidget(item, widget)

    def draw_to_library(self, dir):
        item = QtWidgets.QListWidgetItem()
        widget = LibraryWidget(self, item, dir)
        item.setSizeHint(widget.sizeHint())

        if widget.branch == 'stable':
            list_widget = self.LibraryStableListWidget
        elif widget.branch == 'daily':
            list_widget = self.LibraryDailyListWidget
        else:
            list_widget = self.LibraryExperimentalListWidget

        widget.list_widget = list_widget
        list_widget.insertItem(0, item)
        list_widget.setItemWidget(item, widget)

    def show_settings_window(self):
        self.settings_window = SettingsWindow()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def mousePressEvent(self, event):
        self.pos = event.globalPos()
        self.pressing = True

    def mouseMoveEvent(self, event):
        if self.pressing:
            delta = QPoint(event.globalPos() - self.pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.pos = event.globalPos()

    def mouseReleaseEvent(self, QMouseEvent):
        self.pressing = False