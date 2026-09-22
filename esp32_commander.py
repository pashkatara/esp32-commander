import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import threading
import serial
import serial.tools.list_ports
import esptool
from esptool.cmds import _get_flash_info, connect_esp, run_stub
import io
import contextlib
import time
import os
import re

APP_VERSION = "1.2.0"
APP_AUTHOR  = "pashka_tara"
APP_CONTACT = "onepashka25@gmail.com"
APP_YEAR    = "2026"
APP_DESC    = "Инструмент для полного управления контроллерами ESP32: безопасное стирание flash-памяти, считывание резервных дампов (.bin), загрузка прошивок по адресам памяти и встроенный высокоскоростной монитор последовательного порта."

VENDOR_NAMES = {
    0x20: "XMC (0x20)",
    0xc8: "GigaDevice (0xc8)",
    0xef: "Winbond (0xef)",
    0x1c: "EON (0x1c)",
    0x68: "Boya Micro (0x68)",
    0x85: "Puya (0x85)",
    0x0b: "XTX (0x0b)",
    0x5e: "ZB / Zetta (0x5e)",
    0xa1: "Fudan Micro (0xa1)",
    0x9d: "ISSI (0x9d)",
    0xc2: "Macronix (0xc2)",
    0x37: "AMIC (0x37)",
    0x7f: "Microchip (0x7f)",
    0x01: "Spansion (0x01)",
    0x1f: "Adesto (0x1f)",
}

def run_esptool(args) -> str:
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            esptool.main(args)
    except SystemExit:
        pass
    return buf.getvalue()


class CommanderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ESP32 Commander")
        self.geometry("680x660")
        self.resizable(False, False)
        self._banner        = None
        self._monitor_run   = False
        self._monitor_ser   = None
        self._theme         = "light"
        self._about_shown   = False
        self._build_ui()
        self._refresh_ports()

    # ══════════════════════════════════════════════════════════════════
    # UI BUILD
    # ══════════════════════════════════════════════════════════════════

    def _build_ui(self):
        self._build_header()
        self._build_portbar()
        self._build_statusbar()

        # 5 Main Tabs (no separate "About" tab in the tab bar)
        self.tabs = ctk.CTkTabview(self, corner_radius=12, width=650)
        self.tabs.pack(fill="both", expand=True, padx=14, pady=(4, 6))

        tab_names = [
            "  Очистка flash  ",
            "  Инфо о плате  ",
            "  Резервная копия  ",
            "  Прошивка  ",
            "  Монитор порта  ",
        ]
        for name in tab_names:
            self.tabs.add(name)

        self._build_erase_tab()
        self._build_info_tab()
        self._build_backup_tab()
        self._build_flash_tab()
        self._build_monitor_tab()

        # Inline About Panel (replaces tabs when active)
        self.about_panel = ctk.CTkFrame(self, fg_color="transparent")
        self._build_about_panel()

    def _build_statusbar(self):
        self.statusbar = ctk.CTkFrame(self, fg_color=("#e4eaf5", "#0d1527"), corner_radius=0, height=28)
        self.statusbar.pack(side="bottom", fill="x")
        self.statusbar.pack_propagate(False)

        ctk.CTkFrame(self.statusbar, fg_color=("#cbd5e1", "#1e2d4a"), height=1, corner_radius=0).pack(fill="x")

        self.status_msg_var = tk.StringVar(value="Готов к работе")
        self.status_icon_lbl = ctk.CTkLabel(
            self.statusbar, text="●",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=("#22c55e", "#00e5ff"),
        )
        self.status_icon_lbl.pack(side="left", padx=(14, 6))

        self.status_msg_lbl = ctk.CTkLabel(
            self.statusbar, textvariable=self.status_msg_var,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#475569", "#94a3b8"),
            anchor="w",
        )
        self.status_msg_lbl.pack(side="left", fill="x", expand=True, padx=(0, 14))

    # ── Header ────────────────────────────────────────────────────────

    def _build_header(self):
        self.hdr = ctk.CTkFrame(self, fg_color="#060d1a", corner_radius=0, height=88)
        self.hdr.pack(fill="x")
        self.hdr.pack_propagate(False)

        ctk.CTkFrame(self.hdr, fg_color="#00e5ff", height=3, corner_radius=0).pack(fill="x")

        center = ctk.CTkFrame(self.hdr, fg_color="transparent")
        center.place(relx=0.5, rely=0.54, anchor="center")

        title_row = ctk.CTkFrame(center, fg_color="transparent")
        title_row.pack()

        ctk.CTkLabel(
            title_row, text="ESP32",
            font=ctk.CTkFont(family="OCR-A BT", size=28, weight="bold"),
            text_color="#00e5ff",
        ).pack(side="left")

        ctk.CTkLabel(
            title_row, text="  COMMANDER",
            font=ctk.CTkFont(family="OCR-A BT", size=28, weight="bold"),
            text_color="white",
        ).pack(side="left")

        ctk.CTkLabel(
            center,
            text="[ FLASH TOOL  ·  FIRMWARE MANAGER  ·  SERIAL MONITOR ]",
            font=ctk.CTkFont(family="Bahnschrift", size=10),
            text_color="#0099bb",
        ).pack(pady=(2, 0))

        ctk.CTkFrame(self.hdr, fg_color="#00e5ff", height=1, corner_radius=0).pack(fill="x", side="bottom")

    # ── Port bar ──────────────────────────────────────────────────────

    def _build_portbar(self):
        self.portbar = ctk.CTkFrame(self, fg_color=("#eef2ff", "#101827"), corner_radius=0)
        self.portbar.pack(fill="x")
        inner = ctk.CTkFrame(self.portbar, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(inner, text="COM-порт:",
                     font=ctk.CTkFont(family="Segoe UI", size=13)).pack(side="left", padx=(0, 6))

        self.port_var = tk.StringVar()
        self.port_combo = ctk.CTkComboBox(
            inner, variable=self.port_var, values=[], state="readonly", width=120,
            font=ctk.CTkFont(family="Segoe UI", size=13))
        self.port_combo.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(inner, text="Скорость:",
                     font=ctk.CTkFont(family="Segoe UI", size=13)).pack(side="left", padx=(0, 6))

        self.baud_var = tk.StringVar(value="115200")
        self.baud_combo = ctk.CTkComboBox(
            inner, variable=self.baud_var,
            values=["9600","19200","38400","57600","115200","230400","460800","921600"],
            state="readonly", width=100,
            font=ctk.CTkFont(family="Segoe UI", size=13))
        self.baud_combo.pack(side="left", padx=(0, 10))

        self.refresh_btn = ctk.CTkButton(
            inner, text="↺  Обновить", width=105, height=30, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=("#dde8ff", "#1a2234"), text_color=("#1a73e8", "#00e5ff"),
            hover_color=("#c5d8ff", "#2a344a"),
            command=self._refresh_ports)
        self.refresh_btn.pack(side="left")

        # Right buttons: Info & Theme
        self.about_btn = ctk.CTkButton(
            inner, text="ⓘ", width=34, height=30, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=15),
            fg_color=("#dde8ff", "#1a2234"), text_color=("#555555", "#aaaaaa"),
            hover_color=("#c5d8ff", "#2a344a"),
            command=self._toggle_about_panel)
        self.about_btn.pack(side="right", padx=(4, 0))

        self.theme_btn = ctk.CTkButton(
            inner, text="☀", width=34, height=30, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=15),
            fg_color=("#dde8ff", "#1a2234"), text_color=("#e6a817", "#00e5ff"),
            hover_color=("#c5d8ff", "#2a344a"),
            command=self._toggle_theme)
        self.theme_btn.pack(side="right", padx=(4, 0))

    # ── Tab helpers ───────────────────────────────────────────────────

    def _make_log(self, parent):
        box = ctk.CTkTextbox(
            parent,
            font=ctk.CTkFont(family="Consolas", size=10),
            state="disabled", corner_radius=8,
            border_width=1,
            border_color=("#e0e0e0", "#1e2d4a"),
            fg_color=("#f9f9f9", "#080e1a"),
            text_color=("#222222", "#00d4ff"),
        )
        box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        return box

    def _append_log(self, widget, text: str):
        widget.configure(state="normal")
        widget.insert("end", text + "\n")
        widget.see("end")
        widget.configure(state="disabled")

    def _section_label(self, parent, text):
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="gray", justify="center",
        ).pack(pady=(8, 8))

    # ── Tab: Erase ────────────────────────────────────────────────────

    def _build_erase_tab(self):
        t = self.tabs.tab("  Очистка flash  ")
        self._section_label(
            t, "Полное стирание flash-памяти ESP32.\n"
               "Все данные и прошивка будут удалены безвозвратно.")

        self.erase_btn = ctk.CTkButton(
            t, text="🗑   Стереть устройство",
            height=44, corner_radius=12,
            font=ctk.CTkFont(family="Bahnschrift", size=14),
            fg_color="#c0392b", hover_color="#a93226",
            command=self._ask_erase_confirm)
        self.erase_btn.pack(fill="x", padx=8)

        self.confirm_frame = ctk.CTkFrame(
            t, corner_radius=10, fg_color=("#fff8e1", "#2b2314"),
            border_width=1, border_color="#f0c040")

        ctk.CTkLabel(
            self.confirm_frame,
            text="⚠  Вы уверены? Все данные исчезнут навсегда!",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=("#7a5c00", "#ffcc00"), fg_color="transparent",
        ).pack(side="left", padx=(12, 8), pady=10)

        ctk.CTkButton(
            self.confirm_frame, text="Да, стереть",
            width=110, height=30, corner_radius=8,
            fg_color="#c0392b", hover_color="#a93226",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._do_erase,
        ).pack(side="left", padx=(0, 6), pady=10)

        ctk.CTkButton(
            self.confirm_frame, text="Отмена",
            width=80, height=30, corner_radius=8,
            fg_color="transparent", text_color=("#555", "#aaa"),
            hover_color=("#eee", "#333"), border_width=1, border_color="#ccc",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._cancel_erase_confirm,
        ).pack(side="left", pady=10)

        self.erase_status = tk.StringVar(value="")
        ctk.CTkLabel(t, textvariable=self.erase_status,
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color="gray", anchor="w",
                     ).pack(fill="x", padx=8, pady=(6, 2))

        self.erase_log = self._make_log(t)

    # ── Tab: Info ─────────────────────────────────────────────────────

    def _build_info_tab(self):
        t = self.tabs.tab("  Инфо о плате  ")

        top_row = ctk.CTkFrame(t, fg_color="transparent")
        top_row.pack(fill="x", padx=8, pady=(10, 6))

        self.info_btn = ctk.CTkButton(
            top_row, text="📋  Считать информацию с платы",
            height=40, corner_radius=10,
            font=ctk.CTkFont(family="Bahnschrift", size=13),
            command=self._get_info)
        self.info_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.info_status_var = tk.StringVar(value="Подключите ESP32 к выбранному COM-порту и нажмите кнопку выше.")
        self.info_status_lbl = ctk.CTkLabel(
            t, textvariable=self.info_status_var,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="gray", anchor="w")
        self.info_status_lbl.pack(fill="x", padx=12, pady=(0, 8))

        # 6 Cards Grid (2 cols x 3 rows) - perfectly fits without scrollbar!
        self.cards_grid = ctk.CTkFrame(t, fg_color="transparent")
        self.cards_grid.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.cards_grid.columnconfigure(0, weight=1)
        self.cards_grid.columnconfigure(1, weight=1)
        self.cards_grid.rowconfigure(0, weight=1)
        self.cards_grid.rowconfigure(1, weight=1)
        self.cards_grid.rowconfigure(2, weight=1)

        self.tile_vars = {}
        tile_configs = [
            ("chip",         "🔲", "Модель процессора",  0, 0),
            ("mac",          "📡", "MAC-адрес платы",   0, 1),
            ("flash_size",   "💾", "Объём Flash-памяти", 1, 0),
            ("crystal",      "⚡", "Частота кварца",    1, 1),
            ("manufacturer", "🏭", "Производитель Flash", 2, 0),
            ("features",     "⚙",  "Функции и модули",   2, 1),
        ]

        for key, icon, title, row, col in tile_configs:
            tile = ctk.CTkFrame(
                self.cards_grid, corner_radius=10,
                border_width=1, border_color=("#dbe3f0", "#1e2d4a"),
                fg_color=("white", "#131d31")
            )
            tile.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

            hdr = ctk.CTkFrame(tile, fg_color="transparent")
            hdr.pack(fill="x", padx=12, pady=(8, 2))

            ctk.CTkLabel(hdr, text=icon, font=ctk.CTkFont(family="Segoe UI", size=14)).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(hdr, text=title.upper(), font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                         text_color=("#718096", "#00d4ff")).pack(side="left")

            val_var = tk.StringVar(value="—")
            self.tile_vars[key] = val_var

            ctk.CTkLabel(
                tile, textvariable=val_var,
                font=ctk.CTkFont(family="Bahnschrift", size=13),
                text_color=("#1a202c", "#e2e8f0"),
                anchor="w", wraplength=280, justify="left"
            ).pack(fill="x", padx=12, pady=(0, 8))

    # ── Tab: Backup ───────────────────────────────────────────────────

    def _build_backup_tab(self):
        t = self.tabs.tab("  Резервная копия  ")
        self._section_label(
            t, "Считывает содержимое flash-памяти ESP32\n"
               "и сохраняет в .bin файл на вашем компьютере.")

        file_row = ctk.CTkFrame(t, fg_color="transparent")
        file_row.pack(fill="x", padx=8, pady=(0, 6))
        self.backup_path_var = tk.StringVar(value="Файл не выбран")
        ctk.CTkEntry(file_row, textvariable=self.backup_path_var,
                     font=ctk.CTkFont(family="Segoe UI", size=12),
                     state="readonly", width=390).pack(side="left", padx=(0, 8))
        ctk.CTkButton(file_row, text="📁  Выбрать путь",
                      width=140, height=32, corner_radius=8,
                      font=ctk.CTkFont(family="Segoe UI", size=12),
                      command=self._choose_backup_path).pack(side="left")

        opt_row = ctk.CTkFrame(t, fg_color="transparent")
        opt_row.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkLabel(opt_row, text="Размер flash:",
                     font=ctk.CTkFont(family="Segoe UI", size=12)).pack(side="left", padx=(0, 8))
        self.backup_size_var = tk.StringVar(value="4MB")
        ctk.CTkComboBox(opt_row, variable=self.backup_size_var,
                        values=["1MB","2MB","4MB","8MB","16MB"],
                        state="readonly", width=100,
                        font=ctk.CTkFont(family="Segoe UI", size=12)).pack(side="left")

        self.backup_btn = ctk.CTkButton(
            t, text="💾  Создать резервную копию",
            height=42, corner_radius=12,
            font=ctk.CTkFont(family="Bahnschrift", size=14),
            fg_color="#1565c0", hover_color="#0d47a1",
            command=self._do_backup)
        self.backup_btn.pack(fill="x", padx=8, pady=(0, 6))

        self.backup_progress = ctk.CTkProgressBar(t, corner_radius=6, height=8)
        self.backup_progress.set(0)
        self.backup_progress.pack(fill="x", padx=8, pady=(0, 4))

        self.backup_status = tk.StringVar(value="")
        ctk.CTkLabel(t, textvariable=self.backup_status,
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color="gray", anchor="w",
                     ).pack(fill="x", padx=8, pady=(0, 4))
        self.backup_log = self._make_log(t)

    # ── Tab: Flash ────────────────────────────────────────────────────

    def _build_flash_tab(self):
        t = self.tabs.tab("  Прошивка  ")
        self._section_label(
            t, "Загружает .bin файл прошивки на ESP32.\n"
               "Выберите файл и укажите адрес записи во flash.")

        file_row = ctk.CTkFrame(t, fg_color="transparent")
        file_row.pack(fill="x", padx=8, pady=(0, 6))
        self.flash_path_var = tk.StringVar(value="Файл не выбран")
        ctk.CTkEntry(file_row, textvariable=self.flash_path_var,
                     font=ctk.CTkFont(family="Segoe UI", size=12),
                     state="readonly", width=390).pack(side="left", padx=(0, 8))
        ctk.CTkButton(file_row, text="📁  Выбрать .bin файл",
                      width=150, height=32, corner_radius=8,
                      font=ctk.CTkFont(family="Segoe UI", size=12),
                      command=self._choose_flash_file).pack(side="left")

        opt_row = ctk.CTkFrame(t, fg_color="transparent")
        opt_row.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkLabel(opt_row, text="Адрес записи:",
                     font=ctk.CTkFont(family="Segoe UI", size=12)).pack(side="left", padx=(0, 8))
        self.flash_addr_var = tk.StringVar(value="0x1000")
        ctk.CTkComboBox(opt_row, variable=self.flash_addr_var,
                        values=["0x0000","0x1000","0x8000","0xe000","0x10000"],
                        width=120,
                        font=ctk.CTkFont(family="Segoe UI", size=12)).pack(side="left")

        self.flash_btn = ctk.CTkButton(
            t, text="⚡  Прошить устройство",
            height=42, corner_radius=12,
            font=ctk.CTkFont(family="Bahnschrift", size=14),
            fg_color="#e67e00", hover_color="#c06000",
            command=self._do_flash)
        self.flash_btn.pack(fill="x", padx=8, pady=(0, 6))

        self.flash_progress = ctk.CTkProgressBar(t, corner_radius=6, height=8)
        self.flash_progress.set(0)
        self.flash_progress.pack(fill="x", padx=8, pady=(0, 4))

        self.flash_status = tk.StringVar(value="")
        ctk.CTkLabel(t, textvariable=self.flash_status,
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color="gray", anchor="w",
                     ).pack(fill="x", padx=8, pady=(0, 4))
        self.flash_log = self._make_log(t)

    # ── Tab: Monitor ──────────────────────────────────────────────────

    def _build_monitor_tab(self):
        t = self.tabs.tab("  Монитор порта  ")

        ctrl = ctk.CTkFrame(t, fg_color="transparent")
        ctrl.pack(fill="x", padx=8, pady=(8, 6))

        self.mon_start_btn = ctk.CTkButton(
            ctrl, text="▶  Подключить",
            width=120, height=32, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#2e7d32", hover_color="#1b5e20",
            command=self._monitor_start)
        self.mon_start_btn.pack(side="left", padx=(0, 6))

        self.mon_stop_btn = ctk.CTkButton(
            ctrl, text="⏹  Отключить",
            width=110, height=32, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#555", hover_color="#333", state="disabled",
            command=self._monitor_stop)
        self.mon_stop_btn.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            ctrl, text="🗑  Очистить",
            width=95, height=32, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="transparent", text_color=("#555", "#aaa"),
            hover_color=("#eee", "#333"), border_width=1, border_color="#ccc",
            command=self._monitor_clear).pack(side="left", padx=(0, 10))

        self.mon_status = tk.StringVar(value="Статус: Не подключено")
        self.mon_status_label = ctk.CTkLabel(
            ctrl, textvariable=self.mon_status,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="gray", anchor="w")
        self.mon_status_label.pack(side="left", fill="x", expand=True)

        self.monitor_log = ctk.CTkTextbox(
            t, font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled", corner_radius=8,
            border_width=1, border_color=("#1a2a4a", "#00d4ff"),
            fg_color=("#060d1a", "#040812"), text_color="#00e5ff")
        self.monitor_log.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        send_row = ctk.CTkFrame(t, fg_color="transparent")
        send_row.pack(fill="x", padx=8, pady=(0, 8))

        self.send_var = tk.StringVar()
        send_entry = ctk.CTkEntry(
            send_row, textvariable=self.send_var,
            font=ctk.CTkFont(family="Consolas", size=12),
            placeholder_text="Введите команду и нажмите Enter для отправки…")
        send_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        send_entry.bind("<Return>", lambda e: self._monitor_send())

        ctk.CTkButton(
            send_row, text="Отправить",
            width=110, height=32, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._monitor_send).pack(side="left")

    # ── Inline About Panel (Inside Same Window) ────────────────────────

    def _build_about_panel(self):
        # Top bar with Back Button
        top_bar = ctk.CTkFrame(self.about_panel, fg_color="transparent")
        top_bar.pack(fill="x", padx=8, pady=(4, 6))

        ctk.CTkButton(
            top_bar, text="←  Вернуться к панели управления",
            height=32, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=("#dde8ff", "#1a2234"), text_color=("#1a73e8", "#00e5ff"),
            hover_color=("#c5d8ff", "#2a344a"),
            command=self._toggle_about_panel
        ).pack(side="left")

        # Banner card
        banner = ctk.CTkFrame(
            self.about_panel, corner_radius=10,
            border_width=1, border_color="#00e5ff",
            fg_color=("#0a1224", "#060d1a")
        )
        banner.pack(fill="x", padx=8, pady=(0, 8))

        b_in = ctk.CTkFrame(banner, fg_color="transparent")
        b_in.pack(fill="x", padx=16, pady=10)

        title_line = ctk.CTkFrame(b_in, fg_color="transparent")
        title_line.pack(anchor="w")

        ctk.CTkLabel(title_line, text="ESP32", font=ctk.CTkFont(family="OCR-A BT", size=22, weight="bold"),
                     text_color="#00e5ff").pack(side="left")
        ctk.CTkLabel(title_line, text="  COMMANDER", font=ctk.CTkFont(family="OCR-A BT", size=22, weight="bold"),
                     text_color="white").pack(side="left")
        ctk.CTkLabel(title_line, text=f"   версия {APP_VERSION} ({APP_YEAR})",
                     font=ctk.CTkFont(family="Bahnschrift", size=12),
                     text_color="#0099bb").pack(side="left")

        # Full unwrapped clear description
        ctk.CTkLabel(
            b_in,
            text=APP_DESC,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#c8d6e5",
            wraplength=610,
            justify="left"
        ).pack(anchor="w", pady=(6, 0))

        # 2x2 Info Grid
        grid = ctk.CTkFrame(self.about_panel, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=8, pady=(0, 6))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)

        about_cards = [
            ("👤", "Разработка и автор", [
                ("Автор:", APP_AUTHOR),
                ("Контакты:", APP_CONTACT),
                ("Год релиза:", f"{APP_YEAR} г. (v{APP_VERSION})"),
            ], 0, 0),
            ("⚡", "Ключевые функции", [
                ("•", "Быстрая очистка flash-памяти в 1 клик"),
                ("•", "Резервное копирование и сохранение .bin"),
                ("•", "Загрузка прошивок по адресам flash"),
                ("•", "Интерактивный serial-терминал порта"),
            ], 0, 1),
            ("🔌", "Поддерживаемые контроллеры", [
                ("•", "ESP32 (Classic, WROOM, WROVER)"),
                ("•", "ESP32-S2 / ESP32-S3 (USB, AI)"),
                ("•", "ESP32-C3 / ESP32-C6 (RISC-V)"),
                ("•", "ESP8266 (ESP-01, ESP-12E/12F)"),
            ], 1, 0),
            ("🛠", "Технологический стек", [
                ("Движок:", "Python 3.12 · esptool 5.4 API"),
                ("Интерфейс:", "CustomTkinter (Win11 Modern UI)"),
                ("Связь:", "PySerial (CP210x, CH340, FTDI)"),
                ("Сборка:", "Standalone Executable (x64)"),
            ], 1, 1),
        ]

        for icon, title, items, row, col in about_cards:
            card = ctk.CTkFrame(
                grid, corner_radius=10,
                border_width=1, border_color=("#dbe3f0", "#1e2d4a"),
                fg_color=("white", "#131d31")
            )
            card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")

            hdr = ctk.CTkFrame(card, fg_color="transparent")
            hdr.pack(fill="x", padx=10, pady=(6, 2))
            ctk.CTkLabel(hdr, text=icon, font=ctk.CTkFont(family="Segoe UI", size=13)).pack(side="left", padx=(0, 5))
            ctk.CTkLabel(hdr, text=title.upper(), font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                         text_color=("#718096", "#00d4ff")).pack(side="left")

            body = ctk.CTkFrame(card, fg_color="transparent")
            body.pack(fill="both", expand=True, padx=10, pady=(0, 6))

            for k, v in items:
                r = ctk.CTkFrame(body, fg_color="transparent")
                r.pack(fill="x", pady=1)
                ctk.CTkLabel(r, text=k, font=ctk.CTkFont(family="Segoe UI", size=10),
                             text_color="gray", width=70 if ":" in k else 15, anchor="w").pack(side="left")
                ctk.CTkLabel(r, text=v, font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                             text_color=("#1a202c", "#e2e8f0"), anchor="w", wraplength=210, justify="left").pack(side="left")

    # ══════════════════════════════════════════════════════════════════
    # THEME & INLINE ABOUT TOGGLE
    # ══════════════════════════════════════════════════════════════════

    def _toggle_theme(self):
        if self._theme == "light":
            self._theme = "dark"
            ctk.set_appearance_mode("dark")
            self.theme_btn.configure(text="🌙", text_color="#00e5ff")
        else:
            self._theme = "light"
            ctk.set_appearance_mode("light")
            self.theme_btn.configure(text="☀", text_color="#e6a817")

    def _toggle_about_panel(self):
        if self._about_shown:
            self._about_shown = False
            self.about_panel.pack_forget()
            self.tabs.pack(fill="both", expand=True, padx=14, pady=(4, 6))
            self.about_btn.configure(fg_color=("#dde8ff", "#1a2234"))
        else:
            self._about_shown = True
            self.tabs.pack_forget()
            self.about_panel.pack(fill="both", expand=True, padx=14, pady=(4, 6))
            self.about_btn.configure(fg_color=("#c5d8ff", "#2a344a"))

    # ══════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo.configure(values=ports)
        if ports:
            self.port_combo.set(ports[0])
        else:
            self.port_combo.set("")

    def _get_port(self): return self.port_var.get()
    def _get_baud(self):
        try: return int(self.baud_var.get())
        except: return 115200

    def _set_busy(self, busy: bool):
        s = "disabled" if busy else "normal"
        for b in [self.erase_btn, self.info_btn, self.backup_btn,
                  self.flash_btn, self.refresh_btn]:
            b.configure(state=s)
        self.port_combo.configure(state="disabled" if busy else "readonly")

    def _show_banner(self, text: str, success: bool):
        self._show_status(text, success)

    def _show_status(self, text: str, success: bool = True):
        self._status_seq = getattr(self, "_status_seq", 0) + 1
        curr_seq = self._status_seq

        if success:
            self.status_icon_lbl.configure(text="✓", text_color=("#16a34a", "#22c55e"))
            self.status_msg_lbl.configure(text_color=("#15803d", "#4ade80"))
        else:
            self.status_icon_lbl.configure(text="✗", text_color=("#dc2626", "#ef4444"))
            self.status_msg_lbl.configure(text_color=("#b91c1c", "#f87171"))

        self.status_msg_var.set(text)

        def _reset():
            if getattr(self, "_status_seq", 0) == curr_seq:
                self.status_icon_lbl.configure(text="●", text_color=("#22c55e", "#00e5ff"))
                self.status_msg_lbl.configure(text_color=("#475569", "#94a3b8"))
                self.status_msg_var.set("Готов к работе")
        self.after(8000, _reset)

    def _animate_progress(self, bar, duration: int):
        def _run():
            steps = duration * 20
            for i in range(steps):
                bar.set(min(0.93, i / steps))
                time.sleep(0.05)
        threading.Thread(target=_run, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════
    # ERASE
    # ══════════════════════════════════════════════════════════════════

    def _ask_erase_confirm(self):
        if not self._get_port():
            self.erase_status.set("⚠  Сначала выберите COM-порт.")
            return
        self.erase_btn.configure(state="disabled")
        self.confirm_frame.pack(fill="x", padx=8, pady=(8, 0), after=self.erase_btn)

    def _cancel_erase_confirm(self):
        self.confirm_frame.pack_forget()
        self.erase_btn.configure(state="normal")
        self.erase_status.set("Отменено.")

    def _do_erase(self):
        self.confirm_frame.pack_forget()
        threading.Thread(target=self._run_erase, args=(self._get_port(),), daemon=True).start()

    def _run_erase(self, port):
        self._set_busy(True)
        self.erase_status.set(f"Стираю {port}…")
        self._append_log(self.erase_log, f">>> erase_flash на {port}")
        try:
            out = run_esptool(["--port", port, "erase_flash"])
            for line in out.splitlines():
                if line.strip():
                    self._append_log(self.erase_log, line)
            self.erase_status.set("Готово! Flash-память полностью очищена.")
            self._show_banner("✓  Flash-память ESP32 успешно очищена.", True)
        except Exception as exc:
            self.erase_status.set("Ошибка!")
            self._append_log(self.erase_log, f">>> Ошибка: {exc}")
            self._show_banner(f"✗  Ошибка: {exc}", False)
        finally:
            self._set_busy(False)

    # ══════════════════════════════════════════════════════════════════
    # INFO (Direct ESPLoader API + CLI Regex Fallback)
    # ══════════════════════════════════════════════════════════════════

    def _get_info(self):
        port = self._get_port()
        if not port:
            self._show_banner("⚠  Сначала выберите COM-порт.", False)
            return
        threading.Thread(target=self._run_info, args=(port,), daemon=True).start()

    def _run_info(self, port):
        self._set_busy(True)
        self.info_status_var.set(f"⏳  Считываю параметры с {port}...")
        for v in self.tile_vars.values():
            v.set("—")

        data = {
            "chip": "—",
            "mac": "—",
            "flash_size": "—",
            "crystal": "—",
            "manufacturer": "—",
            "features": "—",
        }

        # Method 1: Direct ESPLoader API
        api_success = False
        try:
            with connect_esp(port=port, connect_attempts=3) as esp:
                esp = run_stub(esp)
                data["chip"] = esp.get_chip_description()
                features = esp.get_chip_features()
                if features:
                    data["features"] = ", ".join(features)
                try:
                    data["crystal"] = f"{esp.get_crystal_freq()} MHz"
                except Exception:
                    data["crystal"] = "40 MHz (стандарт)"
                try:
                    mac_bytes = esp.read_mac()
                    data["mac"] = ":".join(f"{b:02X}" for b in mac_bytes)
                except Exception:
                    pass
                try:
                    vendor_id, device_id, flash_size = _get_flash_info(esp)
                    if flash_size:
                        data["flash_size"] = flash_size
                    if vendor_id and vendor_id in VENDOR_NAMES:
                        data["manufacturer"] = VENDOR_NAMES[vendor_id]
                    elif vendor_id:
                        data["manufacturer"] = f"SPI Flash (0x{vendor_id:02X})"
                except Exception:
                    pass
                api_success = True
        except Exception:
            api_success = False

        # Method 2: CLI Flash ID Fallback if Direct API didn't get all fields
        if not api_success or data["chip"] == "—":
            try:
                out = run_esptool(["--port", port, "flash_id"])
                parsed = self._parse_flash_id_cli(out)
                for k, val in parsed.items():
                    if val != "—" and (data[k] == "—" or not data[k]):
                        data[k] = val
            except Exception:
                pass

        # Populate GUI
        has_any_data = any(v != "—" for v in data.values())
        if has_any_data:
            for k, val in data.items():
                if k in self.tile_vars:
                    self.tile_vars[k].set(val)
            self.info_status_var.set(f"✓  Данные успешно получены с {port}")
            self._show_banner(f"✓  Информация о плате {port} успешно обновлена.", True)
        else:
            self.info_status_var.set(f"✗  Не удалось прочитать данные с {port}. Проверьте подключение платы.")
            self._show_banner(f"✗  Не удалось прочитать данные с {port}.", False)

        self._set_busy(False)

    def _parse_flash_id_cli(self, out: str) -> dict:
        d = {
            "chip": "—",
            "mac": "—",
            "flash_size": "—",
            "crystal": "—",
            "manufacturer": "—",
            "features": "—",
        }
        for line in out.splitlines():
            line_s = line.strip()
            low = line_s.lower()
            if "chip is" in low:
                d["chip"] = line_s.split("is", 1)[1].strip().lstrip(":")
            elif "features:" in low:
                d["features"] = line_s.split(":", 1)[1].strip()
            elif "crystal is" in low:
                d["crystal"] = line_s.split("is", 1)[1].strip().lstrip(":")
            elif "mac:" in low:
                d["mac"] = line_s.split(":", 1)[1].strip().upper()
            elif "detected flash size:" in low:
                d["flash_size"] = line_s.split(":", 1)[1].strip()
            elif "manufacturer:" in low:
                m_hex = line_s.split(":", 1)[1].strip().lower()
                try:
                    m_int = int(m_hex, 16)
                    d["manufacturer"] = VENDOR_NAMES.get(m_int, f"SPI Flash (0x{m_hex})")
                except ValueError:
                    d["manufacturer"] = f"SPI Flash ({m_hex})"
        return d

    # ══════════════════════════════════════════════════════════════════
    # BACKUP
    # ══════════════════════════════════════════════════════════════════

    def _choose_backup_path(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".bin",
            filetypes=[("Binary files", "*.bin"), ("All files", "*.*")],
            title="Сохранить резервную копию как…",
            initialfile="esp32_backup.bin")
        if path:
            self.backup_path_var.set(path)

    def _do_backup(self):
        port, path = self._get_port(), self.backup_path_var.get()
        if not port:
            self._show_banner("⚠  Сначала выберите COM-порт.", False); return
        if not path or path == "Файл не выбран":
            self._show_banner("⚠  Сначала выберите путь для сохранения файла.", False); return
        threading.Thread(target=self._run_backup, args=(port, path), daemon=True).start()

    def _run_backup(self, port, path):
        self._set_busy(True)
        size_map = {"1MB":"0x100000","2MB":"0x200000","4MB":"0x400000",
                    "8MB":"0x800000","16MB":"0x1000000"}
        size_hex = size_map.get(self.backup_size_var.get(), "0x400000")
        self.backup_status.set(f"Считываю flash ({self.backup_size_var.get()})…")
        self.backup_progress.set(0)
        self._append_log(self.backup_log, f">>> read_flash 0x0 {size_hex} → {path}")
        self._animate_progress(self.backup_progress, 20)
        try:
            out = run_esptool(["--port", port, "read_flash", "0x0", size_hex, path])
            for line in out.splitlines():
                if line.strip():
                    self._append_log(self.backup_log, line)
            self.backup_progress.set(1)
            if os.path.exists(path):
                kb = os.path.getsize(path) // 1024
                self.backup_status.set(f"Готово! Сохранено {kb} КБ → {os.path.basename(path)}")
                self._show_banner(f"✓  Резервная копия сохранена: {os.path.basename(path)} ({kb} КБ)", True)
            else:
                self.backup_status.set("Ошибка: файл не создан.")
                self._show_banner("✗  Файл резервной копии не создан.", False)
        except Exception as exc:
            self.backup_status.set("Ошибка!")
            self._append_log(self.backup_log, f">>> Ошибка: {exc}")
            self._show_banner(f"✗  Ошибка: {exc}", False)
        finally:
            self._set_busy(False)

    # ══════════════════════════════════════════════════════════════════
    # FLASH
    # ══════════════════════════════════════════════════════════════════

    def _choose_flash_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Binary files", "*.bin"), ("All files", "*.*")],
            title="Выберите файл прошивки (.bin)…")
        if path:
            self.flash_path_var.set(path)

    def _do_flash(self):
        port, path = self._get_port(), self.flash_path_var.get()
        if not port:
            self._show_banner("⚠  Сначала выберите COM-порт.", False); return
        if not path or path == "Файл не выбран":
            self._show_banner("⚠  Сначала выберите .bin файл прошивки.", False); return
        if not os.path.exists(path):
            self._show_banner("⚠  Файл не найден.", False); return
        threading.Thread(target=self._run_flash, args=(port, path), daemon=True).start()

    def _run_flash(self, port, path):
        self._set_busy(True)
        addr, baud = self.flash_addr_var.get(), self.baud_var.get()
        kb = os.path.getsize(path) // 1024
        self.flash_status.set(f"Прошиваю {os.path.basename(path)} ({kb} КБ) → {addr}…")
        self.flash_progress.set(0)
        self._append_log(self.flash_log, f">>> write_flash {addr} {path}")
        self._animate_progress(self.flash_progress, 20)
        try:
            out = run_esptool(["--port", port, "--baud", baud,
                               "write_flash", "-z", addr, path])
            for line in out.splitlines():
                if line.strip():
                    self._append_log(self.flash_log, line)
            self.flash_progress.set(1)
            self.flash_status.set("Готово! Прошивка успешно загружена.")
            self._show_banner(f"✓  Прошивка загружена: {os.path.basename(path)}", True)
        except Exception as exc:
            self.flash_status.set("Ошибка!")
            self._append_log(self.flash_log, f">>> Ошибка: {exc}")
            self._show_banner(f"✗  Ошибка прошивки: {exc}", False)
        finally:
            self._set_busy(False)

    # ══════════════════════════════════════════════════════════════════
    # MONITOR
    # ══════════════════════════════════════════════════════════════════

    def _monitor_start(self):
        port = self._get_port()
        if not port:
            self._show_banner("⚠  Сначала выберите COM-порт.", False); return
        if self._monitor_run:
            return
        try:
            self._monitor_ser = serial.Serial(port, self._get_baud(), timeout=0.1)
            self._monitor_run = True
            self.mon_status.set(f"Статус: Подключено ({port} @ {self._get_baud()})")
            self.mon_start_btn.configure(state="disabled")
            self.mon_stop_btn.configure(state="normal")
            threading.Thread(target=self._monitor_loop, daemon=True).start()
        except Exception as exc:
            self._show_banner(f"✗  Не удалось открыть порт: {exc}", False)

    def _monitor_stop(self):
        self._monitor_run = False
        if self._monitor_ser:
            try: self._monitor_ser.close()
            except: pass
            self._monitor_ser = None
        self.mon_status.set("Статус: Не подключено")
        self.mon_start_btn.configure(state="normal")
        self.mon_stop_btn.configure(state="disabled")

    def _monitor_loop(self):
        while self._monitor_run and self._monitor_ser:
            try:
                data = self._monitor_ser.read(256)
                if data:
                    text = data.decode("utf-8", errors="replace")
                    self.monitor_log.configure(state="normal")
                    self.monitor_log.insert("end", text)
                    self.monitor_log.see("end")
                    self.monitor_log.configure(state="disabled")
            except Exception:
                break
        self._monitor_stop()

    def _monitor_send(self):
        if not self._monitor_run or not self._monitor_ser:
            self._show_banner("⚠  Сначала подключитесь к порту.", False); return
        text = self.send_var.get()
        if text:
            try:
                self._monitor_ser.write((text + "\r\n").encode("utf-8"))
                self._append_log(self.monitor_log, f"  ← {text}")
                self.send_var.set("")
            except Exception as exc:
                self._show_banner(f"✗  Ошибка отправки: {exc}", False)

    def _monitor_clear(self):
        self.monitor_log.configure(state="normal")
        self.monitor_log.delete("1.0", "end")
        self.monitor_log.configure(state="disabled")

    def on_closing(self):
        self._monitor_stop()
        self.destroy()


if __name__ == "__main__":
    app = CommanderApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
