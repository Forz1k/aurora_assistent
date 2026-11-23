import os

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QWidget

from aurora.ui.character import CharacterWindow


def test_character_controls_and_transparency(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "chat.ini"), QSettings.Format.IniFormat)
    owner = QWidget()
    character = CharacterWindow(settings)
    try:
        menu = character.menu_button(owner).menu()
        menu.aboutToShow.emit()
        menu.actions()[0].trigger()
        assert character.isVisible()
        menu.actions()[2].menu().actions()[-1].trigger()
        menu.actions()[3].menu().actions()[0].trigger()
        area = character.screen().availableGeometry()
        assert character.x() == area.x() + 16 and character.y() == area.y() + 16
        assert character.size().width() == 80
        assert character.windowFlags() & Qt.WindowType.WindowTransparentForInput
        image = character.grab().toImage()
        assert image.pixelColor(0, 0).alpha() == 0
        assert image.pixelColor(image.width() // 2, image.height() // 2).alpha() >= 250
        menu.actions()[0].trigger()
        assert not character.isVisible()
        settings.sync()
        reopened = QSettings(settings.fileName(), QSettings.Format.IniFormat)
        assert reopened.value("character/corner") == "tl"
        assert reopened.value("character/size", type=int) == 80
        assert not reopened.value("character/visible", type=bool)
    finally:
        character.close()
        owner.close()
        app.processEvents()


def test_animation_states(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    character = CharacterWindow(QSettings(str(tmp_path / "chat.ini"), QSettings.Format.IniFormat))
    try:
        character.show()
        for state in ("LISTENING", "THINKING", "EXECUTING", "SPEAKING", "SUCCESS", "ERROR", "IDLE"):
            character.set_state(state)
            assert character.movie.fileName().endswith(state.lower() + ".webp")
            assert character.movie.frameCount() > 1
            assert character.movie.jumpToNextFrame()
        character.hide()
        assert character.movie.state() == character.movie.MovieState.NotRunning
    finally:
        character.close()
        app.processEvents()
