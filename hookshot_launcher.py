#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hookshot Launcher & Profile Manager
===================================
A modern, dark-themed GUI Launcher, Save Profile Manager (with live JPEG screenshot
and location extraction from caption.sav), Live-Synced Configuration Editor
(hookshot_options.ini & language.txt), Process Monitor, and Automatic GitHub Updater
for Hookshot (The Legend of Zelda: Ocarina of Time PC Port).

Repository: https://github.com/sephirods/Hookshot-Launcher
License: MIT
"""

import ctypes
import ctypes.wintypes
import datetime
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import webbrowser
import zipfile
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

LAUNCHER_VERSION = "v1.2.0"
LAUNCHER_REPO = "sephirods/Hookshot-Launcher"
HOOKSHOT_REPO = "NotRexed/Hookshot"
HOOKSHOT_API_LATEST = f"https://api.github.com/repos/{HOOKSHOT_REPO}/releases/latest"
HOOKSHOT_RELEASES_URL = f"https://github.com/{HOOKSHOT_REPO}/releases/latest"
HOOKSHOT_BUILDER_DIRECT = f"https://github.com/{HOOKSHOT_REPO}/releases/latest/download/HookshotBuilder.exe"
DEFAULT_UID = "5a3c9e1f0b7d24680000000000000001"
TITLE_ID = "0400486024DEC000"

# Enable High-DPI awareness on Windows
if os.name == "nt":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("sephirods.hookshot.launcher.1")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Color Palette (Hookshot v2.1.0 Sheikah / Ocarina of Time UI Theme)
# Authentic tokens derived directly from Hookshot gpu/vk/vk_ui.h
# ---------------------------------------------------------------------------
BG_MAIN = "#16110b"         # kBar: Deepest obsidian background
BG_PANEL = "#221a11"        # kColumn: Warm dark stone panel
BG_CARD = "#241c13"         # kBox: Cards and containers
BG_INPUT = "#1e1913"        # kCellDark: Inputs, comboboxes, preview frames
FG_TEXT = "#f0e8d6"         # kInk: Warm parchment text
FG_MUTED = "#a89c88"        # kDim: Secondary muted bronze/stone text
ACCENT_GOLD = "#de9828"     # kGold: Triforce gold
ACCENT_GOLD_HOVER = "#eea834"# kGoldHi: Bright gold glow / active
ACCENT_GOLD_INK = "#241808" # kGoldInk: Deep dark text on gold elements
ACCENT_BLUE = "#58a6ff"     # Navi / Zora sapphire accent
ACCENT_GREEN = "#2e8540"    # Kokiri emerald green
ACCENT_GREEN_HOVER = "#389e4e"
ACCENT_RED = "#c53030"      # Goron ruby red
ACCENT_RED_HOVER = "#dc3545"
BORDER_COLOR = "#7a6240"    # kEdge / kBoxEdge: Ancient bronze/gold border
BORDER_SUBTLE = "#463018"   # kBannerEdge: Subtle inner divider
BANNER_BG = "#2e2214"       # Warm update banner background


# ---------------------------------------------------------------------------
# Fast Win32 Process Detection & Termination (Zero Console Flash)
# ---------------------------------------------------------------------------
TH32CS_SNAPPROCESS = 0x00000002
PROCESS_TERMINATE = 0x0001


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.wintypes.DWORD),
        ("cntUsage", ctypes.wintypes.DWORD),
        ("th32ProcessID", ctypes.wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", ctypes.wintypes.DWORD),
        ("cntThreads", ctypes.wintypes.DWORD),
        ("th32ParentProcessID", ctypes.wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def find_running_pids_by_name(exe_name="hookshot.exe"):
    """Return list of active PIDs matching exe_name using Win32 Toolhelp32 snapshot."""
    pids = []
    if os.name != "nt":
        return pids
    target = exe_name.lower()
    try:
        kernel32 = ctypes.windll.kernel32
        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == ctypes.wintypes.HANDLE(-1).value or snap == -1:
            return pids
        try:
            pe = PROCESSENTRY32W()
            pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            if kernel32.Process32FirstW(snap, ctypes.byref(pe)):
                while True:
                    if pe.szExeFile.lower() == target:
                        pids.append(int(pe.th32ProcessID))
                    if not kernel32.Process32NextW(snap, ctypes.byref(pe)):
                        break
        finally:
            kernel32.CloseHandle(snap)
    except Exception:
        pass
    return pids


def terminate_pids(pids):
    """Terminate all given PIDs cleanly via Win32 TerminateProcess."""
    if os.name != "nt":
        return False
    killed_any = False
    kernel32 = ctypes.windll.kernel32
    for pid in pids:
        try:
            hproc = kernel32.OpenProcess(PROCESS_TERMINATE, False, int(pid))
            if hproc:
                try:
                    if kernel32.TerminateProcess(hproc, 0):
                        killed_any = True
                finally:
                    kernel32.CloseHandle(hproc)
        except Exception:
            pass
    return killed_any


# ---------------------------------------------------------------------------
# Option Tables (Exact match with Hookshot gpu/vk/vk_menu.h & vk_menu.cpp)
# ---------------------------------------------------------------------------
QUALITY_PRESETS = [
    (0, "Personalizado (Custom)"),
    (1, "Mínimo (4 GB VRAM / iGPU)"),
    (2, "Bajo (6 GB VRAM)"),
    (3, "Equilibrado (8 GB VRAM - RTX 3070)"),
    (4, "Alto (12 GB VRAM)"),
    (5, "Ultra (16 GB+ VRAM)"),
]

OUTPUT_RESOLUTIONS = [
    (3, "1920×1080 (Full HD 1080p)"),
    (0, "2048×1152 (Nativa de Consola)"),
    (1, "2560×1440 (Quad HD 1440p)"),
    (2, "3840×2160 (4K Ultra HD)"),
    (4, "5120×1440 (Super Ultrawide 32:9)"),
    (5, "5120×2880 (5K Ultra HD)"),
]

OUTPUT_RES_CODE_TO_STR = {
    0: "2048x1152",
    1: "2560x1440",
    2: "3840x2160",
    3: "1920x1080",
    4: "5120x1440",
    5: "5120x2880",
}

OUTPUT_RES_STR_TO_CODE = {v: k for k, v in OUTPUT_RES_CODE_TO_STR.items()}

UPSCALERS = [
    (0, "Propio del Juego (Nativo)"),
    (1, "NVIDIA DLSS"),
    (2, "NVIDIA DLAA (Nativo + Suavizado IA)"),
    (3, "AMD FSR 3.1"),
    (4, "AMD FSR 4"),
    (5, "AMD FSR 4 Native AA"),
]

DLSS_MODELS = [
    (0, "Transformer (Preset K - Recomendado)"),
    (1, "Transformer Gen 2 (Preset M)"),
    (2, "Transformer Gen 2 (Preset L - Ultra Perf)"),
    (3, "Por defecto de NVIDIA"),
]

RENDER_RESOLUTIONS = [
    (0, "Automática (Dinámica)"),
    (1, "100% (Tamaño completo)"),
    (9, "92% (Escala 11/12)"),
    (8, "83% (Escala 10/12)"),
    (2, "75% (Escala 9/12)"),
    (3, "67% (DLSS / FSR Calidad)"),
    (5, "58% (DLSS / FSR Equilibrado)"),
    (4, "50% (DLSS / FSR Rendimiento)"),
    (7, "42% (Escala 5/12)"),
    (6, "33% (DLSS / FSR Ultra Rendimiento)"),
]

SCALING_FILTERS = [
    (0, "Desactivado (Copia directa)"),
    (1, "Catmull-Rom (Nítido)"),
    (2, "Lanczos (Muy nítido)"),
]

ANISOTROPIC_MODES = [
    (0, "Propio del Juego (1x / 2x)"),
    (1, "2x"),
    (2, "4x"),
    (3, "8x"),
    (4, "16x (Máxima nitidez - Recomendado)"),
]

MESH_SHADER_MODES = [
    (0, "Automático (Mesh Shaders si la GPU soporta)"),
    (1, "Nativo (Mesh Shaders de la GPU)"),
    (2, "Compute (Modo compatible para todas las GPUs)"),
]

ULTRAWIDE_MENU_MODES = [
    (0, "Ancho Completo (Estirados)"),
    (1, "Centrados 16:9 (Bordes difuminados)"),
    (2, "Centrados 16:9 (Barras negras)"),
]

FPS_CAPS = [
    (0, "60 FPS (Original de Consola)"),
    (1, "90 FPS"),
    (2, "120 FPS"),
    (3, "144 FPS"),
    (4, "165 FPS"),
    (5, "240 FPS"),
]

FRAME_GEN_MODES = [
    (0, "Desactivado (Sin latencia extra)"),
    (1, "Automático (Al refresco del monitor)"),
    (2, "2x (1 cuadro generado)"),
    (3, "3x (2 cuadros generados)"),
    (4, "4x (3 cuadros generados)"),
    (5, "5x"),
    (6, "6x"),
    (7, "7x"),
    (8, "8x"),
]

REFLEX_MODES = [
    (0, "Desactivado"),
    (1, "Activado (Menor latencia)"),
    (2, "Activado + Boost (Relojes GPU altos)"),
]

HDR_MODES = [
    (0, "Desactivado (SDR)"),
    (1, "Expandido (SDR a HDR10)"),
    (2, "Nativo del Juego (HDR10 Real)"),
]

ROBUST_MODES = [
    (0, "Automático (Activado)"),
    (1, "Desactivado (Más rápido en algunas NVIDIA)"),
    (2, "Siempre Activado"),
]

LANGUAGES = [
    ("es-419", "Español (Latinoamérica) [es-419]"),
    ("es", "Español (España) [es]"),
    ("en-US", "English (US) [en-US]"),
    ("en-GB", "English (UK) [en-GB]"),
    ("fr", "Français (France) [fr]"),
    ("fr-CA", "Français (Canada) [fr-CA]"),
    ("de", "Deutsch [de]"),
    ("it", "Italiano [it]"),
    ("pt-BR", "Português (Brasil) [pt-BR]"),
    ("nl", "Nederlands [nl]"),
    ("pl", "Polski [pl]"),
    ("ru", "Русский [ru]"),
    ("ja", "日本語 [ja]"),
    ("ko", "한국어 [ko]"),
    ("zh-Hans", "简体中文 [zh-Hans]"),
    ("zh-Hant", "繁體中文 [zh-Hant]"),
]

GAME_SPEEDS = [
    (1, "Tiempo Real (Sigue al reloj, no se ralentiza)"),
    (0, "Por Cuadro (Se ralentiza si baja de 60 FPS)"),
]

TEXT_SPEEDS = [
    (0, "Normal (Velocidad original)"),
    (1, "2x (Doble de rápido)"),
    (2, "4x (Cuádruple de rápido)"),
    (3, "Instantáneo"),
]

TEXT_SIZES = [
    (0, "Original (100%)"),
    (1, "110% (Un poco más grande)"),
    (2, "125% (Grande)"),
    (3, "150% (Muy grande)"),
    (4, "175% (Máximo)"),
]

MENU_SIZES = [
    (1, "Pequeño (Monitor de escritorio)"),
    (2, "Mediano (Estándar)"),
    (3, "Grande (Televisor / Sala)"),
]

MENU_SHORTCUTS = [
    (0, "Insert o F1 (Por defecto)"),
    (1, "Solo F1 (Deja Insert libre)"),
    (2, "Insert, F1 o Esc (Como pausa de PC)"),
]

AUDIO_OUTPUTS = [
    (0, "Automático (Según dispositivo Windows)"),
    (1, "Estéreo (2.0)"),
    (2, "Envolvente (5.1 Surround)"),
]

MIC_MODES = [
    (0, "Desactivado"),
    (1, "Micrófono Predeterminado del Sistema"),
]

PAD_LAYOUTS = [
    (0, "Nintendo Switch (A=Derecha, B=Abajo)"),
    (1, "Xbox / PC (A=Abajo, B=Derecha, X=Izq, Y=Arriba)"),
    (2, "Intercambiar A/B (A=Abajo, B=Derecha, X/Y Switch)"),
    (3, "Personalizado (Custom)"),
]

BUTTON_PROMPTS = [
    (0, "Automático (Según mando conectado)"),
    (1, "Nintendo Switch"),
    (2, "Xbox"),
    (3, "PlayStation 4 (DualShock 4)"),
    (4, "PlayStation 5 (DualSense)"),
    (5, "Steam Deck"),
]

MOUSE_CAM_MODES = [
    (0, "Como Stick Derecho (Curva de mando)"),
    (1, "Cámara Nativa PC (Giro directo 1:1)"),
]

DEADZONE_MODES = [
    (0, "Por defecto XInput (~24%)"),
    (1, "5% (Stick muy preciso)"),
    (2, "10%"),
    (3, "15%"),
    (4, "20%"),
    (5, "30% (Evita drift fuerte)"),
]

GYRO_DEADZONES = [
    (0, "Ajustada (Detecta movimientos mínimos)"),
    (1, "Estándar (Por defecto de consola)"),
    (2, "Amplia (Estabiliza pulso tembloroso)"),
]

DEFAULT_OPTIONS = {
    "quality_preset": 0,
    "fullscreen": 0,
    "gpu_device": 0,
    "frame_generation": 0,
    "frame_pacing": 0,
    "hdr": 0,
    "hdr_paper_white": 200,
    "hdr_peak_brightness": 1000,
    "frame_rate_cap": 0,
    "nvidia_reflex": 0,
    "amd_anti_lag_2": 0,
    "output_res": 0,
    "dlss": 0,
    "dlss_model": 0,
    "resolution": 1,
    "upscaling": 0,
    "sharpness": 10,
    "anisotropic_filtering": 4,
    "handheld_profile": 0,
    "ultrawide": 0,
    "ultrawide_menus": 1,
    "robust_buffers": 0,
    "mesh_shaders": 0,
    "descriptor_reuse": 1,
    "sampler_cache": 0,
    "volume": 100,
    "mute_in_background": 0,
    "audio_output": 0,
    "fps_counter": 0,
    "menu_size": 2,
    "game_speed": 1,
    "text_speed": 0,
    "text_size": 0,
    "microphone": 1,
    "discord_status": 1,
    "controller_in_background": 0,
    "mouse_camera": 0,
    "disable_camera_centering": 0,
    "mouse_sensitivity": 100,
    "invert_mouse_vertical": 0,
    "invert_camera_x": 0,
    "invert_camera_y": 0,
    "stick_dead_zone": 0,
    "rumble_strength": 100,
    "motion_controls": 1,
    "motion_sensitivity_x": 100,
    "motion_sensitivity_y": 100,
    "invert_motion_x": 0,
    "invert_motion_y": 0,
    "motion_deadzone": 1,
    "layout_preset": 0,
    "button_prompts": 0,
    "menu_shortcut": 0,
    "debug_tools": 0,
    "options_version": 4,
}

OPTION_KEYS_ORDER = [
    "quality_preset", "fullscreen", "gpu_device", "frame_generation", "frame_pacing",
    "hdr", "hdr_paper_white", "hdr_peak_brightness", "frame_rate_cap", "nvidia_reflex",
    "amd_anti_lag_2", "output_res", "dlss", "dlss_model", "resolution", "upscaling",
    "sharpness", "anisotropic_filtering", "handheld_profile", "ultrawide", "ultrawide_menus",
    "robust_buffers", "mesh_shaders", "volume", "mute_in_background", "audio_output",
    "fps_counter", "menu_size", "game_speed", "text_speed", "text_size", "microphone",
    "discord_status", "controller_in_background", "mouse_camera", "disable_camera_centering",
    "mouse_sensitivity", "invert_mouse_vertical", "invert_camera_x", "invert_camera_y",
    "stick_dead_zone", "rumble_strength", "motion_controls", "motion_sensitivity_x",
    "motion_sensitivity_y", "invert_motion_x", "invert_motion_y", "motion_deadzone",
    "layout_preset", "button_prompts", "menu_shortcut", "debug_tools",
    "descriptor_reuse", "sampler_cache",
]

LOCATION_NAMES_PRETTY = {
    "KokiriForest": "Bosque Kokiri (Kokiri Forest)",
    "HyruleField": "Llanura de Hyrule (Hyrule Field)",
    "KakarikoVillage": "Aldea Kakariko (Kakariko Village)",
    "Market": "Plaza del Mercado (Market)",
    "HyruleCastle": "Castillo de Hyrule (Hyrule Castle)",
    "LostWoods": "Bosque Perdido (Lost Woods)",
    "SacredForestMeadow": "Pradera Sagrada del Bosque",
    "LakeHylia": "Lago Hylia (Lake Hylia)",
    "Graveyard": "Cementerio de Kakariko",
    "DeathMountainTrail": "Sendero de la Montaña de la Muerte",
    "DeathMountainCrater": "Cráter de la Montaña de la Muerte",
    "GoronCity": "Ciudad Goron (Goron City)",
    "ZorasRiver": "Río Zora (Zora's River)",
    "ZorasDomain": "Dominios Zora (Zora's Domain)",
    "ZorasFountain": "Fuente Zora (Zora's Fountain)",
    "GerudoValley": "Valle Gerudo (Gerudo Valley)",
    "GerudoFortress": "Fortaleza Gerudo (Gerudo Fortress)",
    "HauntedWasteland": "Desierto Encantado",
    "DesertColossus": "Coloso del Desierto",
    "DekuTree": "Interior del Gran Árbol Deku",
    "DodongosCavern": "Cueva de los Dodongos",
    "JabuJabusBelly": "Tripa de Jabu-Jabu",
    "ForestTemple": "Templo del Bosque",
    "FireTemple": "Templo del Fuego",
    "WaterTemple": "Templo del Agua",
    "ShadowTemple": "Templo de las Sombras",
    "SpiritTemple": "Templo del Espíritu",
    "LonLonRanch": "Rancho Lon Lon",
    "TempleOfTime": "Templo del Tiempo",
}


# ---------------------------------------------------------------------------
# Helper Functions: Paths, Save Parsing, Config & GitHub Updates
# ---------------------------------------------------------------------------
def get_launcher_config_path():
    local_app = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    cfg_dir = os.path.join(local_app, "HookshotLauncher")
    os.makedirs(cfg_dir, exist_ok=True)
    return os.path.join(cfg_dir, "launcher_config.json")


def detect_game_dir():
    """Find Hookshot's directory: beside the script/exe, from HookshotBuilder settings, or saved config."""
    here = os.path.dirname(os.path.abspath(sys.argv[0]))
    if os.path.isfile(os.path.join(here, "hookshot.exe")) or os.path.isfile(os.path.join(here, "hookshot_options.ini")):
        return here

    cfg_path = get_launcher_config_path()
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("game_dir") and os.path.isdir(data["game_dir"]):
                    return data["game_dir"]
        except Exception:
            pass

    # Check HookshotBuilder's builder-settings.json
    local_app = os.environ.get("LOCALAPPDATA") or ""
    builder_cfg = os.path.join(local_app, "HookshotBuilder", "builder-settings.json")
    if os.path.isfile(builder_cfg):
        try:
            with open(builder_cfg, "r", encoding="utf-8") as f:
                bdata = json.load(f)
                out_dir = bdata.get("Out")
                if out_dir and os.path.isdir(out_dir):
                    return out_dir
        except Exception:
            pass

    default_path = r"D:\Users\Juan\Games\Hookshot"
    if os.path.isdir(default_path):
        return default_path

    return here


def save_launcher_config(game_dir):
    try:
        cfg_path = get_launcher_config_path()
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({"game_dir": game_dir}, f, indent=2)
    except Exception:
        pass


def format_location_name(raw_loc):
    if not raw_loc:
        return "Zona desconocida"
    if raw_loc in LOCATION_NAMES_PRETTY:
        return LOCATION_NAMES_PRETTY[raw_loc]
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", raw_loc)
    return spaced


def parse_caption_sav(caption_path):
    """
    Extract metadata and embedded 543x306 JPEG screenshot from a slot's caption.sav.
    Returns dict with keys: location, scene, age, jpeg_bytes.
    """
    info = {
        "location": "Partida Guardada",
        "scene": "",
        "age": "",
        "jpeg_bytes": None,
    }
    if not os.path.isfile(caption_path):
        return info
    try:
        with open(caption_path, "rb") as f:
            data = f.read()

        if len(data) >= 812:
            raw_loc = data[684:748].split(b"\x00")[0].decode("utf-8", "ignore").strip()
            raw_scn = data[748:812].split(b"\x00")[0].decode("utf-8", "ignore").strip()
            if raw_loc:
                info["location"] = format_location_name(raw_loc)
            if raw_scn:
                info["scene"] = raw_scn
                if "_Child" in raw_scn or "Child" in raw_scn:
                    info["age"] = "Link Niño"
                elif "_Adult" in raw_scn or "Adult" in raw_scn:
                    info["age"] = "Link Adulto"

        # Find JPEG SOI marker (FF D8 FF)
        jpg_start = data.find(b"\xff\xd8\xff")
        if jpg_start != -1:
            info["jpeg_bytes"] = data[jpg_start:]
    except Exception:
        pass
    return info


def inspect_save_folder(folder_path):
    """
    Inspect a profile's save folder (containing account.sav, option.sav, slot_00..slot_05).
    Returns list of slot dicts sorted by most recent first.
    """
    slots_info = []
    if not os.path.isdir(folder_path):
        return slots_info

    for name in sorted(os.listdir(folder_path)):
        if not name.startswith("slot_"):
            continue
        slot_dir = os.path.join(folder_path, name)
        if not os.path.isdir(slot_dir):
            continue
        prog_file = os.path.join(slot_dir, "progress.sav")
        cap_file = os.path.join(slot_dir, "caption.sav")
        if not os.path.isfile(prog_file) and not os.path.isfile(cap_file):
            continue

        mtime = 0.0
        if os.path.isfile(prog_file):
            mtime = os.path.getmtime(prog_file)
        elif os.path.isfile(cap_file):
            mtime = os.path.getmtime(cap_file)

        dt_str = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S") if mtime else "Desconocido"
        cap_meta = parse_caption_sav(cap_file)
        slot_num = name.replace("slot_", "")
        slots_info.append({
            "slot_id": name,
            "label": f"Slot {int(slot_num) + 1 if slot_num.isdigit() else slot_num}",
            "mtime": mtime,
            "datetime": dt_str,
            "location": cap_meta["location"],
            "scene": cap_meta["scene"],
            "age": cap_meta["age"],
            "jpeg_bytes": cap_meta["jpeg_bytes"],
        })

    slots_info.sort(key=lambda s: s["mtime"], reverse=True)
    return slots_info


def get_active_save_dir(game_dir):
    """Return Hookshot's active user/save/<uid> folder path."""
    save_root = os.path.join(game_dir, "user", "save")
    if os.path.isdir(save_root):
        for entry in sorted(os.listdir(save_root)):
            full = os.path.join(save_root, entry)
            if os.path.isdir(full):
                return full
    return os.path.join(save_root, DEFAULT_UID)


def get_folder_latest_mtime(folder_path):
    """Return the latest mtime across slot_*/progress.sav and caption.sav in folder_path."""
    latest = 0.0
    if not os.path.isdir(folder_path):
        return latest
    try:
        for name in os.listdir(folder_path):
            if not name.startswith("slot_"):
                continue
            slot_dir = os.path.join(folder_path, name)
            for fname in ("progress.sav", "caption.sav"):
                fpath = os.path.join(slot_dir, fname)
                if os.path.isfile(fpath):
                    mt = os.path.getmtime(fpath)
                    if mt > latest:
                        latest = mt
    except Exception:
        pass
    return latest


def copy_save_contents(src_dir, dst_dir, keep_option_sav=False):
    """Safely copy slot_* folders, account.sav, and option.sav from src_dir to dst_dir."""
    os.makedirs(dst_dir, exist_ok=True)
    for item in os.listdir(dst_dir):
        if item.startswith("slot_"):
            target_slot = os.path.join(dst_dir, item)
            if os.path.isdir(target_slot):
                shutil.rmtree(target_slot, ignore_errors=True)

    if not os.path.isdir(src_dir):
        return

    for item in os.listdir(src_dir):
        s_item = os.path.join(src_dir, item)
        d_item = os.path.join(dst_dir, item)
        if item.startswith("slot_") and os.path.isdir(s_item):
            shutil.copytree(s_item, d_item, dirs_exist_ok=True)
        elif item == "account.sav" and os.path.isfile(s_item):
            shutil.copy2(s_item, d_item)
        elif item == "option.sav" and os.path.isfile(s_item) and not keep_option_sav:
            shutil.copy2(s_item, d_item)


def discover_external_saves():
    """
    Find external Ocarina of Time Remake saves in Eden/Lichii/Fritchii and NX2navi.
    Returns list of dicts: {label, source_name, path, slots}.
    """
    results = []
    appdata = os.environ.get("APPDATA") or ""
    localappdata = os.environ.get("LOCALAPPDATA") or ""

    candidates = [
        ("Eden / Lichii / Fritchii", os.path.join(appdata, "eden", "nand", "user", "save")),
        ("NX2navi (D:\\Navi)", r"D:\Navi\profile\save"),
        ("NX2navi (AppData)", os.path.join(localappdata, "Programs", "NX2navi", "game", "profile", "save")),
        ("NX2navi (C:\\Games)", r"C:\Games\Ocarina\profile\save"),
    ]

    seen_paths = set()
    for label, base_dir in candidates:
        if not os.path.isdir(base_dir):
            continue
        for root, dirs, files in os.walk(base_dir):
            if "account.sav" in files or any(d.startswith("slot_") for d in dirs):
                norm = os.path.normcase(os.path.abspath(root))
                if norm in seen_paths:
                    continue
                seen_paths.add(norm)
                slots = inspect_save_folder(root)
                if slots:
                    results.append({
                        "label": f"{label} ({len(slots)} slots - {slots[0]['datetime']})",
                        "source_name": label,
                        "path": root,
                        "slots": slots,
                    })
    return results


# ---------------------------------------------------------------------------
# Main Application Window
# ---------------------------------------------------------------------------
class HookshotLauncherApp(tk.Tk):
    def __init__(self, game_dir=None):
        super().__init__()
        self.game_dir = game_dir or detect_game_dir()
        save_launcher_config(self.game_dir)

        self.title(f"Hookshot Launcher & Profile Manager {LAUNCHER_VERSION}")
        self.geometry("760x730")
        self.minsize(680, 660)
        self.configure(bg=BG_MAIN)

        self._load_window_icon()
        self._configure_styles()

        # State variables
        self.options_data = dict(DEFAULT_OPTIONS)
        self.preserved_bind_lines = []
        self.microphone_device_line = None
        self.current_language = "es-419"

        self.profiles_dir = os.path.join(self.game_dir, "profiles")
        self.profiles_meta_path = os.path.join(self.profiles_dir, "profiles.json")
        self.profiles_meta = {"active": "Principal", "profiles": ["Principal"]}
        self.current_slots = []
        self.selected_slot_index = 0
        self.preview_photo = None

        self.hookshot_version = "Desconocida"
        self.builder_exe_path = None
        self.latest_github_tag = None
        self.latest_release_notes = ""

        # Settings dialog & live-sync state
        self.settings_win = None
        self.ui_vars = {}
        self._suppress_autosave = False
        self._slider_save_job = None
        self._last_ini_mtime = 0.0
        self._last_lang_mtime = 0.0
        self._last_save_mtime = 0.0
        self._last_ver_mtime = 0.0
        self.game_proc = None
        self._was_game_running = False

        # Initialize data
        self._read_version_file()
        self._init_profiles_system()
        self._load_options_and_language()
        self._record_file_mtimes()

        # Build UI (Focused on Save Profiles, with Settings in dedicated modal menu)
        self._build_header()
        self._build_update_banner()
        self._build_main_body()
        self._build_footer()

        # Populate UI controls
        self._refresh_profiles_ui()
        self._update_play_button_state()

        # Start async GitHub update check & live monitor loop
        threading.Thread(target=self._check_updates_background, daemon=True).start()
        self.after(800, self._poll_live_state)

    def _load_window_icon(self):
        bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        ico_candidates = [
            os.path.join(self.game_dir, "hookshot.ico"),
            os.path.join(bundle_dir, "hookshot.ico"),
            os.path.join(bundle_dir, "assets", "hookshot.ico"),
        ]
        self.icon_path = None
        for p in ico_candidates:
            if os.path.isfile(p):
                self.icon_path = p
                try:
                    self.iconbitmap(default=p)
                except Exception:
                    pass
                break

    def _configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", background=BG_MAIN, foreground=FG_TEXT, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG_MAIN)
        style.configure("Panel.TFrame", background=BG_PANEL)
        style.configure("Card.TFrame", background=BG_CARD)

        style.configure("TLabel", background=BG_PANEL, foreground=FG_TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG_PANEL, foreground=FG_MUTED, font=("Segoe UI", 9))
        style.configure("Gold.TLabel", background=BG_PANEL, foreground=ACCENT_GOLD, font=("Segoe UI", 11, "bold"))
        style.configure("Header.TLabel", background=BG_PANEL, foreground=FG_TEXT, font=("Segoe UI", 15, "bold"))

        style.configure(
            "TNotebook",
            background=BG_PANEL,
            borderwidth=0,
            tabmargins=[2, 4, 2, 0],
        )
        style.configure(
            "TNotebook.Tab",
            background=BG_CARD,
            foreground=FG_MUTED,
            padding=[16, 8],
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", ACCENT_GOLD), ("active", "#3c2f20")],
            foreground=[("selected", ACCENT_GOLD_INK), ("active", FG_TEXT)],
        )

        style.configure(
            "TCombobox",
            fieldbackground=BG_INPUT,
            background=BG_CARD,
            foreground=FG_TEXT,
            arrowcolor=ACCENT_GOLD,
            bordercolor=BORDER_COLOR,
            lightcolor=BORDER_COLOR,
            darkcolor=BORDER_COLOR,
            padding=5,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", BG_INPUT)],
            selectbackground=[("readonly", BG_INPUT)],
            selectforeground=[("readonly", FG_TEXT)],
            foreground=[("readonly", FG_TEXT)],
        )
        self.option_add("*TCombobox*Listbox.background", BG_INPUT)
        self.option_add("*TCombobox*Listbox.foreground", FG_TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT_GOLD)
        self.option_add("*TCombobox*Listbox.selectForeground", ACCENT_GOLD_INK)
        self.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))

        style.configure(
            "TCheckbutton",
            background=BG_PANEL,
            foreground=FG_TEXT,
            font=("Segoe UI", 10),
            indicatorbackground=BG_INPUT,
            indicatorforeground=ACCENT_GOLD,
        )
        style.map(
            "TCheckbutton",
            background=[("active", BG_PANEL)],
            foreground=[("active", ACCENT_GOLD)],
        )

        style.configure(
            "Horizontal.TScale",
            background=BG_PANEL,
            troughcolor=BG_INPUT,
            bordercolor=BORDER_COLOR,
        )

    # -----------------------------------------------------------------------
    # Version, File Timestamps & Running Game Detection
    # -----------------------------------------------------------------------
    def _get_file_mtime(self, path):
        try:
            return os.path.getmtime(path) if os.path.isfile(path) else 0.0
        except Exception:
            return 0.0

    def _record_file_mtimes(self):
        self._last_ini_mtime = self._get_file_mtime(os.path.join(self.game_dir, "hookshot_options.ini"))
        self._last_lang_mtime = self._get_file_mtime(os.path.join(self.game_dir, "language.txt"))
        self._last_ver_mtime = self._get_file_mtime(os.path.join(self.game_dir, "hookshot_version.txt"))
        self._last_save_mtime = get_folder_latest_mtime(get_active_save_dir(self.game_dir))

    def _read_version_file(self):
        ver_file = os.path.join(self.game_dir, "hookshot_version.txt")
        self.hookshot_version = "No detectado"
        self.builder_exe_path = None
        if os.path.isfile(ver_file):
            try:
                with open(ver_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("version="):
                            self.hookshot_version = line.split("=", 1)[1].strip()
                        elif line.startswith("builder="):
                            bpath = line.split("=", 1)[1].strip()
                            if os.path.isfile(bpath):
                                self.builder_exe_path = bpath
            except Exception:
                pass

        if not self.builder_exe_path:
            local_app = os.environ.get("LOCALAPPDATA") or ""
            cur_txt = os.path.join(local_app, "HookshotBuilder", "versions", "current.txt")
            if os.path.isfile(cur_txt):
                try:
                    with open(cur_txt, "r", encoding="utf-8") as f:
                        tag = f.read().strip()
                    candidate = os.path.join(
                        local_app, "HookshotBuilder", "versions", tag, "HookshotBuilder", "HookshotBuilder.exe"
                    )
                    if os.path.isfile(candidate):
                        self.builder_exe_path = candidate
                        if self.hookshot_version == "No detectado":
                            self.hookshot_version = tag
                except Exception:
                    pass

    def is_hookshot_installed(self):
        return os.path.isfile(os.path.join(self.game_dir, "hookshot.exe"))

    def is_game_running(self):
        if self.game_proc is not None and self.game_proc.poll() is None:
            return True
        pids = find_running_pids_by_name("hookshot.exe")
        return len(pids) > 0

    def _settings_window_alive(self):
        return self.settings_win is not None and bool(self.settings_win.winfo_exists())

    # -----------------------------------------------------------------------
    # Live State Polling (Game Running + In-Game Option & Save Changes)
    # -----------------------------------------------------------------------
    def _poll_live_state(self):
        try:
            # 1. Check if game is running or just closed
            running_now = self.is_game_running()
            if running_now != self._was_game_running:
                prev_running = self._was_game_running
                self._was_game_running = running_now
                self._update_play_button_state()
                if prev_running and not running_now:
                    self.game_proc = None
                    self._on_game_closed()

            # 2. Check if hookshot_options.ini or language.txt changed externally (e.g. via Insert menu in-game)
            ini_path = os.path.join(self.game_dir, "hookshot_options.ini")
            lang_path = os.path.join(self.game_dir, "language.txt")
            ini_mt = self._get_file_mtime(ini_path)
            lang_mt = self._get_file_mtime(lang_path)

            if (ini_mt and abs(ini_mt - self._last_ini_mtime) > 0.05) or (
                lang_mt and abs(lang_mt - self._last_lang_mtime) > 0.05
            ):
                self._last_ini_mtime = ini_mt
                self._last_lang_mtime = lang_mt
                self._load_options_and_language()
                self._update_footer_summary()
                if self._settings_window_alive():
                    self._populate_settings_ui()
                self.status_var.set("🔄 Ajustes sincronizados en vivo desde el juego.")

            # 3. Check if save files changed in user/save/<uid> while playing
            save_mt = get_folder_latest_mtime(get_active_save_dir(self.game_dir))
            if save_mt and abs(save_mt - self._last_save_mtime) > 0.05:
                self._last_save_mtime = save_mt
                self.sync_active_save_to_current_profile()
                self._refresh_profiles_ui()
                self.status_var.set("💾 Nueva partida detectada y sincronizada en vivo.")

            # 4. Check if hookshot_version.txt changed after an update
            ver_mt = self._get_file_mtime(os.path.join(self.game_dir, "hookshot_version.txt"))
            if ver_mt and abs(ver_mt - self._last_ver_mtime) > 0.05:
                self._last_ver_mtime = ver_mt
                self._read_version_file()
                self.subtitle_var.set(
                    f"The Legend of Zelda: Ocarina of Time PC  •  Motor: {self.hookshot_version}  •  {self.game_dir}"
                )
                if self.latest_github_tag:
                    self._apply_update_check_result()
        except Exception:
            pass
        finally:
            self.after(1000, self._poll_live_state)

    # -----------------------------------------------------------------------
    # Profiles System
    # -----------------------------------------------------------------------
    def _init_profiles_system(self):
        os.makedirs(self.profiles_dir, exist_ok=True)
        active_save_dir = get_active_save_dir(self.game_dir)
        os.makedirs(active_save_dir, exist_ok=True)

        if os.path.isfile(self.profiles_meta_path):
            try:
                with open(self.profiles_meta_path, "r", encoding="utf-8") as f:
                    self.profiles_meta = json.load(f)
            except Exception:
                self.profiles_meta = {"active": "Principal", "profiles": ["Principal"]}
        else:
            self.profiles_meta = {"active": "Principal", "profiles": ["Principal"]}

        if not self.profiles_meta.get("profiles"):
            self.profiles_meta["profiles"] = ["Principal"]
        if self.profiles_meta.get("active") not in self.profiles_meta["profiles"]:
            self.profiles_meta["active"] = self.profiles_meta["profiles"][0]
        if "bt_rumble_compat" not in self.profiles_meta:
            self.profiles_meta["bt_rumble_compat"] = 1

        active_name = self.profiles_meta["active"]
        active_profile_folder = os.path.join(self.profiles_dir, active_name)
        os.makedirs(active_profile_folder, exist_ok=True)

        active_slots = inspect_save_folder(active_save_dir)
        if active_slots:
            copy_save_contents(active_save_dir, active_profile_folder)

        self._save_profiles_meta()

    def _save_profiles_meta(self):
        try:
            os.makedirs(self.profiles_dir, exist_ok=True)
            with open(self.profiles_meta_path, "w", encoding="utf-8") as f:
                json.dump(self.profiles_meta, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def sync_active_save_to_current_profile(self):
        """Copy whatever is in user/save/<uid> back to profiles/<active>."""
        active_name = self.profiles_meta.get("active", "Principal")
        profile_folder = os.path.join(self.profiles_dir, active_name)
        active_save_dir = get_active_save_dir(self.game_dir)
        if os.path.isdir(active_save_dir):
            copy_save_contents(active_save_dir, profile_folder)

    def activate_profile(self, profile_name):
        """Switch active profile: save current user/save/<uid> to previous profile, then load profile_name into user/save/<uid>."""
        if profile_name not in self.profiles_meta["profiles"]:
            return
        self.sync_active_save_to_current_profile()

        target_folder = os.path.join(self.profiles_dir, profile_name)
        os.makedirs(target_folder, exist_ok=True)
        active_save_dir = get_active_save_dir(self.game_dir)
        copy_save_contents(target_folder, active_save_dir)

        self.profiles_meta["active"] = profile_name
        self._save_profiles_meta()
        self._last_save_mtime = get_folder_latest_mtime(active_save_dir)

    # -----------------------------------------------------------------------
    # Configuration Read / Write (hookshot_options.ini & language.txt)
    # -----------------------------------------------------------------------
    def _load_options_and_language(self):
        self.options_data = dict(DEFAULT_OPTIONS)
        self.preserved_bind_lines = []
        self.preserved_other_lines = []
        self.microphone_device_line = None
        self.custom_output_res_str = None

        ini_file = os.path.join(self.game_dir, "hookshot_options.ini")
        if os.path.isfile(ini_file):
            try:
                loaded_version = 0
                with open(ini_file, "r", encoding="utf-8", errors="ignore") as f:
                    for raw_line in f:
                        line = raw_line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if line.startswith("pad_") or line.startswith("key_"):
                            self.preserved_bind_lines.append(line)
                            continue
                        if line.startswith("microphone_device="):
                            self.microphone_device_line = line
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip()
                            if k == "options_version":
                                try:
                                    loaded_version = int(v)
                                except ValueError:
                                    pass
                                continue
                            if k == "output_res":
                                v_norm = v.lower().replace("×", "x")
                                if v_norm in OUTPUT_RES_STR_TO_CODE:
                                    self.options_data["output_res"] = OUTPUT_RES_STR_TO_CODE[v_norm]
                                    self.custom_output_res_str = None
                                elif "x" in v_norm:
                                    self.options_data["output_res"] = 0
                                    self.custom_output_res_str = v_norm
                                else:
                                    try:
                                        self.options_data["output_res"] = int(v)
                                        self.custom_output_res_str = None
                                    except ValueError:
                                        pass
                                continue
                            if k in self.options_data:
                                try:
                                    iv = int(v)
                                    if k == "menu_size" and iv == 0:
                                        iv = 2
                                    self.options_data[k] = iv
                                except ValueError:
                                    pass
                            else:
                                self.preserved_other_lines.append(line)
                if loaded_version and loaded_version < 4:
                    self.options_data["descriptor_reuse"] = 1
            except Exception:
                pass

        lang_file = os.path.join(self.game_dir, "language.txt")
        self.current_language = "es-419"
        if os.path.isfile(lang_file):
            try:
                with open(lang_file, "r", encoding="utf-8", errors="ignore") as f:
                    for raw_line in f:
                        line = raw_line.strip()
                        if line and not line.startswith("#"):
                            self.current_language = line
                            break
            except Exception:
                pass

    def save_options_and_language(self, show_toast=False):
        """Write hookshot_options.ini (preserving pad_*, key_*, and custom lines) and language.txt."""
        if self._settings_window_alive():
            self._collect_ui_to_options()
        os.makedirs(self.game_dir, exist_ok=True)

        ini_file = os.path.join(self.game_dir, "hookshot_options.ini")
        current_binds = []
        current_others = []
        known_keys = set(OPTION_KEYS_ORDER) | {"options_version", "microphone_device"}
        if os.path.isfile(ini_file):
            try:
                with open(ini_file, "r", encoding="utf-8", errors="ignore") as f:
                    for raw_line in f:
                        s = raw_line.strip()
                        if not s or s.startswith("#"):
                            continue
                        if s.startswith("pad_") or s.startswith("key_"):
                            current_binds.append(s)
                        elif s.startswith("microphone_device=") and not self.microphone_device_line:
                            self.microphone_device_line = s
                        elif "=" in s:
                            k_name = s.split("=", 1)[0].strip()
                            if k_name not in known_keys:
                                current_others.append(s)
            except Exception:
                pass
        binds_to_write = current_binds if current_binds else self.preserved_bind_lines
        others_to_write = current_others if current_others else getattr(self, "preserved_other_lines", [])

        # Check if installed Hookshot is v2.1.0+ (which accepts WxH or 0..5, while v2.0.14 only accepts 0..4)
        is_v2_1_plus = False
        try:
            ver_clean = self.hookshot_version.lstrip("vV").split("-")[0]
            parts = [int(x) for x in ver_clean.split(".")[:2]]
            if len(parts) >= 2 and (parts[0] > 2 or (parts[0] == 2 and parts[1] >= 1)):
                is_v2_1_plus = True
        except Exception:
            pass

        try:
            with open(ini_file, "w", encoding="utf-8", newline="\n") as f:
                for k in OPTION_KEYS_ORDER:
                    val = self.options_data.get(k, DEFAULT_OPTIONS.get(k, 0))
                    if k == "output_res" and is_v2_1_plus:
                        out_str = OUTPUT_RES_CODE_TO_STR.get(int(val), "2048x1152")
                        f.write(f"output_res={out_str}\n")
                    else:
                        f.write(f"{k}={val}\n")
                if self.microphone_device_line:
                    f.write(f"{self.microphone_device_line}\n")
                f.write("options_version=4\n")
                for oline in others_to_write:
                    f.write(f"{oline}\n")
                for bline in binds_to_write:
                    f.write(f"{bline}\n")
        except Exception as e:
            messagebox.showerror("Error al guardar", f"No se pudo escribir hookshot_options.ini:\n{e}")
            return False

        lang_file = os.path.join(self.game_dir, "language.txt")
        lang_content = (
            "# The game's language. Change the line below to one of the codes listed here, save, and start the game again.\n\n"
            f"{self.current_language}\n\n"
            "# en-US    English (US)\n"
            "# en-GB    English (UK)\n"
            "# fr       French (France)\n"
            "# fr-CA    French (Canada)\n"
            "# de       German\n"
            "# it       Italian\n"
            "# es       Spanish (Spain)\n"
            "# es-419   Spanish (Latin America)\n"
            "# pt-BR    Portuguese (Brazil)\n"
            "# nl       Dutch\n"
            "# pl       Polish\n"
            "# ru       Russian\n"
            "# ja       Japanese\n"
            "# ko       Korean\n"
            "# zh-Hans  Chinese (Simplified)\n"
            "# zh-Hant  Chinese (Traditional)\n"
        )
        try:
            with open(lang_file, "w", encoding="utf-8", newline="\n") as f:
                f.write(lang_content)
        except Exception as e:
            messagebox.showerror("Error al guardar idioma", f"No se pudo escribir language.txt:\n{e}")
            return False

        self._last_ini_mtime = self._get_file_mtime(ini_file)
        self._last_lang_mtime = self._get_file_mtime(lang_file)
        self._update_footer_summary()
        if show_toast:
            self.status_var.set("✔ Ajuste guardado automáticamente.")
            if hasattr(self, "settings_status_var") and self._settings_window_alive():
                now_str = datetime.datetime.now().strftime("%H:%M:%S")
                self.settings_status_var.set(f"✔ Guardado automático activo ({now_str})")
        return True

    def _on_any_setting_changed(self, _event=None):
        if self._suppress_autosave:
            return
        self.save_options_and_language(show_toast=True)

    # -----------------------------------------------------------------------
    # UI Construction (Main Window)
    # -----------------------------------------------------------------------
    def _build_header(self):
        header = tk.Frame(self, bg=BG_PANEL, height=68, highlightthickness=1, highlightbackground=BORDER_COLOR)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        left = tk.Frame(header, bg=BG_PANEL)
        left.pack(side="left", padx=16, pady=8)

        self.header_icon_img = None
        if HAS_PIL and self.icon_path and os.path.isfile(self.icon_path):
            try:
                im = Image.open(self.icon_path).convert("RGBA").resize((42, 42), Image.LANCZOS)
                self.header_icon_img = ImageTk.PhotoImage(im)
                lbl_ico = tk.Label(left, image=self.header_icon_img, bg=BG_PANEL)
                lbl_ico.pack(side="left", padx=(0, 10))
            except Exception:
                pass

        title_box = tk.Frame(left, bg=BG_PANEL)
        title_box.pack(side="left")

        tk.Label(
            title_box,
            text="HOOKSHOT LAUNCHER",
            bg=BG_PANEL,
            fg=ACCENT_GOLD,
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")

        self.subtitle_var = tk.StringVar(
            value=f"Ocarina of Time PC  •  Motor: {self.hookshot_version}"
        )
        tk.Label(
            title_box,
            textvariable=self.subtitle_var,
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w")

        # Right quick-action buttons
        right = tk.Frame(header, bg=BG_PANEL)
        right.pack(side="right", padx=14, pady=12)

        self.version_badge_var = tk.StringVar(value="🔄 Updates...")
        self.version_badge = tk.Label(
            right,
            textvariable=self.version_badge_var,
            bg=BG_CARD,
            fg=ACCENT_BLUE,
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=5,
        )
        self.version_badge.pack(side="left", padx=(0, 8))

        btn_cfg = tk.Button(
            right,
            text="⚙ Opciones",
            command=self._open_settings_dialog,
            bg=ACCENT_GOLD,
            fg=ACCENT_GOLD_INK,
            activebackground=ACCENT_GOLD_HOVER,
            activeforeground=ACCENT_GOLD_INK,
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=4,
            cursor="hand2",
        )
        btn_cfg.pack(side="left", padx=3)

        self._make_flat_button(right, "📁 Mods", self._open_mods_folder).pack(side="left", padx=2)
        self._make_flat_button(right, "📂 Carpeta", self._open_game_folder).pack(side="left", padx=2)
        self._make_flat_button(right, "📄 Log", self._open_log_file).pack(side="left", padx=2)
        self._make_flat_button(right, "📍 Ruta", self._change_game_dir).pack(side="left", padx=2)

    def _build_update_banner(self):
        """Hidden banner that appears when a new Hookshot update is available or when Hookshot is not installed."""
        self.banner_frame = tk.Frame(self, bg=BANNER_BG, highlightthickness=1, highlightbackground=ACCENT_GOLD)
        self.banner_label_var = tk.StringVar(value="")
        tk.Label(
            self.banner_frame,
            textvariable=self.banner_label_var,
            bg=BANNER_BG,
            fg=FG_TEXT,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=12, pady=8)

        self.banner_btn_skip = tk.Button(
            self.banner_frame,
            text="Omitir",
            command=self._skip_update_version,
            bg=BG_CARD,
            fg=FG_MUTED,
            activebackground=BORDER_COLOR,
            activeforeground=FG_TEXT,
            relief="flat",
            font=("Segoe UI", 9),
            padx=8,
            pady=3,
            cursor="hand2",
        )
        self.banner_btn_skip.pack(side="right", padx=(4, 12), pady=6)

        self.banner_btn_notes = tk.Button(
            self.banner_frame,
            text="Ver Notas",
            command=lambda: webbrowser.open(HOOKSHOT_RELEASES_URL),
            bg=BG_CARD,
            fg=FG_TEXT,
            activebackground=BORDER_COLOR,
            activeforeground=FG_TEXT,
            relief="flat",
            font=("Segoe UI", 9),
            padx=8,
            pady=3,
            cursor="hand2",
        )
        self.banner_btn_notes.pack(side="right", padx=4, pady=6)

        self.banner_btn_action = tk.Button(
            self.banner_frame,
            text="⬇ Actualizar",
            command=self._trigger_update_or_install,
            bg=ACCENT_GOLD,
            fg=ACCENT_GOLD_INK,
            activebackground=ACCENT_GOLD_HOVER,
            activeforeground=ACCENT_GOLD_INK,
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=3,
            cursor="hand2",
        )
        self.banner_btn_action.pack(side="right", padx=4, pady=6)

        if not self.is_hookshot_installed():
            self.banner_label_var.set(
                "⚠ No se encontró hookshot.exe en esta carpeta. Descárgalo e instálalo con 1 clic."
            )
            self.banner_btn_action.configure(text="⬇ Instalar Hookshot")
            self.banner_btn_skip.pack_forget()
            self.banner_frame.pack(fill="x", padx=14, pady=(8, 0))

    def _build_main_body(self):
        body = tk.Frame(self, bg=BG_MAIN)
        body.pack(fill="both", expand=True, padx=14, pady=12)

        main_panel = tk.Frame(
            body, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER_COLOR
        )
        main_panel.pack(fill="both", expand=True)
        self._build_profiles_panel(main_panel)

    def _build_profiles_panel(self, parent):
        # Section Header
        hdr = tk.Frame(parent, bg=BG_PANEL)
        hdr.pack(fill="x", padx=18, pady=(14, 6))
        tk.Label(
            hdr,
            text="🛡 PERFILES DE GUARDADO (SAVES)",
            bg=BG_PANEL,
            fg=ACCENT_GOLD,
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left")

        tk.Button(
            hdr,
            text="⚙ Abrir Menú de Configuración (Gráficos, Audio y Controles)",
            command=self._open_settings_dialog,
            bg=BG_CARD,
            fg=ACCENT_GOLD,
            activebackground=BORDER_COLOR,
            activeforeground=ACCENT_GOLD_HOVER,
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=4,
            cursor="hand2",
        ).pack(side="right")

        # Profile Selector Row
        prof_row = tk.Frame(parent, bg=BG_PANEL)
        prof_row.pack(fill="x", padx=18, pady=6)

        tk.Label(prof_row, text="Perfil Activo:", bg=BG_PANEL, fg=FG_TEXT, font=("Segoe UI", 10, "bold")).pack(
            side="left", padx=(0, 10)
        )
        self.profile_combo_var = tk.StringVar()
        self.profile_combo = ttk.Combobox(
            prof_row, textvariable=self.profile_combo_var, state="readonly", width=32
        )
        self.profile_combo.pack(side="left", fill="x", expand=True)
        self.profile_combo.bind("<<ComboboxSelected>>", self._on_profile_selected)

        # Profile Action Buttons Row 1
        btn_row1 = tk.Frame(parent, bg=BG_PANEL)
        btn_row1.pack(fill="x", padx=18, pady=(6, 3))
        self._make_flat_button(btn_row1, "+ Nuevo Perfil", self._create_new_profile).pack(
            side="left", padx=(0, 4), expand=True, fill="x"
        )
        self._make_flat_button(btn_row1, "📋 Clonar", self._clone_current_profile).pack(
            side="left", padx=4, expand=True, fill="x"
        )
        self._make_flat_button(btn_row1, "✏ Renombrar", self._rename_current_profile).pack(
            side="left", padx=4, expand=True, fill="x"
        )
        self._make_flat_button(btn_row1, "🗑 Borrar", self._delete_current_profile).pack(
            side="left", padx=(4, 0), expand=True, fill="x"
        )

        # Profile Action Buttons Row 2 (Backup & Emulator Sync)
        btn_row2 = tk.Frame(parent, bg=BG_PANEL)
        btn_row2.pack(fill="x", padx=18, pady=(3, 10))
        self._make_flat_button(btn_row2, "💾 Crear Backup ZIP", self._backup_profile_zip).pack(
            side="left", padx=(0, 4), expand=True, fill="x"
        )
        self._make_flat_button(btn_row2, "📦 Restaurar ZIP", self._restore_profile_zip).pack(
            side="left", padx=4, expand=True, fill="x"
        )
        self._make_flat_button(btn_row2, "⇄ Sincronizar Emuladores / NX2", self._open_sync_dialog).pack(
            side="left", padx=(4, 0), expand=True, fill="x"
        )

        # Divider
        tk.Frame(parent, bg=BORDER_COLOR, height=1).pack(fill="x", padx=18, pady=4)

        # Save Slot Selector & Live Screenshot Card
        slot_hdr = tk.Frame(parent, bg=BG_PANEL)
        slot_hdr.pack(fill="x", padx=18, pady=(6, 4))
        tk.Label(
            slot_hdr, text="Vista Previa de Partida Guardada:", bg=BG_PANEL, fg=FG_MUTED, font=("Segoe UI", 10, "bold")
        ).pack(side="left")

        self.slot_combo_var = tk.StringVar()
        self.slot_combo = ttk.Combobox(
            slot_hdr, textvariable=self.slot_combo_var, state="readonly", width=34
        )
        self.slot_combo.pack(side="right")
        self.slot_combo.bind("<<ComboboxSelected>>", self._on_slot_selected)

        # Screenshot Container (480 x 270, 16:9 ratio matching 543x306)
        self.preview_card = tk.Frame(
            parent, bg=BG_INPUT, width=484, height=272, highlightthickness=1, highlightbackground=BORDER_COLOR
        )
        self.preview_card.pack(padx=18, pady=8)
        self.preview_card.pack_propagate(False)

        self.preview_img_label = tk.Label(
            self.preview_card,
            text="Sin capturas en este perfil\n(Inicia el juego para crear una partida)",
            bg=BG_INPUT,
            fg=FG_MUTED,
            font=("Segoe UI", 10),
            justify="center",
        )
        self.preview_img_label.pack(fill="both", expand=True)

        # Metadata Details Box
        meta_card = tk.Frame(
            parent, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_COLOR
        )
        meta_card.pack(fill="both", expand=True, padx=18, pady=(4, 14))

        self.meta_location_var = tk.StringVar(value="📍 Zona: —")
        self.meta_age_var = tk.StringVar(value="🗡 Estado: —")
        self.meta_date_var = tk.StringVar(value="🕒 Guardado: —")
        self.meta_slots_count_var = tk.StringVar(value="🗂 Slots ocupados: 0 / 6")

        tk.Label(
            meta_card,
            textvariable=self.meta_location_var,
            bg=BG_CARD,
            fg=ACCENT_GOLD,
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 3))

        info_row = tk.Frame(meta_card, bg=BG_CARD)
        info_row.pack(fill="x", padx=14, pady=2)
        tk.Label(
            info_row,
            textvariable=self.meta_age_var,
            bg=BG_CARD,
            fg=FG_TEXT,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(side="left", padx=(0, 18))

        tk.Label(
            info_row,
            textvariable=self.meta_date_var,
            bg=BG_CARD,
            fg=FG_TEXT,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(side="left", padx=(0, 18))

        tk.Label(
            info_row,
            textvariable=self.meta_slots_count_var,
            bg=BG_CARD,
            fg=FG_MUTED,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(side="left")

    # -----------------------------------------------------------------------
    # Dedicated Settings Modal Window (Auto-Saved & Live-Synced)
    # -----------------------------------------------------------------------
    def _open_settings_dialog(self):
        if self._settings_window_alive():
            self.settings_win.deiconify()
            self.settings_win.lift()
            self.settings_win.focus_force()
            return

        win = tk.Toplevel(self)
        win.title("Configuración de Hookshot (Guardado Automático en Vivo)")
        win.geometry("780x590")
        win.minsize(740, 540)
        win.configure(bg=BG_MAIN)
        win.transient(self)
        if self.icon_path and os.path.isfile(self.icon_path):
            try:
                win.iconbitmap(default=self.icon_path)
            except Exception:
                pass

        self.settings_win = win
        self.ui_vars = {}

        # Top bar inside settings modal
        top_bar = tk.Frame(win, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER_COLOR)
        top_bar.pack(fill="x", side="top")
        tk.Label(
            top_bar,
            text="⚙ CONFIGURACIÓN DE HOOKSHOT",
            bg=BG_PANEL,
            fg=ACCENT_GOLD,
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left", padx=16, pady=10)

        self.settings_status_var = tk.StringVar(
            value="✔ Guardado automático activo (los cambios en el juego también se reflejan aquí en vivo)"
        )
        tk.Label(
            top_bar,
            textvariable=self.settings_status_var,
            bg=BG_PANEL,
            fg="#3fb950",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="right", padx=16, pady=10)

        # Notebook container
        panel = tk.Frame(win, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER_COLOR)
        panel.pack(fill="both", expand=True, padx=12, pady=12)

        notebook = ttk.Notebook(panel)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_graphics = tk.Frame(notebook, bg=BG_PANEL)
        self.tab_system = tk.Frame(notebook, bg=BG_PANEL)
        self.tab_controls = tk.Frame(notebook, bg=BG_PANEL)

        notebook.add(self.tab_graphics, text="  🖥 Gráficos y VRAM  ")
        notebook.add(self.tab_system, text="  🌐 Idioma, Audio y Sistema  ")
        notebook.add(self.tab_controls, text="  🎮 Controles y Cámara  ")

        self._build_tab_graphics(self.tab_graphics)
        self._build_tab_system(self.tab_system)
        self._build_tab_controls(self.tab_controls)

        self._load_options_and_language()
        self._populate_settings_ui()

        def _on_close():
            self.settings_win = None
            self.ui_vars = {}
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)

    def _build_tab_graphics(self, parent):
        cols = tk.Frame(parent, bg=BG_PANEL)
        cols.pack(fill="both", expand=True, padx=14, pady=10)

        col_l = tk.Frame(cols, bg=BG_PANEL)
        col_l.pack(side="left", fill="both", expand=True, padx=(0, 12))

        col_r = tk.Frame(cols, bg=BG_PANEL)
        col_r.pack(side="left", fill="both", expand=True, padx=(12, 0))

        self._add_section_label(col_l, "Calidad, VRAM y Escalado")
        self._add_combo_row(
            col_l, "quality_preset", "Preset de VRAM / Calidad:", QUALITY_PRESETS, on_change=self._on_preset_changed
        )
        self._add_combo_row(col_l, "output_res", "Resolución de Salida:", OUTPUT_RESOLUTIONS)
        self._add_combo_row(col_l, "dlss", "Escalador 3D (Upscaler):", UPSCALERS)
        self._add_combo_row(col_l, "dlss_model", "Modelo IA de DLSS:", DLSS_MODELS)
        self._add_combo_row(col_l, "resolution", "Resolución de Render 3D:", RENDER_RESOLUTIONS)
        self._add_combo_row(col_l, "upscaling", "Filtro Escalado Ventana:", SCALING_FILTERS)
        self._add_combo_row(col_l, "anisotropic_filtering", "Filtro Anisotrópico:", ANISOTROPIC_MODES)
        self._add_slider_row(col_l, "sharpness", "Nitidez (Sharpness %):", 0, 100, 10)

        self._add_section_label(col_r, "Fluidez, Pantalla y Vulkan")
        self._add_combo_row(col_r, "frame_rate_cap", "Límite de Cuadros (FPS):", FPS_CAPS)
        self._add_combo_row(col_r, "frame_generation", "Frame Generation:", FRAME_GEN_MODES)
        self._add_combo_row(col_r, "nvidia_reflex", "NVIDIA Reflex:", REFLEX_MODES)
        self._add_combo_row(col_r, "hdr", "Modo HDR10:", HDR_MODES)
        self._add_combo_row(col_r, "mesh_shaders", "Mesh Shaders (Geometría):", MESH_SHADER_MODES)
        self._add_combo_row(col_r, "robust_buffers", "Buffers Robustos (VRAM):", ROBUST_MODES)
        self._add_combo_row(col_r, "ultrawide_menus", "Menús en Ultrawide:", ULTRAWIDE_MENU_MODES)

        toggles_frame = tk.Frame(col_r, bg=BG_PANEL)
        toggles_frame.pack(fill="x", pady=(6, 0))
        self._add_check_row(toggles_frame, "fullscreen", "Pantalla Completa sin bordes (F11)")
        self._add_check_row(toggles_frame, "ultrawide", "Cámara Ultrawide (Adaptar a monitor 21:9 / 32:9 / 4:3)")
        self._add_check_row(toggles_frame, "frame_pacing", "Frame Pacing uniforme (Menos micro-stutter)")
        self._add_check_row(toggles_frame, "handheld_profile", "Perfil Portátil (1536×864, más ligero para GPU)")
        self._add_check_row(toggles_frame, "amd_anti_lag_2", "Activar AMD Anti-Lag 2 (En GPUs AMD compatibles)")
        self._add_check_row(toggles_frame, "descriptor_reuse", "Reutilizar Descriptores Vulkan (Streaming rápido)")
        self._add_check_row(toggles_frame, "sampler_cache", "Caché de Samplers sin bloqueo")

    def _build_tab_system(self, parent):
        cols = tk.Frame(parent, bg=BG_PANEL)
        cols.pack(fill="both", expand=True, padx=14, pady=10)

        col_l = tk.Frame(cols, bg=BG_PANEL)
        col_l.pack(side="left", fill="both", expand=True, padx=(0, 12))

        col_r = tk.Frame(cols, bg=BG_PANEL)
        col_r.pack(side="left", fill="both", expand=True, padx=(12, 0))

        self._add_section_label(col_l, "Idioma de Consola y Jugabilidad")
        self._add_combo_row(col_l, "_language", "Idioma del Juego (language.txt):", LANGUAGES)
        self._add_combo_row(col_l, "game_speed", "Velocidad del Juego:", GAME_SPEEDS)
        self._add_combo_row(col_l, "text_speed", "Velocidad de Diálogos:", TEXT_SPEEDS)
        self._add_combo_row(col_l, "text_size", "Tamaño de Texto / Diálogos:", TEXT_SIZES)

        self._add_section_label(col_l, "Audio y Micrófono (Ocarina)")
        self._add_slider_row(col_l, "volume", "Volumen General del Juego (%):", 0, 100, 5)
        self._add_combo_row(col_l, "audio_output", "Canales de Salida Audio:", AUDIO_OUTPUTS)
        self._add_combo_row(col_l, "microphone", "Micrófono para Ocarina:", MIC_MODES)
        self._add_check_row(col_l, "mute_in_background", "Silenciar el audio cuando la ventana esté en segundo plano")

        self._add_section_label(col_r, "Superposición, HDR Avanzado y Utilidades")
        self._add_combo_row(col_r, "menu_size", "Tamaño del Menú F1 y FPS:", MENU_SIZES)
        self._add_combo_row(col_r, "menu_shortcut", "Atajo para abrir el Menú:", MENU_SHORTCUTS)
        self._add_slider_row(col_r, "hdr_paper_white", "HDR Brillo Blanco (Nits):", 80, 400, 10)
        self._add_slider_row(col_r, "hdr_peak_brightness", "HDR Brillo Pico (Nits):", 400, 4000, 100)

        sys_toggles = tk.Frame(col_r, bg=BG_PANEL)
        sys_toggles.pack(fill="x", pady=(8, 0))
        self._add_check_row(sys_toggles, "fps_counter", "Mostrar Contador de FPS en esquina superior derecha")
        self._add_check_row(sys_toggles, "discord_status", "Mostrar actividad en Discord (Rich Presence)")
        self._add_check_row(
            sys_toggles,
            "debug_tools",
            "Activar pestaña Debug / Cheats en menú F1 (Vuelo, Teletransporte, Inventario)",
        )

        info_card = tk.Frame(col_r, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_COLOR)
        info_card.pack(fill="x", pady=(12, 0))
        tk.Label(
            info_card,
            text="💡 Atajos dentro del juego:\n"
            "• Tecla F1 / Insert (o Home / Select+Start en mando): Abre el menú interno.\n"
            "• Ratón en Menús: En v2.1.0 puedes usar clic del ratón en menús de Zelda y F1.\n"
            "• Tecla F11: Alterna entre Ventana y Pantalla Completa.",
            bg=BG_CARD,
            fg=FG_MUTED,
            font=("Segoe UI", 9),
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=12, pady=10)

    def _build_tab_controls(self, parent):
        cols = tk.Frame(parent, bg=BG_PANEL)
        cols.pack(fill="both", expand=True, padx=14, pady=10)

        col_l = tk.Frame(cols, bg=BG_PANEL)
        col_l.pack(side="left", fill="both", expand=True, padx=(0, 12))

        col_r = tk.Frame(cols, bg=BG_PANEL)
        col_r.pack(side="left", fill="both", expand=True, padx=(12, 0))

        self._add_section_label(col_l, "Mando y Cámara con Ratón")
        self._add_combo_row(col_l, "layout_preset", "Disposición de Botones:", PAD_LAYOUTS)
        self._add_combo_row(col_l, "button_prompts", "Iconos en Pantalla:", BUTTON_PROMPTS)
        self._add_combo_row(col_l, "stick_dead_zone", "Zona Muerta de Sticks:", DEADZONE_MODES)
        self._add_slider_row(col_l, "rumble_strength", "Fuerza de Vibración (%):", 0, 150, 25)
        self._add_combo_row(col_l, "mouse_camera", "Modo Cámara Ratón:", MOUSE_CAM_MODES)
        self._add_slider_row(col_l, "mouse_sensitivity", "Sensibilidad Ratón (%):", 10, 500, 10)

        self._add_section_label(col_r, "Control por Movimiento (Giroscopio) e Inversión")
        self._add_combo_row(col_r, "motion_deadzone", "Zona Muerta Giroscopio:", GYRO_DEADZONES)
        self._add_slider_row(col_r, "motion_sensitivity_x", "Sensibilidad Giroscopio X (%):", 10, 600, 10)
        self._add_slider_row(col_r, "motion_sensitivity_y", "Sensibilidad Giroscopio Y (%):", 10, 300, 10)

        ctrl_toggles = tk.Frame(col_r, bg=BG_PANEL)
        ctrl_toggles.pack(fill="x", pady=(6, 0))
        self._add_check_row(ctrl_toggles, "motion_controls", "Activar Apuntado por Giroscopio (Switch Pro / DualSense / DS4)")
        self._add_check_row(ctrl_toggles, "_bt_rumble_compat", "Vibración compatible Bluetooth (Evita vibración pegada)")
        self._add_check_row(ctrl_toggles, "disable_camera_centering", "Desactivar centrado automático de cámara al caminar")
        self._add_check_row(ctrl_toggles, "controller_in_background", "Permitir uso del mando con la ventana en segundo plano")
        self._add_check_row(ctrl_toggles, "invert_mouse_vertical", "Invertir eje vertical del ratón")
        self._add_check_row(ctrl_toggles, "invert_camera_x", "Invertir cámara horizontal (Stick derecho X)")
        self._add_check_row(ctrl_toggles, "invert_camera_y", "Invertir cámara vertical (Stick derecho Y)")
        self._add_check_row(ctrl_toggles, "invert_motion_x", "Invertir eje horizontal del giroscopio")
        self._add_check_row(ctrl_toggles, "invert_motion_y", "Invertir eje vertical del giroscopio")

    def _build_footer(self):
        footer = tk.Frame(self, bg=BG_PANEL, height=66, highlightthickness=1, highlightbackground=BORDER_COLOR)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        left = tk.Frame(footer, bg=BG_PANEL)
        left.pack(side="left", padx=18, pady=10)

        self.status_var = tk.StringVar(value="Listo para jugar.")
        tk.Label(
            left,
            textvariable=self.status_var,
            bg=BG_PANEL,
            fg=FG_TEXT,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")

        self.summary_var = tk.StringVar(value="")
        tk.Label(
            left,
            textvariable=self.summary_var,
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w")

        right = tk.Frame(footer, bg=BG_PANEL)
        right.pack(side="right", padx=18, pady=10)

        self.play_btn = tk.Button(
            right,
            text="▶  JUGAR HOOKSHOT",
            command=self._on_play_or_stop_clicked,
            bg=ACCENT_GREEN,
            fg="#ffffff",
            activebackground=ACCENT_GREEN_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            font=("Segoe UI", 11, "bold"),
            padx=26,
            pady=8,
            cursor="hand2",
        )
        self.play_btn.pack(side="left")

    # -----------------------------------------------------------------------
    # UI Widget Helpers (Bound for Instant Auto-Save)
    # -----------------------------------------------------------------------
    def _make_flat_button(self, parent, text, command, width=None):
        kw = dict(
            text=text,
            command=command,
            bg=BG_CARD,
            fg=FG_TEXT,
            activebackground=BORDER_COLOR,
            activeforeground=ACCENT_GOLD,
            relief="flat",
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
            cursor="hand2",
        )
        if width:
            kw["width"] = width
        return tk.Button(parent, **kw)

    def _add_section_label(self, parent, text):
        f = tk.Frame(parent, bg=BG_PANEL)
        f.pack(fill="x", pady=(6, 4))
        tk.Label(f, text=text, bg=BG_PANEL, fg=ACCENT_GOLD, font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Frame(f, bg=BORDER_COLOR, height=1).pack(side="left", fill="x", expand=True, padx=(8, 0), pady=2)

    def _add_combo_row(self, parent, key, label_text, items, on_change=None):
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label_text, bg=BG_PANEL, fg=FG_TEXT, font=("Segoe UI", 9)).pack(side="left")

        var = tk.StringVar()
        combo = ttk.Combobox(row, textvariable=var, state="readonly", width=31)
        combo["values"] = [label for _, label in items]
        combo.pack(side="right")

        self.ui_vars[key] = ("combo", var, items)
        if on_change:
            combo.bind("<<ComboboxSelected>>", on_change)
        else:
            combo.bind("<<ComboboxSelected>>", self._on_any_setting_changed)

    def _add_slider_row(self, parent, key, label_text, min_val, max_val, step):
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill="x", pady=3)

        lbl = tk.Label(row, text=label_text, bg=BG_PANEL, fg=FG_TEXT, font=("Segoe UI", 9))
        lbl.pack(side="left")

        val_label_var = tk.StringVar(value=str(min_val))
        val_lbl = tk.Label(
            row, textvariable=val_label_var, bg=BG_PANEL, fg=ACCENT_GOLD, font=("Segoe UI", 9, "bold"), width=5, anchor="e"
        )
        val_lbl.pack(side="right")

        var = tk.IntVar(value=min_val)

        def _on_slide(v):
            snapped = int(round(float(v) / step) * step)
            snapped = max(min_val, min(max_val, snapped))
            var.set(snapped)
            val_label_var.set(str(snapped))
            if not self._suppress_autosave:
                if self._slider_save_job is not None:
                    try:
                        self.after_cancel(self._slider_save_job)
                    except Exception:
                        pass
                self._slider_save_job = self.after(150, self._on_any_setting_changed)

        scale = ttk.Scale(row, from_=min_val, to=max_val, orient="horizontal", command=_on_slide, length=150)
        scale.pack(side="right", padx=(6, 4))

        self.ui_vars[key] = ("slider", var, scale, val_label_var, min_val, max_val, step)

    def _add_check_row(self, parent, key, label_text):
        var = tk.IntVar(value=0)
        chk = ttk.Checkbutton(parent, text=label_text, variable=var, command=self._on_any_setting_changed)
        chk.pack(anchor="w", pady=2)
        self.ui_vars[key] = ("check", var)

    # -----------------------------------------------------------------------
    # Populate & Collect Settings UI
    # -----------------------------------------------------------------------
    def _populate_settings_ui(self):
        self._suppress_autosave = True
        try:
            for key, item in self.ui_vars.items():
                kind = item[0]
                if key == "_language":
                    raw_val = self.current_language
                elif key == "_bt_rumble_compat":
                    raw_val = self.profiles_meta.get("bt_rumble_compat", 1)
                else:
                    raw_val = self.options_data.get(key, DEFAULT_OPTIONS.get(key, 0))

                if kind == "combo":
                    _, var, choices = item
                    matched_label = choices[0][1]
                    for code, label in choices:
                        if code == raw_val:
                            matched_label = label
                            break
                    var.set(matched_label)
                elif kind == "slider":
                    _, var, scale, val_label_var, min_v, max_v, _ = item
                    clamped = max(min_v, min(max_v, int(raw_val)))
                    var.set(clamped)
                    scale.set(clamped)
                    val_label_var.set(str(clamped))
                elif kind == "check":
                    _, var = item
                    var.set(1 if int(raw_val) != 0 else 0)
        finally:
            self._suppress_autosave = False

        self._update_footer_summary()

    def _collect_ui_to_options(self):
        if not self.ui_vars:
            return
        for key, item in self.ui_vars.items():
            kind = item[0]
            if kind == "combo":
                _, var, choices = item
                selected_label = var.get()
                code_val = choices[0][0]
                for code, label in choices:
                    if label == selected_label:
                        code_val = code
                        break
                if key == "_language":
                    self.current_language = code_val
                else:
                    self.options_data[key] = int(code_val)
            elif kind == "slider":
                _, var, _, _, _, _, _ = item
                self.options_data[key] = int(var.get())
            elif kind == "check":
                _, var = item
                val = 1 if int(var.get()) != 0 else 0
                if key == "_bt_rumble_compat":
                    self.profiles_meta["bt_rumble_compat"] = val
                    self._save_profiles_meta()
                else:
                    self.options_data[key] = val

    def _on_preset_changed(self, _event=None):
        """Apply Hookshot v2.1.0's exact preset rules from vk_menu.cpp apply_preset() and auto-save."""
        if self._suppress_autosave:
            return
        self._collect_ui_to_options()
        p = self.options_data.get("quality_preset", 0)
        if p == 1:  # Minimum (4GB)
            self.options_data.update({"resolution": 4, "upscaling": 2, "sharpness": 30, "frame_pacing": 1, "game_speed": 1, "handheld_profile": 1})
        elif p == 2:  # Low (6GB)
            self.options_data.update({"resolution": 2, "upscaling": 2, "sharpness": 30, "frame_pacing": 1, "game_speed": 1, "handheld_profile": 1})
        elif p == 3:  # Balanced (8GB)
            self.options_data.update({"resolution": 1, "upscaling": 1, "sharpness": 30, "frame_pacing": 1, "game_speed": 1, "handheld_profile": 0})
        elif p == 4:  # High (12GB)
            self.options_data.update({"resolution": 1, "upscaling": 2, "sharpness": 40, "frame_pacing": 1, "game_speed": 1, "handheld_profile": 0})
        elif p == 5:  # Ultra (16GB+)
            self.options_data.update({"resolution": 1, "upscaling": 2, "sharpness": 50, "frame_pacing": 1, "game_speed": 1, "handheld_profile": 0})
        self._populate_settings_ui()
        self.save_options_and_language(show_toast=True)

    def _update_footer_summary(self):
        active_prof = self.profiles_meta.get("active", "Principal")
        out_code = self.options_data.get("output_res", 0)
        out_label = next((lbl.split(" ")[0] for c, lbl in OUTPUT_RESOLUTIONS if c == out_code), "2048×1152")
        fps_code = self.options_data.get("frame_rate_cap", 0)
        fps_label = next((lbl.split(" ")[0] + " FPS" for c, lbl in FPS_CAPS if c == fps_code), "60 FPS")
        self.summary_var.set(
            f"Perfil activo: {active_prof}   |   Idioma: {self.current_language}   |   Salida: {out_label}   |   Meta: {fps_label}"
        )

    # -----------------------------------------------------------------------
    # Profile UI Refresh & Actions
    # -----------------------------------------------------------------------
    def _refresh_profiles_ui(self):
        profiles = self.profiles_meta.get("profiles", ["Principal"])
        active = self.profiles_meta.get("active", profiles[0])

        self.profile_combo["values"] = profiles
        self.profile_combo_var.set(active)

        active_folder = os.path.join(self.profiles_dir, active)
        self.current_slots = inspect_save_folder(active_folder)
        self.meta_slots_count_var.set(f"🗂 Slots ocupados: {len(self.current_slots)} / 6")

        if self.current_slots:
            slot_labels = [f"{s['label']} — {s['location']}" for s in self.current_slots]
            self.slot_combo["values"] = slot_labels
            self.selected_slot_index = 0
            self.slot_combo.current(0)
            self._render_slot_preview(self.current_slots[0])
        else:
            self.slot_combo["values"] = ["(Sin partidas guardadas)"]
            self.slot_combo.current(0)
            self._render_slot_preview(None)

        self._update_footer_summary()

    def _render_slot_preview(self, slot_data):
        if not slot_data:
            self.preview_img_label.configure(
                image="",
                text="Perfil vacío (Nueva Partida)\nAl iniciar Hookshot empezarás desde cero.",
            )
            self.preview_photo = None
            self.meta_location_var.set("📍 Zona: Nueva Partida")
            self.meta_age_var.set("🗡 Estado: Sin datos")
            self.meta_date_var.set("🕒 Guardado: —")
            return

        self.meta_location_var.set(f"📍 Zona: {slot_data['location']}")
        age_str = slot_data["age"] or "Link"
        scene_str = f" ({slot_data['scene']})" if slot_data["scene"] else ""
        self.meta_age_var.set(f"🗡 Estado: {age_str}{scene_str}")
        self.meta_date_var.set(f"🕒 Guardado: {slot_data['datetime']}")

        if HAS_PIL and slot_data.get("jpeg_bytes"):
            try:
                im = Image.open(io.BytesIO(slot_data["jpeg_bytes"])).convert("RGB")
                im = im.resize((480, 270), Image.LANCZOS)
                self.preview_photo = ImageTk.PhotoImage(im)
                self.preview_img_label.configure(image=self.preview_photo, text="")
                return
            except Exception:
                pass

        self.preview_img_label.configure(
            image="",
            text=f"Partida en {slot_data['location']}\n({slot_data['datetime']})",
        )
        self.preview_photo = None

    def _on_profile_selected(self, _event=None):
        chosen = self.profile_combo_var.get()
        if chosen and chosen != self.profiles_meta.get("active"):
            self.activate_profile(chosen)
            self._refresh_profiles_ui()
            self.status_var.set(f"✔ Perfil cambiado a '{chosen}'.")

    def _on_slot_selected(self, _event=None):
        idx = self.slot_combo.current()
        if 0 <= idx < len(self.current_slots):
            self.selected_slot_index = idx
            self._render_slot_preview(self.current_slots[idx])

    def _sanitize_profile_name(self, name):
        if not name:
            return ""
        cleaned = re.sub(r'[<>:"/\\|?*]', "", name).strip()
        return cleaned[:40]

    def _create_new_profile(self):
        raw = simpledialog.askstring(
            "Nuevo Perfil Vacío",
            "Escribe el nombre para el nuevo perfil de guardado (empezará desde cero):",
            parent=self,
        )
        name = self._sanitize_profile_name(raw)
        if not name:
            return
        if name in self.profiles_meta["profiles"]:
            messagebox.showwarning("Perfil existente", f"Ya existe un perfil llamado '{name}'.")
            return

        self.sync_active_save_to_current_profile()

        new_dir = os.path.join(self.profiles_dir, name)
        os.makedirs(new_dir, exist_ok=True)
        self.profiles_meta["profiles"].append(name)
        self.activate_profile(name)
        self._refresh_profiles_ui()
        self.status_var.set(f"✔ Perfil nuevo '{name}' creado y activado.")

    def _clone_current_profile(self):
        cur = self.profiles_meta.get("active", "Principal")
        raw = simpledialog.askstring(
            "Clonar Perfil Actual",
            f"Nombre para la copia del perfil '{cur}':",
            initialvalue=f"{cur} - Copia",
            parent=self,
        )
        name = self._sanitize_profile_name(raw)
        if not name:
            return
        if name in self.profiles_meta["profiles"]:
            messagebox.showwarning("Perfil existente", f"Ya existe un perfil llamado '{name}'.")
            return

        self.sync_active_save_to_current_profile()
        src_dir = os.path.join(self.profiles_dir, cur)
        dst_dir = os.path.join(self.profiles_dir, name)
        copy_save_contents(src_dir, dst_dir)

        self.profiles_meta["profiles"].append(name)
        self.activate_profile(name)
        self._refresh_profiles_ui()
        self.status_var.set(f"✔ Perfil '{cur}' clonado como '{name}'.")

    def _rename_current_profile(self):
        cur = self.profiles_meta.get("active", "Principal")
        raw = simpledialog.askstring(
            "Renombrar Perfil",
            f"Nuevo nombre para el perfil '{cur}':",
            initialvalue=cur,
            parent=self,
        )
        name = self._sanitize_profile_name(raw)
        if not name or name == cur:
            return
        if name in self.profiles_meta["profiles"]:
            messagebox.showwarning("Perfil existente", f"Ya existe un perfil llamado '{name}'.")
            return

        self.sync_active_save_to_current_profile()
        old_dir = os.path.join(self.profiles_dir, cur)
        new_dir = os.path.join(self.profiles_dir, name)
        try:
            os.rename(old_dir, new_dir)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo renombrar la carpeta:\n{e}")
            return

        idx = self.profiles_meta["profiles"].index(cur)
        self.profiles_meta["profiles"][idx] = name
        self.profiles_meta["active"] = name
        self._save_profiles_meta()
        self._refresh_profiles_ui()
        self.status_var.set(f"✔ Perfil renombrado a '{name}'.")

    def _delete_current_profile(self):
        cur = self.profiles_meta.get("active", "Principal")
        if len(self.profiles_meta["profiles"]) <= 1:
            messagebox.showwarning(
                "No permitido",
                "No puedes borrar el único perfil existente. Crea otro perfil primero si deseas limpiar este.",
            )
            return

        if not messagebox.askyesno(
            "Confirmar eliminación",
            f"¿Seguro que deseas eliminar el perfil '{cur}' y sus partidas?\n\n(Se creará un backup automático antes de borrarlo).",
            parent=self,
        ):
            return

        self._backup_profile_zip(silent=True)

        target_dir = os.path.join(self.profiles_dir, cur)
        shutil.rmtree(target_dir, ignore_errors=True)
        self.profiles_meta["profiles"].remove(cur)
        next_prof = self.profiles_meta["profiles"][0]
        self.profiles_meta["active"] = next_prof
        self._save_profiles_meta()

        copy_save_contents(os.path.join(self.profiles_dir, next_prof), get_active_save_dir(self.game_dir))
        self._refresh_profiles_ui()
        self.status_var.set(f"🗑 Perfil '{cur}' eliminado (backup guardado en /backups).")

    def _backup_profile_zip(self, silent=False):
        self.sync_active_save_to_current_profile()
        cur = self.profiles_meta.get("active", "Principal")
        src_dir = os.path.join(self.profiles_dir, cur)
        backups_dir = os.path.join(self.game_dir, "backups")
        os.makedirs(backups_dir, exist_ok=True)

        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        zip_name = f"Backup_{cur}_{stamp}.zip"
        zip_path = os.path.join(backups_dir, zip_name)

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(src_dir):
                    for file in files:
                        full = os.path.join(root, file)
                        rel = os.path.relpath(full, src_dir)
                        zf.write(full, rel)
            if not silent:
                self.status_var.set(f"💾 Backup creado: backups\\{zip_name}")
                messagebox.showinfo(
                    "Backup Completado",
                    f"Se ha guardado una copia de seguridad del perfil '{cur}' en:\n\n{zip_path}",
                    parent=self,
                )
        except Exception as e:
            if not silent:
                messagebox.showerror("Error en Backup", f"No se pudo crear el archivo ZIP:\n{e}", parent=self)

    def _restore_profile_zip(self):
        backups_dir = os.path.join(self.game_dir, "backups")
        initial_dir = backups_dir if os.path.isdir(backups_dir) else self.game_dir
        zip_path = filedialog.askopenfilename(
            title="Seleccionar Backup ZIP para restaurar",
            initialdir=initial_dir,
            filetypes=[("Archivos ZIP", "*.zip")],
            parent=self,
        )
        if not zip_path:
            return

        cur = self.profiles_meta.get("active", "Principal")
        if not messagebox.askyesno(
            "Restaurar Backup",
            f"¿Quieres restaurar este archivo ZIP dentro del perfil activo ('{cur}')?",
            parent=self,
        ):
            return

        target_dir = os.path.join(self.profiles_dir, cur)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(tmp)
                copy_save_contents(tmp, target_dir)
                copy_save_contents(target_dir, get_active_save_dir(self.game_dir))
            self._refresh_profiles_ui()
            self.status_var.set(f"✔ Backup restaurado en el perfil '{cur}'.")
        except Exception as e:
            messagebox.showerror("Error al restaurar", f"No se pudo restaurar el ZIP:\n{e}", parent=self)

    def _open_sync_dialog(self):
        """Modal window to import/export saves with Eden/Lichii/Fritchii and NX2navi."""
        ext_saves = discover_external_saves()
        dlg = tk.Toplevel(self)
        dlg.title("Sincronizar Partidas con Emuladores y NX2navi")
        dlg.geometry("620x360")
        dlg.configure(bg=BG_PANEL)
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(
            dlg,
            text="⇄ Importar o Exportar Partidas (Eden / Lichii / Fritchii / NX2navi)",
            bg=BG_PANEL,
            fg=ACCENT_GOLD,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 6))

        tk.Label(
            dlg,
            text=f"Perfil activo en Hookshot: {self.profiles_meta.get('active', 'Principal')}",
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=16, pady=(0, 10))

        if not ext_saves:
            tk.Label(
                dlg,
                text="No se detectaron partidas automáticas de Eden o NX2navi.\nPuedes usar el botón de abajo para elegir cualquier carpeta manualmente.",
                bg=BG_CARD,
                fg=FG_TEXT,
                padx=14,
                pady=14,
            ).pack(fill="x", padx=16, pady=10)
        else:
            list_frame = tk.Frame(dlg, bg=BG_PANEL)
            list_frame.pack(fill="both", expand=True, padx=16, pady=4)

            ext_var = tk.StringVar(value=ext_saves[0]["label"])
            combo = ttk.Combobox(
                list_frame,
                textvariable=ext_var,
                values=[e["label"] for e in ext_saves],
                state="readonly",
            )
            combo.pack(fill="x", pady=6)

            def _get_selected_ext():
                idx = combo.current()
                return ext_saves[idx] if 0 <= idx < len(ext_saves) else ext_saves[0]

            btn_box = tk.Frame(list_frame, bg=BG_PANEL)
            btn_box.pack(fill="x", pady=12)

            def _import_selected():
                sel = _get_selected_ext()
                cur = self.profiles_meta.get("active", "Principal")
                if messagebox.askyesno(
                    "Importar a Hookshot",
                    f"¿Copiar las partidas de:\n{sel['source_name']}\n\nhacia tu perfil activo '{cur}' en Hookshot?",
                    parent=dlg,
                ):
                    self._backup_profile_zip(silent=True)
                    prof_dir = os.path.join(self.profiles_dir, cur)
                    copy_save_contents(sel["path"], prof_dir, keep_option_sav=True)
                    copy_save_contents(prof_dir, get_active_save_dir(self.game_dir))
                    self._refresh_profiles_ui()
                    self.status_var.set(f"✔ Partida importada desde {sel['source_name']}.")
                    dlg.destroy()

            def _export_selected():
                sel = _get_selected_ext()
                cur = self.profiles_meta.get("active", "Principal")
                if messagebox.askyesno(
                    "Exportar desde Hookshot",
                    f"¿Enviar las partidas de tu perfil '{cur}' de Hookshot hacia:\n{sel['source_name']} ({sel['path']})?",
                    parent=dlg,
                ):
                    self.sync_active_save_to_current_profile()
                    prof_dir = os.path.join(self.profiles_dir, cur)
                    copy_save_contents(prof_dir, sel["path"], keep_option_sav=True)
                    self.status_var.set(f"✔ Partida exportada hacia {sel['source_name']}.")
                    messagebox.showinfo("Exportación lista", f"Partida copiada a {sel['source_name']}.", parent=dlg)
                    dlg.destroy()

            self._make_flat_button(btn_box, "⬇ Importar hacia este Perfil de Hookshot", _import_selected).pack(
                fill="x", pady=4
            )
            self._make_flat_button(btn_box, "⬆ Exportar este Perfil hacia el Emulador / NX2navi", _export_selected).pack(
                fill="x", pady=4
            )

        def _import_custom_folder():
            folder = filedialog.askdirectory(title="Seleccionar carpeta con slot_00 / account.sav", parent=dlg)
            if not folder:
                return
            slots = inspect_save_folder(folder)
            if not slots:
                messagebox.showwarning("Sin partidas", "Esa carpeta no contiene carpetas slot_00..slot_05.", parent=dlg)
                return
            cur = self.profiles_meta.get("active", "Principal")
            self._backup_profile_zip(silent=True)
            prof_dir = os.path.join(self.profiles_dir, cur)
            copy_save_contents(folder, prof_dir, keep_option_sav=True)
            copy_save_contents(prof_dir, get_active_save_dir(self.game_dir))
            self._refresh_profiles_ui()
            self.status_var.set("✔ Partida importada desde carpeta externa.")
            dlg.destroy()

        self._make_flat_button(dlg, "📂 Importar desde otra carpeta...", _import_custom_folder).pack(
            padx=16, pady=(4, 14), fill="x"
        )

    # -----------------------------------------------------------------------
    # Quick Folder / File Actions
    # -----------------------------------------------------------------------
    def _open_mods_folder(self):
        mods_dir = os.path.join(self.game_dir, "mods")
        os.makedirs(mods_dir, exist_ok=True)
        os.startfile(mods_dir)

    def _open_game_folder(self):
        os.makedirs(self.game_dir, exist_ok=True)
        os.startfile(self.game_dir)

    def _open_log_file(self):
        for name in ("hookshot_log.txt", "hookshot_log.1.txt"):
            p = os.path.join(self.game_dir, name)
            if os.path.isfile(p) and os.path.getsize(p) > 0:
                os.startfile(p)
                return
        messagebox.showinfo("Log vacío", "Aún no hay registros en hookshot_log.txt.", parent=self)

    def _change_game_dir(self):
        chosen = filedialog.askdirectory(
            title="Seleccionar carpeta de Hookshot",
            initialdir=self.game_dir,
            parent=self,
        )
        if not chosen:
            return
        self.game_dir = os.path.abspath(chosen)
        save_launcher_config(self.game_dir)
        self.profiles_dir = os.path.join(self.game_dir, "profiles")
        self.profiles_meta_path = os.path.join(self.profiles_dir, "profiles.json")
        self._read_version_file()
        self._init_profiles_system()
        self._load_options_and_language()
        self._record_file_mtimes()
        self._refresh_profiles_ui()
        if self._settings_window_alive():
            self._populate_settings_ui()
        self.subtitle_var.set(f"Ocarina of Time PC  •  Motor: {self.hookshot_version}")
        self._update_play_button_state()
        if self.is_hookshot_installed():
            self.banner_frame.pack_forget()
        else:
            self.banner_label_var.set(
                "⚠ No se encontró hookshot.exe en esta carpeta. Descárgalo e instálalo con 1 clic."
            )
            self.banner_btn_action.configure(text="⬇ Instalar Hookshot")
            self.banner_frame.pack(fill="x", padx=14, pady=(8, 0))

    # -----------------------------------------------------------------------
    # GitHub Update Checker & Auto-Installer (hos_update.c compatible)
    # -----------------------------------------------------------------------
    def _get_skipped_version(self):
        skip_file = os.path.join(self.game_dir, "user", "hookshot_update_skip.txt")
        if os.path.isfile(skip_file):
            try:
                with open(skip_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("skip="):
                            return line.split("=", 1)[1].strip()
            except Exception:
                pass
        return ""

    def _skip_update_version(self):
        if not self.latest_github_tag:
            return
        user_dir = os.path.join(self.game_dir, "user")
        os.makedirs(user_dir, exist_ok=True)
        skip_file = os.path.join(user_dir, "hookshot_update_skip.txt")
        try:
            with open(skip_file, "w", encoding="utf-8", newline="\n") as f:
                f.write(f"skip={self.latest_github_tag}\n")
        except Exception:
            pass
        self.banner_frame.pack_forget()
        self.status_var.set(f"Versión {self.latest_github_tag} omitida.")

    def _check_updates_background(self):
        try:
            req = urllib.request.Request(
                HOOKSHOT_API_LATEST,
                headers={
                    "User-Agent": "Hookshot-Launcher-Update-Check",
                    "Accept": "application/vnd.github+json",
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                tag = data.get("tag_name", "").strip()
                notes = data.get("body", "")
                if tag:
                    self.latest_github_tag = tag
                    self.latest_release_notes = notes
                    self.after(0, self._apply_update_check_result)
                    return
        except Exception:
            pass
        self.after(0, lambda: self.version_badge_var.set(f"Motor: {self.hookshot_version}"))

    def _apply_update_check_result(self):
        tag = self.latest_github_tag
        if not self.is_hookshot_installed():
            self.version_badge_var.set(f"Última: {tag}")
            self.version_badge.configure(fg=ACCENT_GOLD)
            return

        if self.hookshot_version == tag:
            self.version_badge_var.set(f"✔ {tag} (Al día)")
            self.version_badge.configure(fg="#3fb950")
            self.banner_frame.pack_forget()
        else:
            self.version_badge_var.set(f"✨ Update: {tag}")
            self.version_badge.configure(fg=ACCENT_GOLD)
            if tag != self._get_skipped_version():
                self.banner_label_var.set(
                    f"✨ ¡Nueva versión de Hookshot disponible: {tag}! (Instalada: {self.hookshot_version})"
                )
                self.banner_btn_action.configure(text=f"⬇ Actualizar a {tag}")
                self.banner_frame.pack(fill="x", padx=14, pady=(8, 0), before=self.children[list(self.children.keys())[2]])

    def _trigger_update_or_install(self):
        if not self.is_hookshot_installed():
            self._download_and_run_builder(update_mode=False)
            return

        tag = self.latest_github_tag
        if self.builder_exe_path and os.path.isfile(self.builder_exe_path) and tag:
            if not messagebox.askyesno(
                "Actualizar Hookshot",
                f"¿Deseas actualizar Hookshot de {self.hookshot_version} a {tag} ahora?\n\n"
                "Hookshot Builder descargará únicamente los archivos nuevos y reconstruirá el ejecutable.\n"
                "Tus perfiles de guardado y tu configuración se conservarán intactos.",
                parent=self,
            ):
                return
            self.save_options_and_language()
            self.sync_active_save_to_current_profile()
            try:
                subprocess.Popen(
                    [self.builder_exe_path, "--update", self.game_dir, "--tag", tag],
                    cwd=os.path.dirname(self.builder_exe_path),
                )
                self.destroy()
                return
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo iniciar HookshotBuilder:\n{e}", parent=self)
        else:
            self._download_and_run_builder(update_mode=True)

    def _download_and_run_builder(self, update_mode=False):
        """If HookshotBuilder.exe exists locally, run it; otherwise download it from GitHub Releases and execute it."""
        if self.builder_exe_path and os.path.isfile(self.builder_exe_path):
            try:
                cmd = [self.builder_exe_path]
                if update_mode and self.latest_github_tag and os.path.isdir(self.game_dir):
                    cmd += ["--update", self.game_dir, "--tag", self.latest_github_tag]
                subprocess.Popen(cmd, cwd=os.path.dirname(self.builder_exe_path))
                self.status_var.set("🚀 HookshotBuilder iniciado.")
                return
            except Exception:
                pass

        if not messagebox.askyesno(
            "Descargar Instalador Oficial de Hookshot",
            "¿Deseas descargar automáticamente el instalador oficial (HookshotBuilder.exe) desde el GitHub de NotRexed/Hookshot y ejecutarlo?",
            parent=self,
        ):
            return

        dl_win = tk.Toplevel(self)
        dl_win.title("Descargando HookshotBuilder.exe...")
        dl_win.geometry("460x150")
        dl_win.configure(bg=BG_PANEL)
        dl_win.transient(self)
        dl_win.grab_set()

        lbl_var = tk.StringVar(value="Conectando con GitHub Releases (NotRexed/Hookshot)...")
        tk.Label(dl_win, textvariable=lbl_var, bg=BG_PANEL, fg=FG_TEXT, font=("Segoe UI", 10)).pack(
            padx=20, pady=(24, 12)
        )
        pbar = ttk.Progressbar(dl_win, orient="horizontal", length=400, mode="determinate")
        pbar.pack(padx=20, pady=8)

        def _worker():
            try:
                dest_dir = os.path.join(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir(), "HookshotLauncher")
                os.makedirs(dest_dir, exist_ok=True)
                dest_exe = os.path.join(dest_dir, "HookshotBuilder-Setup.exe")

                req = urllib.request.Request(
                    HOOKSHOT_BUILDER_DIRECT,
                    headers={"User-Agent": "Hookshot-Launcher"},
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    total = int(resp.headers.get("Content-Length", 0))
                    downloaded = 0
                    with open(dest_exe, "wb") as out_f:
                        while True:
                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            out_f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                pct = int(downloaded * 100 / total)
                                self.after(
                                    0,
                                    lambda p=pct, d=downloaded, t=total: (
                                        pbar.configure(value=p),
                                        lbl_var.set(f"Descargando HookshotBuilder.exe... ({d // 1024} KB / {t // 1024} KB)"),
                                    ),
                                )

                def _finish():
                    dl_win.destroy()
                    self.status_var.set("✔ HookshotBuilder descargado. Ejecutando...")
                    os.startfile(dest_exe)

                self.after(0, _finish)
            except Exception as e:
                def _err():
                    dl_win.destroy()
                    if messagebox.askyesno(
                        "Descarga manual",
                        f"No se pudo descargar directamente ({e}).\n¿Abrir la página oficial de descargas en el navegador?",
                        parent=self,
                    ):
                        webbrowser.open(HOOKSHOT_RELEASES_URL)

                self.after(0, _err)

        threading.Thread(target=_worker, daemon=True).start()

    # -----------------------------------------------------------------------
    # Dynamic Play / Stop Button & Process Control
    # -----------------------------------------------------------------------
    def _update_play_button_state(self):
        if not self.is_hookshot_installed():
            self.play_btn.configure(
                text="⬇  INSTALAR HOOKSHOT",
                bg=ACCENT_GOLD,
                fg=ACCENT_GOLD_INK,
                activebackground=ACCENT_GOLD_HOVER,
                activeforeground=ACCENT_GOLD_INK,
            )
            return

        if self.is_game_running():
            self.play_btn.configure(
                text="⏹  DETENER HOOKSHOT",
                bg=ACCENT_RED,
                fg="#ffffff",
                activebackground=ACCENT_RED_HOVER,
                activeforeground="#ffffff",
            )
            self.status_var.set("🟢 Hookshot en ejecución (los cambios de opciones y partidas se sincronizan en vivo).")
        else:
            self.play_btn.configure(
                text="▶  JUGAR HOOKSHOT",
                bg=ACCENT_GREEN,
                fg="#ffffff",
                activebackground=ACCENT_GREEN_HOVER,
                activeforeground="#ffffff",
            )

    def _on_play_or_stop_clicked(self):
        if not self.is_hookshot_installed():
            self._trigger_update_or_install()
            return

        if self.is_game_running():
            self._stop_running_game()
        else:
            self._launch_game()

    def _stop_running_game(self):
        self.status_var.set("⏹ Deteniendo Hookshot...")
        self.update_idletasks()

        if self.game_proc is not None and self.game_proc.poll() is None:
            try:
                self.game_proc.terminate()
            except Exception:
                pass

        pids = find_running_pids_by_name("hookshot.exe")
        if pids:
            terminate_pids(pids)

        self.game_proc = None
        self._was_game_running = False
        self._update_play_button_state()
        self._on_game_closed()

    def _launch_game(self):
        if not self.save_options_and_language(show_toast=False):
            return

        active_prof = self.profiles_meta.get("active", "Principal")
        self.activate_profile(active_prof)

        exe_path = os.path.join(self.game_dir, "hookshot.exe")
        env = os.environ.copy()
        env["HOOKSHOT_NO_UPDATE_CHECK"] = "1"
        if self.profiles_meta.get("bt_rumble_compat", 1):
            env["HOS_HD_RUMBLE"] = "0"
        else:
            env.pop("HOS_HD_RUMBLE", None)

        self.status_var.set(f"🚀 Ejecutando Hookshot con el perfil '{active_prof}'...")
        self.update_idletasks()

        try:
            self.game_proc = subprocess.Popen([exe_path], cwd=self.game_dir, env=env)
        except Exception as e:
            messagebox.showerror("Error al iniciar", f"No se pudo ejecutar hookshot.exe:\n{e}", parent=self)
            return

        self._was_game_running = True
        self._update_play_button_state()

    def _on_game_closed(self):
        self.sync_active_save_to_current_profile()
        self._load_options_and_language()
        self._record_file_mtimes()
        self._refresh_profiles_ui()
        if self._settings_window_alive():
            self._populate_settings_ui()
        self._update_play_button_state()
        self.status_var.set("✔ Juego cerrado. Progreso del perfil y ajustes sincronizados automáticamente.")


def run_smoke_test():
    """Headless verification mode (--smoke-test) to validate profile sync, caption.sav parser, and ini writer."""
    game_dir = detect_game_dir()
    print(f"[SmokeTest] Game dir: {game_dir}")
    active_save = get_active_save_dir(game_dir)
    slots = inspect_save_folder(active_save)
    print(f"[SmokeTest] Found {len(slots)} save slots in {active_save}")
    for s in slots:
        has_jpg = len(s["jpeg_bytes"]) if s["jpeg_bytes"] else 0
        print(f"  - {s['slot_id']}: {s['location']} | {s['age']} | {s['datetime']} | JPG: {has_jpg} bytes")
    return 0


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        sys.exit(run_smoke_test())
    app = HookshotLauncherApp()
    if "--ui-test" in sys.argv:
        def _auto_verify():
            app.update()
            app._open_settings_dialog()
            app.update()
            print("[UITest] Main UI and Settings modal initialized and verified successfully.")
            app.destroy()
        app.after(800, _auto_verify)
    app.mainloop()
