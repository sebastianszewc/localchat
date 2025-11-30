from pathlib import Path

from PyQt5.QtCore import Qt, QEvent, QThread, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QKeySequence, QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QComboBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QMenu,
    QInputDialog,
    QCheckBox,
    QShortcut,
    QFrame,
)

from core import chat_state
from core.chat_title import build_chat_title
from core.backend import (
    API_URL,
    AVAILABLE_MODELS,
    DEFAULT_MODEL_NAME,
    MAX_TOKENS,
    N_PREDICT,
    Worker,
)
from core.settings import (
    load_default_model,
    save_default_model,
    load_theme,
    get_web_followup_instruction,
    load_web_settings,
    is_title_planner_enabled,
)
from ui import renderer
from ui.settings_window import SettingsOverlay
from web.web_search import WebSearchWorker


# --------------------------------------------------------------------------- #
#  Small widgets / workers
# --------------------------------------------------------------------------- #


class ChatListItemWidget(QWidget):
    delete_clicked = pyqtSignal()

    def __init__(self, title: str, parent=None):
        super().__init__(parent)

        self.setAttribute(Qt.WA_StyledBackground, False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)

        self.label = QLabel(title)
        self.label.setObjectName("ChatListTitleLabel")
        self.label.setStyleSheet("background: transparent;")
        layout.addWidget(self.label, 1)

        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("ChatListCloseButton")
        self.close_button.setFlat(True)
        self.close_button.setFocusPolicy(Qt.NoFocus)
        self.close_button.setVisible(False)
        self.close_button.setFixedSize(18, 18)
        self.close_button.setStyleSheet(
            "QPushButton {"
            "  border: none;"
            "  background: transparent;"
            "  padding: 0px;"
            "}"
        )
        self.close_button.clicked.connect(self.delete_clicked.emit)
        layout.addWidget(self.close_button)

    def set_title(self, title: str) -> None:
        self.label.setText(title)

    def enterEvent(self, event):
        self.close_button.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.close_button.setVisible(False)
        super().leaveEvent(event)


class TitleWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, history, model_name):
        super().__init__()
        self.history = history
        self.model_name = model_name

    def run(self):
        try:
            title = build_chat_title(self.history, self.model_name)
            self.finished.emit(title or "")
        except Exception as e:
            self.error.emit(str(e))


# --------------------------------------------------------------------------- #
#  Main window
# --------------------------------------------------------------------------- #


class HttpLLMChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ollama Chat (local)")
        self.resize(1200, 900)

        # UI scale
        base_font = QApplication.font()
        self.base_font_size = base_font.pointSizeF() or 10.0
        self.default_ui_scale = 1.5
        self.ui_scale = self.default_ui_scale

        # Chat / worker state
        self.chats = []  # list[dict]: {"title","model","history","html"}
        self.current_chat_index = -1

        self.thread = None
        self.worker = None
        self.search_thread = None
        self.search_worker = None

        # Single-job guard (chat + title planner + web follow-up)
        self.llm_busy = False

        # Title planner worker
        self.title_thread = None
        self.title_worker = None

        # Default model
        self.default_model_name = load_default_model()
        if self.default_model_name not in AVAILABLE_MODELS:
            self.default_model_name = DEFAULT_MODEL_NAME
            save_default_model(self.default_model_name)

        # Root splitter
        self.splitter = QSplitter(Qt.Horizontal)
        self._sidebar_last_width = 260
        self.setCentralWidget(self.splitter)

        self._build_sidebar(self.splitter)
        self._build_main_panel(self.splitter)

        self._load_or_create_chats()
        self._init_zoom_shortcuts()
        self.apply_ui_scale()

        # Settings overlay
        self.settings_overlay = SettingsOverlay(self)

    # ------------------------------------------------------------------ #
    #  Basic properties / helpers
    # ------------------------------------------------------------------ #

    @property
    def current_chat(self):
        if 0 <= self.current_chat_index < len(self.chats):
            return self.chats[self.current_chat_index]
        return None

    @property
    def current_model(self):
        chat = self.current_chat
        return chat["model"] if chat else DEFAULT_MODEL_NAME

    @current_model.setter
    def current_model(self, value):
        chat = self.current_chat
        if chat:
            chat["model"] = value

    # ------------------------------------------------------------------ #
    #  UI construction
    # ------------------------------------------------------------------ #

    def _build_sidebar(self, splitter: QSplitter):
        """Left sidebar: chat list + header."""
        left_panel = QWidget()
        self.left_panel = left_panel

        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(6)

        # Header row
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        self.label_chats = QLabel("Chats")
        header_layout.addWidget(self.label_chats)
        header_layout.addStretch(1)

        self.new_chat_button = QPushButton("+")
        self.new_chat_button.setToolTip("New chat (Ctrl+T)")
        self.new_chat_button.setFixedWidth(28)
        self.new_chat_button.clicked.connect(self.on_new_chat_clicked)
        header_layout.addWidget(self.new_chat_button)

        self.sidebar_toggle_button = QPushButton("⟨")
        self.sidebar_toggle_button.setToolTip("Collapse / expand sidebar")
        self.sidebar_toggle_button.setCheckable(True)
        self.sidebar_toggle_button.setFixedWidth(24)
        self.sidebar_toggle_button.clicked.connect(self.toggle_sidebar)
        header_layout.addWidget(self.sidebar_toggle_button)

        left_layout.addLayout(header_layout)

        # Chat list
        self.chat_list = QListWidget()
        self.chat_list.setObjectName("ChatList")
        self.chat_list.setFrameShape(QFrame.NoFrame)
        self.chat_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_list.currentRowChanged.connect(self.on_chat_selected)

        # Context menu
        self.chat_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chat_list.customContextMenuRequested.connect(self.on_chat_context_menu)

        left_layout.addWidget(self.chat_list, 1)

        splitter.addWidget(left_panel)
        splitter.setStretchFactor(0, 0)
        left_panel.setMinimumWidth(220)

    def _build_main_panel(self, splitter: QSplitter):
        """Right panel: model bar + HTML view + input."""
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(6)

        # Top bar: model selector + default + settings
        top_bar = QHBoxLayout()
        right_layout.addLayout(top_bar)

        self.label_model = QLabel("Model:")
        top_bar.addWidget(self.label_model)

        self.model_combo = QComboBox()
        if AVAILABLE_MODELS:
            self.model_combo.addItems(AVAILABLE_MODELS)
        else:
            self.model_combo.addItem(DEFAULT_MODEL_NAME)

        self.model_combo.setCurrentText(self.default_model_name)
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        top_bar.addWidget(self.model_combo)

        self.default_checkbox = QCheckBox("Default")
        self.default_checkbox.setChecked(
            self.model_combo.currentText().strip() == self.default_model_name
        )
        self.default_checkbox.toggled.connect(self.on_default_model_toggled)
        top_bar.addWidget(self.default_checkbox)
        top_bar.addStretch(1)

        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self.on_settings_button_clicked)
        top_bar.addWidget(self.settings_button)

        # Chat HTML view
        self.chat_view = QWebEngineView()
        theme = load_theme()
        bg = theme.get("bg", "#111111")
        self.chat_view.setAttribute(Qt.WA_StyledBackground, True)
        self.chat_view.setStyleSheet(f"background-color: {bg};")
        self.chat_view.page().setBackgroundColor(QColor(bg))
        right_layout.addWidget(self.chat_view, 4)

        # Input box
        self.input_box = QPlainTextEdit()
        self.input_box.setPlaceholderText("Enter message ... ")

        self.input_min_height = 120
        self.input_max_height = 400
        self.input_box.setFixedHeight(self.input_min_height)

        self.input_box.textChanged.connect(self.adjust_input_height)
        self.input_box.installEventFilter(self)
        right_layout.addWidget(self.input_box)
        self.adjust_input_height()

        # Overlay buttons (web toggle + send)
        self.overlay_buttons = QWidget(right_panel)
        self.overlay_buttons.setObjectName("ChatButtonsOverlay")
        self.overlay_buttons.setAttribute(Qt.WA_StyledBackground, False)

        overlay_layout = QHBoxLayout(self.overlay_buttons)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setSpacing(4)

        self.search_toggle = QPushButton("Search web", self.overlay_buttons)
        self.search_toggle.setObjectName("searchToggle")
        self.search_toggle.setCheckable(True)

        try:
            ws = load_web_settings()
            self.search_toggle.setEnabled(bool(ws.get("enabled", True)))
        except Exception:
            pass

        overlay_layout.addWidget(self.search_toggle)

        self.send_button = QPushButton("Send", self.overlay_buttons)
        self.send_button.setObjectName("sendButton")
        self.send_button.clicked.connect(self.on_send_clicked)
        overlay_layout.addWidget(self.send_button)

        self._position_overlay_buttons()

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 1)

    def _position_overlay_buttons(self):
        """Position overlay buttons at bottom-right of chat_view."""
        if not hasattr(self, "overlay_buttons") or not hasattr(self, "chat_view"):
            return

        right_panel = self.chat_view.parentWidget()
        if right_panel is None:
            return

        self.overlay_buttons.adjustSize()
        w = self.overlay_buttons.width()
        h = self.overlay_buttons.height()

        gv = self.chat_view.geometry()
        margin = 16

        x = gv.right() - w - margin
        y = gv.bottom() - h - margin

        if y < gv.top() + margin:
            y = gv.top() + margin

        self.overlay_buttons.setGeometry(x, y, w, h)

    # ------------------------------------------------------------------ #
    #  Chat load / create / persistence
    # ------------------------------------------------------------------ #

    def _load_or_create_chats(self):
        loaded = chat_state.load_chats()
        if loaded is not None:
            self.chats, current_idx = loaded

            # Rebuild HTML from history
            for chat in self.chats:
                fragments = []
                for msg in chat.get("history", []):
                    role = (msg.get("role") or "").lower()
                    kind = (msg.get("kind") or "").strip()
                    content = msg.get("content") or ""
                    if not content:
                        continue

                    if kind in ("web_links", "web_results"):
                        fragments.append(renderer.render_web_links_block(content))
                        continue

                    if role == "system":
                        frag = renderer.render_system_msg(content)
                    elif role == "user":
                        frag = renderer.render_user_msg(content)
                    elif role == "assistant":
                        frag = renderer.render_assistant_msg("", content)
                    else:
                        continue

                    fragments.append(frag)

                chat["html"] = "".join(fragments)

            for chat in self.chats:
                self._add_chat_list_item(chat.get("title", "Untitled"))

            self.chat_list.setCurrentRow(current_idx)
            return

        # First run
        first = chat_state.make_new_chat("Chat 1", self.default_model_name)
        self.chats.append(first)
        self._add_chat_list_item(first["title"])
        self.chat_list.setCurrentRow(0)

        self.append_system(f"Backend: {API_URL}")
        self.append_system(f"Available models: {', '.join(AVAILABLE_MODELS)}")
        self.append_system(f"Current model: {self.current_model}")
        self.append_system(f"MAX_TOKENS={MAX_TOKENS}, N_PREDICT={N_PREDICT}")

    def _add_chat_list_item(self, title: str) -> None:
        item = QListWidgetItem()
        widget = ChatListItemWidget(title)
        widget.delete_clicked.connect(
            lambda: self._delete_chat_at(self.chat_list.row(item))
        )
        self.chat_list.addItem(item)
        self.chat_list.setItemWidget(item, widget)

        app = QApplication.instance()
        if app is not None:
            f = app.font()
            widget.setFont(f)
            widget.label.setFont(f)
            widget.close_button.setFont(f)

    def closeEvent(self, event):
        chat_state.save_chats(self.chats, self.current_chat_index)
        super().closeEvent(event)

    # ------------------------------------------------------------------ #
    #  Shortcuts / Events
    # ------------------------------------------------------------------ #

    def _init_zoom_shortcuts(self):
        self.shortcut_zoom_in = QShortcut(QKeySequence("Ctrl++"), self)
        self.shortcut_zoom_in.activated.connect(
            lambda: self.change_ui_scale(1.1)
        )

        self.shortcut_zoom_in2 = QShortcut(QKeySequence("Ctrl+="), self)
        self.shortcut_zoom_in2.activated.connect(
            lambda: self.change_ui_scale(1.1)
        )

        self.shortcut_zoom_out = QShortcut(QKeySequence("Ctrl+-"), self)
        self.shortcut_zoom_out.activated.connect(
            lambda: self.change_ui_scale(1.0 / 1.1)
        )

        self.shortcut_zoom_reset = QShortcut(QKeySequence("Ctrl+0"), self)
        self.shortcut_zoom_reset.activated.connect(self.reset_ui_scale)

        self.shortcut_new_chat = QShortcut(QKeySequence("Ctrl+T"), self)
        self.shortcut_new_chat.activated.connect(self.on_new_chat_clicked)

    def eventFilter(self, obj, event):
        if obj is self.input_box and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if event.modifiers() & Qt.ShiftModifier:
                    return False
                self.on_send_clicked()
                return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "settings_overlay") and self.settings_overlay.isVisible():
            self.settings_overlay.resize_to_parent()
        self._position_overlay_buttons()

    # ------------------------------------------------------------------ #
    #  Settings / theme
    # ------------------------------------------------------------------ #

    def on_settings_button_clicked(self):
        if not self.settings_overlay:
            return
        self.settings_overlay.sync_from_settings()
        self.settings_overlay.resize_to_parent()
        self.settings_overlay.show()
        self.settings_overlay.raise_()
        self.settings_overlay.setFocus()

    def reload_theme(self):
        """Reapply theme (QSS + webview bg + HTML)."""
        theme = load_theme()

        # Web view background
        bg = theme.get("bg", "#111111")
        if hasattr(self, "chat_view"):
            self.chat_view.setAttribute(Qt.WA_StyledBackground, True)
            self.chat_view.setStyleSheet(f"background-color: {bg};")
            self.chat_view.page().setBackgroundColor(QColor(bg))

        # QSS for the whole app
        app = QApplication.instance()
        if app is not None:
            base_dir = Path(__file__).resolve().parent
            style_path = base_dir / "ui" / "style.qss"
            if style_path.exists():
                raw_qss = style_path.read_text(encoding="utf-8")

                replacements = {
                    "{{QT_BG}}": theme.get("qt_bg", theme.get("bg", "#111111")),
                    "{{QT_FG}}": theme.get("qt_fg", theme.get("fg", "#eeeeee")),
                    "{{QT_ACCENT}}": theme.get("qt_accent", "#4a90e2"),
                    "{{QT_ACCENT_HOVER}}": theme.get("qt_accent_hover", "#5aa0f2"),
                    "{{QT_ACCENT_DISABLED}}": theme.get(
                        "qt_accent_disabled", "#555555"
                    ),
                    "{{QT_BORDER}}": theme.get("qt_border", "#333333"),
                    "{{QT_SIDEBAR_BG}}": theme.get(
                        "qt_sidebar_bg", "#101010"
                    ),
                    "{{QT_SIDEBAR_SELECTED_BG}}": theme.get(
                        "qt_sidebar_selected_bg", "#262626"
                    ),
                    "{{QT_SPLITTER_BG}}": theme.get(
                        "qt_splitter_bg", "#181818"
                    ),
                    "{{QT_INPUT_BG}}": theme.get(
                        "qt_input_bg", "#121212"
                    ),
                    "{{QT_BUTTON_BG}}": theme.get(
                        "qt_button_bg", "#181818"
                    ),
                    "{{QT_BUTTON_HOVER_BG}}": theme.get(
                        "qt_button_hover_bg", "#222222"
                    ),
                    "{{QT_BUTTON_PRESSED_BG}}": theme.get(
                        "qt_button_pressed_bg", "#262626"
                    ),
                    "{{QT_BUTTON_DISABLED_BG}}": theme.get(
                        "qt_button_disabled_bg", "#141414"
                    ),
                    "{{QT_BUTTON_DISABLED_FG}}": theme.get(
                        "qt_button_disabled_fg", "#555555"
                    ),
                    "{{QT_SEARCH_TOGGLE_ON_BG}}": theme.get(
                        "qt_search_toggle_on_bg", "#2b7a3f"
                    ),
                    "{{QT_SEARCH_TOGGLE_ON_HOVER_BG}}": theme.get(
                        "qt_search_toggle_on_hover_bg", "#33994c"
                    ),
                    "{{QT_CHECKBOX_BG}}": theme.get(
                        "qt_checkbox_bg", "#181818"
                    ),
                    "{{QT_CHECKBOX_CHECKED_BG}}": theme.get(
                        "qt_checkbox_checked_bg", "#2b7a3f"
                    ),
                    "{{QT_SCROLLBAR_BG}}": theme.get(
                        "qt_scrollbar_bg", "#111111"
                    ),
                    "{{QT_SCROLLBAR_HANDLE_BG}}": theme.get(
                        "qt_scrollbar_handle_bg", "#444444"
                    ),
                }

                for k, v in replacements.items():
                    raw_qss = raw_qss.replace(k, v)

                app.setStyleSheet(raw_qss)

        if hasattr(self, "_refresh_view"):
            self._refresh_view()

    def on_settings_updated(self):
        """Called by SettingsOverlay after Save."""
        self.default_model_name = load_default_model()

        if hasattr(self, "model_combo"):
            idx = self.model_combo.findText(self.default_model_name)
            if idx >= 0:
                self.model_combo.blockSignals(True)
                self.model_combo.setCurrentIndex(idx)
                self.model_combo.blockSignals(False)

        if hasattr(self, "default_checkbox"):
            current = self.model_combo.currentText().strip()
            self.default_checkbox.blockSignals(True)
            self.default_checkbox.setChecked(current == self.default_model_name)
            self.default_checkbox.blockSignals(False)

        self.reload_theme()

    # ------------------------------------------------------------------ #
    #  Sidebar collapse
    # ------------------------------------------------------------------ #

    def toggle_sidebar(self):
        if not hasattr(self, "splitter"):
            return

        sizes = self.splitter.sizes()
        total = sum(sizes) or self.width() or 1

        if self.sidebar_toggle_button.isChecked():
            # Collapse
            if sizes and sizes[0] > 0:
                self._sidebar_last_width = sizes[0]
            self.splitter.setSizes([0, total])
            self.sidebar_toggle_button.setText("⟩")
        else:
            # Expand
            w = self._sidebar_last_width
            if w <= 0 or w >= total:
                w = min(260, max(200, total // 4))
            self.splitter.setSizes([w, total - w])
            self.sidebar_toggle_button.setText("⟨")

    # ------------------------------------------------------------------ #
    #  Chat management / context menu
    # ------------------------------------------------------------------ #

    def on_chat_selected(self, index: int):
        if index < 0 or index >= len(self.chats):
            return

        self.current_chat_index = index
        chat = self.chats[index]

        # Sync model combo
        self.model_combo.blockSignals(True)
        self.model_combo.setCurrentText(chat["model"])
        self.model_combo.blockSignals(False)

        # Sync default checkbox
        if hasattr(self, "default_checkbox"):
            self.default_checkbox.blockSignals(True)
            self.default_checkbox.setChecked(
                chat["model"].strip() == self.default_model_name
            )
            self.default_checkbox.blockSignals(False)

        self._refresh_view()

    def on_new_chat_clicked(self):
        title = f"Chat {len(self.chats) + 1}"
        chat = chat_state.make_new_chat(title, self.default_model_name)
        self.chats.append(chat)
        self._add_chat_list_item(title)
        self.chat_list.setCurrentRow(len(self.chats) - 1)

    def on_delete_chat_clicked(self):
        if not self.chats:
            return
        self._delete_chat_at(self.chat_list.currentRow())

    def on_chat_context_menu(self, pos):
        item = self.chat_list.itemAt(pos)
        if item is None:
            return

        row = self.chat_list.row(item)

        menu = QMenu(self)
        rename_action = menu.addAction("Rename chat")
        delete_action = menu.addAction("Delete chat")

        action = menu.exec_(self.chat_list.mapToGlobal(pos))
        if action is None:
            return

        if action == rename_action:
            self._rename_chat_at(row)
        elif action == delete_action:
            self._delete_chat_at(row)

    def _delete_chat_at(self, row: int):
        if row < 0 or row >= len(self.chats):
            return

        self.chats.pop(row)
        self.chat_list.takeItem(row)

        if not self.chats:
            new_chat = chat_state.make_new_chat("Chat 1", self.default_model_name)
            self.chats.append(new_chat)
            self._add_chat_list_item(new_chat["title"])
            self.chat_list.setCurrentRow(0)
            return

        new_row = min(row, len(self.chats) - 1)
        self.chat_list.setCurrentRow(new_row)

    def _rename_chat_at(self, row: int):
        if row < 0 or row >= len(self.chats):
            return

        chat = self.chats[row]
        old_title = chat.get("title", f"Chat {row + 1}")

        new_title, ok = QInputDialog.getText(
            self,
            "Rename chat",
            "New chat name:",
            text=old_title,
        )
        if not ok:
            return

        new_title = new_title.strip()
        if not new_title:
            return

        chat["title"] = new_title
        item = self.chat_list.item(row)
        if item is not None:
            widget = self.chat_list.itemWidget(item)
            if isinstance(widget, ChatListItemWidget):
                widget.set_title(new_title)
            else:
                item.setText(new_title)

    # ------------------------------------------------------------------ #
    #  Markdown / HTML helpers
    # ------------------------------------------------------------------ #

    def _refresh_view(self):
        chat = self.current_chat
        if not chat:
            self.chat_view.setHtml("<html><body></body></html>")
            return

        full_html = renderer.wrap_page(chat["html"])
        self.chat_view.setHtml(full_html)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        self.chat_view.page().runJavaScript(
            "window.scrollTo(0, document.body.scrollHeight);"
        )

    def append_system(self, content: str):
        chat = self.current_chat
        if not chat:
            return
        chat["html"] += renderer.render_system_msg(content)
        self._refresh_view()

    def append_user(self, content: str):
        chat = self.current_chat
        if not chat:
            return
        chat["html"] += renderer.render_user_msg(content)
        self._refresh_view()

    def append_assistant(self, reasoning: str, answer: str):
        chat = self.current_chat
        if not chat:
            return
        chat["html"] += renderer.render_assistant_msg(reasoning, answer)
        self._refresh_view()

    # ------------------------------------------------------------------ #
    #  Model switching / default model
    # ------------------------------------------------------------------ #

    def on_model_changed(self, text: str):
        chat = self.current_chat
        if not chat:
            return

        text = text.strip()
        if not text or text == chat["model"]:
            return

        old_model = chat.get("model", "").strip()
        chat["model"] = text

        if old_model:
            self.append_system(f"Switched model from: {old_model} to: {chat['model']}")
        else:
            self.append_system(f"Switched model to: {chat['model']}")

    def on_default_model_toggled(self, checked: bool):
        if not checked:
            return

        model = self.model_combo.currentText().strip()
        if not model:
            return

        self.default_model_name = model
        save_default_model(model)

    # ------------------------------------------------------------------ #
    #  LLM busy bookkeeping / title planner
    # ------------------------------------------------------------------ #

    def _finish_llm_cycle(self):
        """Called when all LLM-related work for this turn is done."""
        self.llm_busy = False
        self.send_button.setEnabled(True)
        self.send_button.setText("Send")

    def _start_title_planner_if_needed(self):
        """Optionally start TitleWorker. Otherwise, end cycle."""
        if not is_title_planner_enabled():
            self._finish_llm_cycle()
            return

        if not (0 <= self.current_chat_index < len(self.chats)):
            self._finish_llm_cycle()
            return

        chat = self.chats[self.current_chat_index]
        title = (chat.get("title") or "").strip()

        # Only auto-name generic "Chat N"
        if title and not title.lower().startswith("chat "):
            self._finish_llm_cycle()
            return

        history = chat.get("history") or []
        if not history:
            self._finish_llm_cycle()
            return

        model_name = chat.get("model") or self.default_model_name

        self.title_thread = QThread()
        self.title_worker = TitleWorker(history.copy(), model_name)
        self.title_worker.moveToThread(self.title_thread)

        self.title_thread.started.connect(self.title_worker.run)
        self.title_worker.finished.connect(self.on_title_ready)
        self.title_worker.error.connect(self.on_title_error)
        self.title_worker.finished.connect(self.title_thread.quit)
        self.title_worker.error.connect(self.title_thread.quit)
        self.title_worker.finished.connect(self.title_worker.deleteLater)
        self.title_thread.finished.connect(self.title_thread.deleteLater)

        self.title_thread.start()

    def on_title_ready(self, new_title: str):
        new_title = (new_title or "").strip()

        chat = self.current_chat
        if chat and new_title:
            chat["title"] = new_title
            row = self.current_chat_index
            item = self.chat_list.item(row)
            if item is not None:
                widget = self.chat_list.itemWidget(item)
                if isinstance(widget, ChatListItemWidget):
                    widget.set_title(new_title)
                else:
                    item.setText(new_title)

        self._finish_llm_cycle()

    def on_title_error(self, message: str):
        print(f"[title_planner] ERROR in TitleWorker: {message}")
        self._finish_llm_cycle()

    # ------------------------------------------------------------------ #
    #  Normal LLM send
    # ------------------------------------------------------------------ #

    def on_send_clicked(self):
        chat = self.current_chat
        if not chat or not self.send_button.isEnabled():
            return
        if getattr(self, "llm_busy", False):
            return

        text = self.input_box.toPlainText().strip()
        if not text:
            return

        if self.search_toggle.isChecked():
            self.on_search_web_clicked()
            return

        self.input_box.clear()
        self.append_user(text)
        chat["history"].append({"role": "user", "content": text})

        self.llm_busy = True
        self.send_button.setEnabled(False)
        self.send_button.setText("...")
        QApplication.processEvents()

        self.thread = QThread()
        self.worker = Worker(chat["history"].copy(), chat["model"])
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_reply_ready)
        self.worker.error.connect(self.on_reply_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def adjust_input_height(self):
        """Auto-resize input box height within min/max."""
        doc = self.input_box.document()
        doc.setTextWidth(self.input_box.viewport().width())

        layout = doc.documentLayout()
        if layout is None:
            return

        doc_size = layout.documentSize()
        height = doc_size.height()

        margins = self.input_box.contentsMargins()
        height += margins.top() + margins.bottom()
        height += self.input_box.frameWidth() * 2

        height = max(self.input_min_height, min(height, self.input_max_height))
        self.input_box.setFixedHeight(int(height))

    # ------------------------------------------------------------------ #
    #  LLM-based web search flow
    # ------------------------------------------------------------------ #

    def on_search_web_clicked(self):
        chat = self.current_chat
        if not chat or not self.send_button.isEnabled():
            return
        if getattr(self, "llm_busy", False):
            return

        raw_message = self.input_box.toPlainText().strip()
        if not raw_message:
            return

        # 1) Append user message
        self.input_box.clear()
        self.append_user(raw_message)
        chat["history"].append({"role": "user", "content": raw_message})

        # 2) Build planner_history for search planner
        planner_history = []
        for msg in chat["history"]:
            role = (msg.get("role") or "").lower()
            kind = msg.get("kind") or ""
            if role not in ("user", "assistant"):
                continue
            if role == "assistant" and kind == "web_results":
                continue
            planner_history.append(msg)

        # 3) Start WebSearchWorker
        self.llm_busy = True
        self.send_button.setEnabled(False)
        self.send_button.setText("...")
        QApplication.processEvents()

        self.search_thread = QThread()
        self.search_worker = WebSearchWorker(
            planner_history=planner_history,
            raw_message=raw_message,
            model_name=chat["model"],
        )
        self.search_worker.moveToThread(self.search_thread)

        self.search_thread.started.connect(self.search_worker.run)
        self.search_worker.finished.connect(self.on_web_search_finished)
        self.search_worker.error.connect(self.on_web_search_error)
        self.search_worker.finished.connect(self.search_thread.quit)
        self.search_worker.error.connect(self.search_thread.quit)
        self.search_worker.finished.connect(self.search_worker.deleteLater)
        self.search_thread.finished.connect(self.search_thread.deleteLater)

        self.search_thread.start()

    def on_web_search_finished(self, raw_message, search_query, md_block, context_blocks):
        chat = self.current_chat
        if not chat:
            self._finish_llm_cycle()
            return

        ws = load_web_settings()

        if ws.get("show_query", True):
            self.append_system(f"[web search query] {search_query}")

        frag = renderer.render_web_links_block(md_block or "_no results_")
        chat["html"] += frag
        self._refresh_view()

        if context_blocks:
            text_block = "\n\n\n".join(context_blocks)
        else:
            text_block = "No usable page content found."

        search_context = (
            "Web search results and page content.\n"
            f"Original user message: {raw_message}\n"
            f"Search query used: {search_query}\n\n"
            f"{text_block}"
        )

        chat["history"].append(
            {
                "role": "assistant",
                "content": search_context,
                "kind": "web_results",
            }
        )

        if ws.get("strict_web_only", True):
            chat["history"].append(
                {
                    "role": "system",
                    "content": get_web_followup_instruction(),
                }
            )

        self.thread = QThread()
        self.worker = Worker(chat["history"], chat["model"])
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_reply_ready)
        self.worker.error.connect(self.on_reply_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def on_web_search_error(self, message: str):
        self.append_system(f"Web search error: {message}")
        self._finish_llm_cycle()

    # ------------------------------------------------------------------ #
    #  Worker callbacks
    # ------------------------------------------------------------------ #

    def on_reply_ready(self, reasoning: str, content: str):
        chat = self.current_chat
        if chat:
            full = (content or reasoning or "").strip()
            if full:
                chat["history"].append({"role": "assistant", "content": full})
                self.append_assistant("", full)

        # Last step: title planner
        self._start_title_planner_if_needed()

    def on_reply_error(self, message: str):
        self.append_system(f"ERROR: {message}")
        self._finish_llm_cycle()

    # ------------------------------------------------------------------ #
    #  UI scaling
    # ------------------------------------------------------------------ #

    def apply_ui_scale(self):
        self.ui_scale = max(0.7, min(self.ui_scale, 1.8))

        app = QApplication.instance()
        if app is None:
            return

        base_font = app.font()
        f = QFont(base_font)
        f.setPointSizeF(self.base_font_size * self.ui_scale)

        app.setFont(f)

        for w in [
            getattr(self, "chat_list", None),
            getattr(self, "input_box", None),
            getattr(self, "send_button", None),
            getattr(self, "search_toggle", None),
            getattr(self, "model_combo", None),
            getattr(self, "default_checkbox", None),
            getattr(self, "new_chat_button", None),
            getattr(self, "label_chats", None),
            getattr(self, "label_model", None),
        ]:
            if w is not None:
                w.setFont(f)

        if getattr(self, "chat_list", None) is not None:
            for i in range(self.chat_list.count()):
                item = self.chat_list.item(i)
                widget = self.chat_list.itemWidget(item)
                if isinstance(widget, ChatListItemWidget):
                    widget.setFont(f)
                    widget.label.setFont(f)
                    widget.close_button.setFont(f)

        if hasattr(self, "chat_view"):
            self.chat_view.setZoomFactor(self.ui_scale)

    def change_ui_scale(self, factor: float):
        self.ui_scale *= factor
        self.apply_ui_scale()

    def reset_ui_scale(self):
        self.ui_scale = self.default_ui_scale
        self.apply_ui_scale()
