# ui/settings_window.py

from typing import Dict, Any

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import (
    QWidget,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QFormLayout,
    QPlainTextEdit,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QCheckBox,
    QSpinBox,
)

from core.backend import AVAILABLE_MODELS, DEFAULT_MODEL_NAME
from core.settings import (
    load_default_model,
    save_default_model,
    load_settings_dict,
    save_settings_dict,
    load_theme_presets,
    DEFAULT_THEME,
    DEFAULT_PROMPTS,
    load_prompts_dict,
    save_prompts_dict,
    load_web_settings,
    save_web_settings,
    DEFAULT_WEB_SEARCH_SETTINGS,
    get_title_planner_prompt,
    is_title_planner_enabled,
)

DEFAULT_THEME_NAME = "Default (Dark)"
CUSTOM_THEME_NAME = "Custom"


class SettingsOverlay(QWidget):
    """
    Semi-transparent overlay inside the main window with a larger, two-pane settings UI:
      - Left: category list (General, Theme, Web Search, Prompts)
      - Right: stacked pages for each category
    """

    def __init__(self, parent_window: QWidget):
        super().__init__(parent_window)
        self.parent_window = parent_window

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("SettingsOverlay")
        self.setStyleSheet(
            "#SettingsOverlay { background-color: rgba(0, 0, 0, 160); }"
        )

        # Prompt state cache
        self.prompt_key_order = ["system", "search_planner", "web_followup"]
        self.prompt_labels: Dict[str, str] = {
            "system": "System prompt",
            "search_planner": "Search planner prompt",
            "web_followup": "Web follow-up prompt",
        }
        self.prompts_cache: Dict[str, str] = {}
        self.current_prompt_key: str = "system"

        # Theme presets
        self.theme_presets: Dict[str, Dict[str, Any]] = load_theme_presets() or {}

        # Centered main panel
        self.settings_panel = QFrame(self)
        self.settings_panel.setObjectName("SettingsPanel")
        self.settings_panel.setFrameShape(QFrame.StyledPanel)
        self.settings_panel.setFrameShadow(QFrame.Raised)
        self.settings_panel.setMinimumSize(950, 580)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(40, 40, 40, 40)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.settings_panel, alignment=Qt.AlignCenter)

        panel_layout = QVBoxLayout(self.settings_panel)
        panel_layout.setContentsMargins(16, 16, 16, 16)
        panel_layout.setSpacing(12)

        # Header row
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        title_label = QLabel("Settings")
        title_label.setObjectName("SettingsTitle")

        close_button = QPushButton("✕")
        close_button.setObjectName("SettingsCloseButton")
        close_button.setFixedWidth(28)
        close_button.clicked.connect(self.hide)

        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        header_layout.addWidget(close_button)

        panel_layout.addLayout(header_layout)

        # Main content: categories + pages
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        # Category list
        self.category_list = QListWidget()
        self.category_list.setObjectName("SettingsCategoryList")
        self.category_list.setFixedWidth(200)
        self.category_list.setSpacing(4)

        for name in ["General", "Theme", "Web Search", "Prompts"]:
            item = QListWidgetItem(name)
            item.setSizeHint(QSize(180, 30))
            self.category_list.addItem(item)

        # Stacked pages
        self.stack = QStackedWidget()
        self.stack.setObjectName("SettingsStack")

        self.general_page = self._build_general_page()
        self.theme_page = self._build_theme_page()
        self.web_page = self._build_web_search_page()
        self.prompts_page = self._build_prompts_page()

        self.stack.addWidget(self.general_page)
        self.stack.addWidget(self.theme_page)
        self.stack.addWidget(self.web_page)
        self.stack.addWidget(self.prompts_page)

        self.category_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.category_list.setCurrentRow(0)

        content_layout.addWidget(self.category_list)
        content_layout.addWidget(self.stack, 1)

        panel_layout.addLayout(content_layout)

        # Footer: Save / Cancel
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 8, 0, 0)
        buttons_layout.addStretch(1)

        save_button = QPushButton("Save")
        save_button.setObjectName("SettingsSaveButton")
        save_button.clicked.connect(self.on_save_clicked)

        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("SettingsCancelButton")
        cancel_button.clicked.connect(self.hide)

        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)

        panel_layout.addLayout(buttons_layout)

        # Initial sync
        self.sync_from_settings()

    # ------------------------------------------------------------------ #
    # Page builders                                                      #
    # ------------------------------------------------------------------ #

    def _build_general_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("General")
        title.setObjectName("SettingsSectionTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)

        # Default model
        self.model_combo = QComboBox()
        self.model_combo.setObjectName("DefaultModelCombo")

        models = list(AVAILABLE_MODELS) or [DEFAULT_MODEL_NAME]
        for m in models:
            self.model_combo.addItem(m)

        form.addRow("Default model:", self.model_combo)

        # --- Auto title planner toggle ---
        self.auto_title_checkbox = QCheckBox("Automatically name chats from first message")
        self.auto_title_checkbox.setObjectName("AutoTitleCheckbox")
        form.addRow("Auto titles:", self.auto_title_checkbox)

        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _build_theme_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("Theme")
        title.setObjectName("SettingsSectionTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)

        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName("ThemePresetCombo")

        self.theme_combo.addItem(DEFAULT_THEME_NAME)
        self.theme_combo.addItem(CUSTOM_THEME_NAME)
        for name in sorted(self.theme_presets.keys()):
            self.theme_combo.addItem(name)

        form.addRow("Theme preset:", self.theme_combo)

        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _build_web_search_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("Web Search")
        title.setObjectName("SettingsSectionTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)

        # Enable integration
        self.web_enable_checkbox = QCheckBox("Enable web search integration")
        self.web_enable_checkbox.setObjectName("WebEnableCheckbox")
        form.addRow("Integration:", self.web_enable_checkbox)

        # Use LLM planner
        self.web_use_planner_checkbox = QCheckBox(
            "Use search planner (rewrite query with LLM)"
        )
        self.web_use_planner_checkbox.setObjectName("WebUsePlannerCheckbox")
        form.addRow("Planner:", self.web_use_planner_checkbox)

        # Max results
        self.web_max_results_spin = QSpinBox()
        self.web_max_results_spin.setObjectName("WebMaxResultsSpin")
        self.web_max_results_spin.setRange(1, 50)
        self.web_max_results_spin.setSingleStep(1)
        form.addRow("Max results:", self.web_max_results_spin)

        # Max pages
        self.web_max_pages_spin = QSpinBox()
        self.web_max_pages_spin.setObjectName("WebMaxPagesSpin")
        self.web_max_pages_spin.setRange(1, 10)
        self.web_max_pages_spin.setSingleStep(1)
        form.addRow("Max pages to fetch:", self.web_max_pages_spin)

        # Max chars per page
        self.web_max_chars_spin = QSpinBox()
        self.web_max_chars_spin.setObjectName("WebMaxCharsSpin")
        self.web_max_chars_spin.setRange(500, 50000)
        self.web_max_chars_spin.setSingleStep(500)
        form.addRow("Max chars per page:", self.web_max_chars_spin)

        # Language
        self.web_language_combo = QComboBox()
        self.web_language_combo.setObjectName("WebLanguageCombo")
        self.web_language_combo.addItem("Auto", userData="auto")
        self.web_language_combo.addItem("English (en)", userData="en")
        form.addRow("Language:", self.web_language_combo)

        # Safe search
        self.web_safesearch_combo = QComboBox()
        self.web_safesearch_combo.setObjectName("WebSafesearchCombo")
        self.web_safesearch_combo.addItem("Off (0)", userData=0)
        self.web_safesearch_combo.addItem("Moderate (1)", userData=1)
        self.web_safesearch_combo.addItem("Strict (2)", userData=2)
        form.addRow("Safe search:", self.web_safesearch_combo)

        # Show query in chat
        self.web_show_query_checkbox = QCheckBox(
            "Show effective search query in chat"
        )
        self.web_show_query_checkbox.setObjectName("WebShowQueryCheckbox")
        form.addRow("Display:", self.web_show_query_checkbox)

        # Strict web-only answers
        self.web_strict_only_checkbox = QCheckBox(
            "Force answers to use only web search results"
        )
        self.web_strict_only_checkbox.setObjectName("WebStrictOnlyCheckbox")
        form.addRow("Answer mode:", self.web_strict_only_checkbox)

        layout.addLayout(form)

        # --- Reset row ---
        reset_row = QHBoxLayout()
        reset_row.addStretch(1)

        self.web_reset_button = QPushButton("Reset to defaults")
        self.web_reset_button.setObjectName("WebResetButton")
        self.web_reset_button.clicked.connect(self.on_web_reset_clicked)

        reset_row.addWidget(self.web_reset_button)
        layout.addLayout(reset_row)

        layout.addStretch(1)
        return page

    def _build_prompts_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Prompts")
        title.setObjectName("SettingsSectionTitle")
        layout.addWidget(title)

        selector_row = QHBoxLayout()
        selector_row.setSpacing(8)

        selector_label = QLabel("Prompt:")
        self.prompt_type_combo = QComboBox()
        self.prompt_type_combo.setObjectName("PromptTypeCombo")

        for key in self.prompt_key_order:
            self.prompt_type_combo.addItem(self.prompt_labels[key], userData=key)

        selector_row.addWidget(selector_label)
        selector_row.addWidget(self.prompt_type_combo, 1)
        selector_row.addStretch(1)

        layout.addLayout(selector_row)

        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setObjectName("PromptEdit")
        self.prompt_edit.setMinimumHeight(260)
        layout.addWidget(self.prompt_edit, 1)

        reset_row = QHBoxLayout()
        reset_row.addStretch(1)

        self.prompt_reset_button = QPushButton("Reset to default")
        self.prompt_reset_button.setObjectName("PromptResetButton")
        self.prompt_reset_button.clicked.connect(self.on_prompt_reset_clicked)

        reset_row.addWidget(self.prompt_reset_button)
        layout.addLayout(reset_row)

        self.prompt_type_combo.currentIndexChanged.connect(
            self.on_prompt_type_changed
        )

        return page

    # ------------------------------------------------------------------ #
    # Data sync                                                          #
    # ------------------------------------------------------------------ #

    def sync_from_settings(self) -> None:
        """Load current settings and prompts into the widgets."""
        data = load_settings_dict()

        # Default model
        explicit_default = (data.get("default_model") or "").strip()
        if explicit_default:
            model_name = explicit_default
        else:
            model_name = load_default_model() or DEFAULT_MODEL_NAME

        idx = self.model_combo.findText(model_name)
        if idx < 0:
            idx = 0
        self.model_combo.setCurrentIndex(idx)
        
        # Auto title planner flag
        self.auto_title_checkbox.setChecked(is_title_planner_enabled())

        # Theme
        overrides = data.get("theme") or {}
        if not overrides:
            selected_name = DEFAULT_THEME_NAME
        else:
            selected_name = CUSTOM_THEME_NAME
            for name, preset in self.theme_presets.items():
                if isinstance(preset, dict) and preset == overrides:
                    selected_name = name
                    break

        idx = self.theme_combo.findText(selected_name)
        if idx < 0:
            idx = 0
        self.theme_combo.setCurrentIndex(idx)

        # Web search
        ws = load_web_settings()
        self.web_enable_checkbox.setChecked(bool(ws.get("enabled", True)))
        self.web_use_planner_checkbox.setChecked(bool(ws.get("use_planner", True)))
        self.web_max_results_spin.setValue(int(ws.get("max_results", 10)))
        self.web_max_pages_spin.setValue(int(ws.get("max_pages", 5)))
        self.web_max_chars_spin.setValue(int(ws.get("max_chars_per_page", 6000)))

        lang = ws.get("language", "en") or "en"
        lang_idx = 0
        for i in range(self.web_language_combo.count()):
            if self.web_language_combo.itemData(i) == lang:
                lang_idx = i
                break
        self.web_language_combo.setCurrentIndex(lang_idx)

        ss_val = int(ws.get("safesearch", 1))
        ss_idx = 0
        for i in range(self.web_safesearch_combo.count()):
            if int(self.web_safesearch_combo.itemData(i)) == ss_val:
                ss_idx = i
                break
        self.web_safesearch_combo.setCurrentIndex(ss_idx)

        self.web_show_query_checkbox.setChecked(bool(ws.get("show_query", True)))
        self.web_strict_only_checkbox.setChecked(bool(ws.get("strict_web_only", True)))

        # Prompts
        stored_prompts = load_prompts_dict()
        self.prompts_cache = {}
        for key in self.prompt_key_order:
            self.prompts_cache[key] = stored_prompts.get(
                key, DEFAULT_PROMPTS[key]
            )

        self.current_prompt_key = "system"
        self.prompt_type_combo.blockSignals(True)
        self.prompt_type_combo.setCurrentIndex(
            self.prompt_key_order.index("system")
        )
        self.prompt_type_combo.blockSignals(False)
        self._load_prompt_to_editor("system")

    # ------------------------------------------------------------------ #
    # Prompt helpers                                                     #
    # ------------------------------------------------------------------ #

    def _load_prompt_to_editor(self, key: str) -> None:
        self.prompt_edit.setPlainText(self.prompts_cache.get(key, ""))

    def _save_current_prompt_from_editor(self) -> None:
        if self.current_prompt_key:
            self.prompts_cache[self.current_prompt_key] = (
                self.prompt_edit.toPlainText()
            )

    def on_prompt_type_changed(self, index: int) -> None:
        if index < 0 or index >= len(self.prompt_key_order):
            return
        self._save_current_prompt_from_editor()
        new_key = self.prompt_key_order[index]
        self.current_prompt_key = new_key
        self._load_prompt_to_editor(new_key)

    def on_prompt_reset_clicked(self) -> None:
        key = self.current_prompt_key or "system"
        default_text = DEFAULT_PROMPTS.get(key, "")
        self.prompt_edit.setPlainText(default_text)
        self.prompts_cache[key] = default_text

    # ------------------------------------------------------------------ #
    # Save & Rest                                                        #
    # ------------------------------------------------------------------ #

    def on_save_clicked(self) -> None:
        """Persist settings + prompts + web search and notify parent window."""
        self._save_current_prompt_from_editor()

        # settings.json: default model + theme + auto_title_planner
        data = load_settings_dict()

        selected_model = self.model_combo.currentText().strip()
        if selected_model:
            data["default_model"] = selected_model
            save_default_model(selected_model)

        theme_label = self.theme_combo.currentText()
        if theme_label == DEFAULT_THEME_NAME:
            data.pop("theme", None)
        elif theme_label == CUSTOM_THEME_NAME:
            # keep whatever is already in data["theme"], or let user edit via presets later
            pass
        else:
            preset = self.theme_presets.get(theme_label)
            if isinstance(preset, dict):
                data["theme"] = preset
            else:
                data["theme"] = DEFAULT_THEME.copy()

        # --- Auto title planner flag (MUST be set before saving) ---
        data["auto_title_planner"] = self.auto_title_checkbox.isChecked()

        # Now actually write settings.json with default_model + theme + auto_title_planner
        save_settings_dict(data)

        # web_search (settings.json -> web_search key)
        ws = load_web_settings()
        ws["enabled"] = self.web_enable_checkbox.isChecked()
        ws["use_planner"] = self.web_use_planner_checkbox.isChecked()
        ws["max_results"] = self.web_max_results_spin.value()
        ws["max_pages"] = self.web_max_pages_spin.value()
        ws["max_chars_per_page"] = self.web_max_chars_spin.value()

        lang = self.web_language_combo.currentData() or "en"
        ws["language"] = lang

        ss_val = self.web_safesearch_combo.currentData()
        try:
            ws["safesearch"] = int(ss_val)
        except Exception:
            ws["safesearch"] = 1

        ws["show_query"] = self.web_show_query_checkbox.isChecked()
        ws["strict_web_only"] = self.web_strict_only_checkbox.isChecked()

        save_web_settings(ws)

        # prompts.json
        prompt_overrides = load_prompts_dict()
        for key in self.prompt_key_order:
            text = (self.prompts_cache.get(key) or "").strip()
            default_val = DEFAULT_PROMPTS[key]
            if not text or text == default_val:
                prompt_overrides.pop(key, None)
            else:
                prompt_overrides[key] = text
        save_prompts_dict(prompt_overrides)

        if hasattr(self.parent_window, "on_settings_updated"):
            self.parent_window.on_settings_updated()

        self.hide()

    def on_web_reset_clicked(self) -> None:
        """Reset Web Search page widgets to DEFAULT_WEB_SEARCH_SETTINGS."""
        ws = DEFAULT_WEB_SEARCH_SETTINGS

        self.web_enable_checkbox.setChecked(bool(ws.get("enabled", True)))
        self.web_use_planner_checkbox.setChecked(bool(ws.get("use_planner", True)))
        self.web_max_results_spin.setValue(int(ws.get("max_results", 10)))
        self.web_max_pages_spin.setValue(int(ws.get("max_pages", 5)))
        self.web_max_chars_spin.setValue(int(ws.get("max_chars_per_page", 6000)))

        lang = ws.get("language", "en") or "en"
        lang_idx = 0
        for i in range(self.web_language_combo.count()):
            if self.web_language_combo.itemData(i) == lang:
                lang_idx = i
                break
        self.web_language_combo.setCurrentIndex(lang_idx)

        ss_val = int(ws.get("safesearch", 1))
        ss_idx = 0
        for i in range(self.web_safesearch_combo.count()):
            if int(self.web_safesearch_combo.itemData(i)) == ss_val:
                ss_idx = i
                break
        self.web_safesearch_combo.setCurrentIndex(ss_idx)

        self.web_show_query_checkbox.setChecked(bool(ws.get("show_query", True)))
        self.web_strict_only_checkbox.setChecked(bool(ws.get("strict_web_only", True)))

    # ------------------------------------------------------------------ #
    # Overlay geometry                                                   #
    # ------------------------------------------------------------------ #

    def resize_to_parent(self) -> None:
        if self.parent():
            self.setGeometry(self.parent().rect())

    def showEvent(self, event):
        self.resize_to_parent()
        super().showEvent(event)
