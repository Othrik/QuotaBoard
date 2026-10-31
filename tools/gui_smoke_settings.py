import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

from quotaboard.config import Config
from quotaboard.ui.settings_dialog import SettingsDialog

try:
    app = QApplication([])
    geo = app.primaryScreen().availableGeometry() if app.primaryScreen() else None
    print("primaryScreen:", app.primaryScreen(), "| geo:", geo)

    cfg = Config.__new__(Config)
    cfg._data = {"platforms": {}, "manual": {}, "cache": {},
                 "refresh_interval_minutes": 30}
    cfg.path = None

    d = SettingsDialog(cfg)
    d.show()
    print("dialog:", d.width(), "x", d.height())
    if geo:
        print("fits screen:", d.height() <= geo.height())
    print("OK")
except Exception:
    traceback.print_exc()
    sys.exit(1)
