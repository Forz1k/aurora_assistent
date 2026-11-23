"""Анимированный персонаж поверх рабочего стола."""

from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QPainterPath, QGuiApplication, QMovie, QPainter
from PySide6.QtWidgets import QMenu, QPushButton, QWidget


CORNERS = {"br": "Справа внизу", "bl": "Слева внизу", "tr": "Справа вверху", "tl": "Слева вверху"}
SIZES = (80, 120, 180)


class CharacterWindow(QWidget):
    def __init__(self, settings):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                 Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus |
                 Qt.WindowType.WindowTransparentForInput)
        super().__init__(None, flags)
        self.settings = settings
        self.animation = "idle"
        self.mouth_level = 0
        self.movie = QMovie(self)
        self.movie.frameChanged.connect(self.update_frame)
        self.movie.finished.connect(self.animation_finished)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        app = QGuiApplication.instance()
        for screen in app.screens():
            self.watch_screen(screen)
        app.screenAdded.connect(self.watch_screen)
        app.screenRemoved.connect(self.place)
        app.primaryScreenChanged.connect(self.place)

    def watch_screen(self, screen):
        screen.availableGeometryChanged.connect(self.place)
        self.place()

    def screen_for_character(self):
        name = self.settings.value("character/screen", "")
        return next((s for s in QGuiApplication.screens() if s.name() == name),
                    QGuiApplication.primaryScreen())

    def place(self, *_):
        screen = self.screen_for_character()
        if screen is None:
            return
        area = screen.availableGeometry()
        size = self.settings.value("character/size", 120, type=int)
        size = min(size if size in SIZES else 120, area.width(), area.height())
        corner = self.settings.value("character/corner", "br")
        if corner not in CORNERS:
            corner = "br"
        dx = min(16, (area.width() - size) // 2)
        dy = min(16, (area.height() - size) // 2)
        x = dx if corner.endswith("l") else area.width() - size - dx
        y = dy if corner.startswith("t") else area.height() - size - dy
        self.setScreen(screen)
        self.setFixedSize(size, size)
        self.move(area.topLeft() + QPoint(x, y))

    def apply_setting(self, key, value):
        self.settings.setValue("character/" + key, value)
        self.place()
        self.setVisible(self.settings.value("character/visible", False, type=bool))

    def menu_button(self, parent):
        button = QPushButton("Персонаж", parent)
        menu = QMenu(button)
        button.setMenu(menu)

        submenus = []

        def populate():
            for submenu in submenus:
                submenu.deleteLater()
            submenus.clear()
            menu.clear()
            visible = menu.addAction("Показывать поверх окон")
            visible.setCheckable(True)
            visible.setChecked(self.settings.value("character/visible", False, type=bool))
            visible.triggered.connect(lambda checked: self.apply_setting("visible", checked))
            for key, title, choices, current in (
                ("screen", "Монитор", [(s.name(), s.name()) for s in QGuiApplication.screens()],
                 self.screen_for_character().name()),
                ("corner", "Положение", CORNERS.items(), self.settings.value("character/corner", "br")),
                ("size", "Размер", [(n, str(n)) for n in SIZES], self.settings.value("character/size", 120, type=int)),
            ):
                submenu = QMenu(title, menu)
                submenus.append(submenu)
                menu.addMenu(submenu)
                for value, label in choices:
                    action = submenu.addAction(label)
                    action.setCheckable(True)
                    action.setChecked(value == current)
                    action.triggered.connect(lambda _, k=key, v=value: self.apply_setting(k, v))
        menu.aboutToShow.connect(populate)
        return button

    def set_state(self, state):
        animation = {
            "STARTING": "listening", "WAITING": "listening", "LISTENING": "listening",
            "TRANSCRIBING": "thinking", "THINKING": "thinking", "EXECUTING": "executing",
            "SPEAKING": "speaking", "SUCCESS": "success", "ERROR": "error",
        }.get(state, "idle")
        if self.animation != animation:
            self.mouth_level = 0
            self.animation = animation
            if self.isVisible():
                self.play()

    def play(self):
        self.movie.stop()
        path = Path(__file__).resolve().parents[1] / "assets" / "character"
        self.movie.setFileName(str(path / (self.animation + ".webp")))
        self.movie.start()

    def animation_finished(self):
        if self.animation in ("success", "error"):
            self.set_state("IDLE")

    def update_frame(self, _):
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self.play()

    def hideEvent(self, event):
        self.movie.stop()
        super().hideEvent(event)

    def set_mouth_level(self, level):
        if self.animation == "speaking" and level != self.mouth_level:
            self.mouth_level = level
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        frame = self.movie.currentPixmap()
        painter.drawPixmap(self.rect(), frame)
        if self.mouth_level and not frame.isNull():
            # Coordinates follow the lip seam in the original square portrait.
            painter.scale(self.width() / 1254, self.height() / 1254)
            gap = self.mouth_level * 1.5
            mouth = QPainterPath()
            mouth.moveTo(583, 445)
            mouth.quadTo(624, 455, 666, 453)
            mouth.quadTo(627, 456 + gap, 583, 445)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.fillPath(mouth, QColor("#622c40"))
            lip = QRectF(604, 455, 44, 13)
            source = QRectF(lip.x() * frame.width() / 1254, lip.y() * frame.height() / 1254,
                            lip.width() * frame.width() / 1254, lip.height() * frame.height() / 1254)
            painter.drawPixmap(lip.translated(0, gap * 0.65), frame, source)
