"""Screenshot harness used for visual QA during development."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from wifispectrum.app import ApplicationContext  # noqa: E402
from wifispectrum.ui.main_window import MainWindow  # noqa: E402
from wifispectrum.ui.theme import apply_theme  # noqa: E402

FONT_FILES = [
    "segoeui.ttf",
    "segoeuib.ttf",
    "seguisb.ttf",
    "segoeuil.ttf",
    "consola.ttf",
    "consolab.ttf",
    "arial.ttf",
]


def load_system_fonts() -> None:
    """The offscreen QPA plugin has no font database on Windows; load files."""
    if not sys.platform.startswith("win"):
        return
    fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    for name in FONT_FILES:
        candidate = fonts / name
        if candidate.exists():
            QFontDatabase.addApplicationFont(str(candidate))


def wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main() -> int:
    out = ROOT / "artifacts"
    out.mkdir(exist_ok=True)
    app = QApplication(sys.argv)
    load_system_fonts()
    apply_theme(app)

    ctx = ApplicationContext()
    ctx.settings.set("demo_mode", True, persist=False)
    window = MainWindow(ctx)

    size = (1600, 900)
    pages: list[str] = []
    history_row: int | None = None
    track_bssid: str | None = None
    for argument in sys.argv[1:]:
        if argument.startswith("--size="):
            try:
                width, height = argument.split("=", 1)[1].lower().split("x")
                size = (int(width), int(height))
            except ValueError:
                print(f"ignoring malformed --size={argument}")
        elif argument.startswith("--history-row="):
            try:
                history_row = int(argument.split("=", 1)[1])
            except ValueError:
                print(f"ignoring malformed --history-row={argument}")
        elif argument.startswith("--track="):
            track_bssid = argument.split("=", 1)[1]
        else:
            pages.append(argument)
    pages = pages or ["spectrum"]
    window.resize(*size)
    window.show()
    window.startup()
    wait(5200)

    for page in pages:
        window.navigate(page)
        wait(900)
        if page == "history" and history_row is not None:
            history_page = window.pages.get("history")
            if history_page is None:
                continue
            wait(1400)
            history_page._select_scan(history_row, 0)
            wait(700)
            print(f"history row {history_row} selected -> detail stack {history_page.detail_stack.currentIndex()}")
        if page == "signal" and track_bssid:
            signal_page = window.pages.get("signal")
            if signal_page is None:
                continue
            wait(1200)
            snapshot = window._last_snapshot
            aps = snapshot.aps if snapshot else []
            if track_bssid == "strongest":
                target = snapshot.strongest if snapshot else None
            else:
                target = next((a for a in aps if a.bssid == track_bssid), None)
            if target is not None:
                signal_page.track(target.bssid)
                wait(1600)
                print(f"tracked {target.bssid} ({target.display_ssid}) on channel {target.channel}")
            else:
                print(f"could not track {track_bssid}: no such network in the last snapshot")
        suffix = "" if size == (1600, 900) else f"_{size[0]}x{size[1]}"
        target = out / f"{page}{suffix}.png"
        window.grab().save(str(target), "PNG")
        print(f"saved {target}")

    ctx.monitor.stop()
    if ctx.history is not None:
        ctx.history.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
