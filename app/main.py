# main.py
import os
import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from window import HttpLLMChatWindow
from core.settings import load_theme


# Force QtWebEngine / Chromium to run without GPU (stops EGL errors)
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-software-rasterizer"
# If needed on Wayland:
# os.environ["QT_QPA_PLATFORM"] = "xcb"


def main():
    app = QApplication(sys.argv)

    base_dir = Path(__file__).resolve().parent

    # Load themed QSS from ui/style.qss
    style_path = base_dir / "ui" / "style.qss"
    if style_path.exists():
        raw_qss = style_path.read_text(encoding="utf-8")
        theme = load_theme()

        replacements = {
            # core text / bg / accent
            "{{QT_BG}}": theme.get("qt_bg", theme.get("bg", "#111111")),
            "{{QT_FG}}": theme.get("qt_fg", theme.get("fg", "#eeeeee")),
            "{{QT_ACCENT}}": theme.get("qt_accent", "#4a90e2"),
            "{{QT_ACCENT_HOVER}}": theme.get("qt_accent_hover", "#5aa0f2"),
            "{{QT_ACCENT_DISABLED}}": theme.get("qt_accent_disabled", "#555555"),
            "{{QT_BORDER}}": theme.get("qt_border", "#333333"),

            # new exported variables (defaults taken from your old hard-coded QSS)
            "{{QT_SIDEBAR_BG}}": theme.get("qt_sidebar_bg", "#101010"),
            "{{QT_SIDEBAR_SELECTED_BG}}": theme.get("qt_sidebar_selected_bg", "#262626"),
            "{{QT_SPLITTER_BG}}": theme.get("qt_splitter_bg", "#181818"),
            "{{QT_INPUT_BG}}": theme.get("qt_input_bg", "#121212"),

            "{{QT_BUTTON_BG}}": theme.get("qt_button_bg", "#181818"),
            "{{QT_BUTTON_HOVER_BG}}": theme.get("qt_button_hover_bg", "#222222"),
            "{{QT_BUTTON_PRESSED_BG}}": theme.get("qt_button_pressed_bg", "#262626"),
            "{{QT_BUTTON_DISABLED_BG}}": theme.get("qt_button_disabled_bg", "#141414"),
            "{{QT_BUTTON_DISABLED_FG}}": theme.get("qt_button_disabled_fg", "#555555"),

            "{{QT_SEARCH_TOGGLE_ON_BG}}": theme.get("qt_search_toggle_on_bg", "#2b7a3f"),
            "{{QT_SEARCH_TOGGLE_ON_HOVER_BG}}": theme.get("qt_search_toggle_on_hover_bg", "#33994c"),

            "{{QT_CHECKBOX_BG}}": theme.get("qt_checkbox_bg", "#181818"),
            "{{QT_CHECKBOX_CHECKED_BG}}": theme.get("qt_checkbox_checked_bg", "#2b7a3f"),

            "{{QT_SCROLLBAR_BG}}": theme.get("qt_scrollbar_bg", "#111111"),
            "{{QT_SCROLLBAR_HANDLE_BG}}": theme.get("qt_scrollbar_handle_bg", "#444444"),
        }


        for k, v in replacements.items():
            raw_qss = raw_qss.replace(k, v)

        raw_qss = style_path.read_text(encoding="utf-8")
        theme = load_theme()
        for key, val in theme.items():
            token = "{{" + key.upper() + "}}"
            raw_qss = raw_qss.replace(token, val)

        # DEBUG
        if "{{" in raw_qss or "}}" in raw_qss:
            print("QSS still has unreplaced placeholders!")
            # optionally print offending lines
            for line in raw_qss.splitlines():
                if "{{" in line or "}}" in line:
                    print("BAD LINE:", line)

        app.setStyleSheet(raw_qss)


    w = HttpLLMChatWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
