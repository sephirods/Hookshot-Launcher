#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hookshot Launcher Installer & Shortcut Creator
==============================================
Installs HookshotLauncher.exe, hookshot_launcher.py, and hookshot.ico into the
target Hookshot folder, creates Desktop and Start Menu shortcuts (.lnk) with the
game icon, and optionally launches the application.
"""

import json
import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

APP_SHORTCUT_NAME = "Zelda Ocarina of Time (Hookshot).lnk"


def detect_default_target():
    local_app = os.environ.get("LOCALAPPDATA") or ""
    builder_cfg = os.path.join(local_app, "HookshotBuilder", "builder-settings.json")
    if os.path.isfile(builder_cfg):
        try:
            with open(builder_cfg, "r", encoding="utf-8") as f:
                out_dir = json.load(f).get("Out")
                if out_dir:
                    return out_dir
        except Exception:
            pass

    if os.path.isdir(r"D:\Users\Juan\Games\Hookshot"):
        return r"D:\Users\Juan\Games\Hookshot"

    return os.path.join(os.path.expanduser("~"), "Games", "Hookshot")


def create_windows_shortcut(shortcut_path, target_exe, working_dir, icon_path, description):
    """Create a Windows .lnk shortcut using PowerShell WScript.Shell COM object."""
    ps_script = (
        f'$ws = New-Object -ComObject WScript.Shell; '
        f'$s = $ws.CreateShortcut("{shortcut_path}"); '
        f'$s.TargetPath = "{target_exe}"; '
        f'$s.WorkingDirectory = "{working_dir}"; '
        f'$s.IconLocation = "{icon_path},0"; '
        f'$s.Description = "{description}"; '
        f'$s.Save()'
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def install_to_directory(target_dir, create_desktop=True, create_start_menu=True):
    src_root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(target_dir, exist_ok=True)

    files_to_copy = [
        ("HookshotLauncher.exe", "HookshotLauncher.exe"),
        ("hookshot_launcher.py", "hookshot_launcher.py"),
    ]
    ico_src = os.path.join(src_root, "assets", "hookshot.ico")
    if not os.path.isfile(ico_src):
        ico_src = os.path.join(src_root, "hookshot.ico")

    for src_name, dst_name in files_to_copy:
        s_path = os.path.join(src_root, src_name)
        d_path = os.path.join(target_dir, dst_name)
        if os.path.isfile(s_path) and os.path.normcase(os.path.abspath(s_path)) != os.path.normcase(os.path.abspath(d_path)):
            shutil.copy2(s_path, d_path)

    target_ico = os.path.join(target_dir, "hookshot.ico")
    if os.path.isfile(ico_src) and os.path.normcase(os.path.abspath(ico_src)) != os.path.normcase(os.path.abspath(target_ico)):
        shutil.copy2(ico_src, target_ico)

    target_exe = os.path.join(target_dir, "HookshotLauncher.exe")
    desc = "Hookshot Launcher & Profile Manager - The Legend of Zelda: Ocarina of Time PC"

    created_shortcuts = []
    if create_desktop:
        desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        if os.path.isdir(desktop_dir):
            lnk_desktop = os.path.join(desktop_dir, APP_SHORTCUT_NAME)
            create_windows_shortcut(lnk_desktop, target_exe, target_dir, target_ico, desc)
            created_shortcuts.append(lnk_desktop)

    if create_start_menu:
        appdata = os.environ.get("APPDATA") or ""
        start_menu_dir = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs")
        if os.path.isdir(start_menu_dir):
            lnk_start = os.path.join(start_menu_dir, APP_SHORTCUT_NAME)
            create_windows_shortcut(lnk_start, target_exe, target_dir, target_ico, desc)
            created_shortcuts.append(lnk_start)

    return created_shortcuts


def run_gui_installer():
    root = tk.Tk()
    root.title("Instalador de Hookshot Launcher v1.0.0")
    root.geometry("560x300")
    root.configure(bg="#0d1117")
    root.resizable(False, False)

    tk.Label(
        root,
        text="🛡 INSTALADOR DE HOOKSHOT LAUNCHER",
        bg="#0d1117",
        fg="#d4af37",
        font=("Segoe UI", 13, "bold"),
    ).pack(anchor="w", padx=20, pady=(18, 4))

    tk.Label(
        root,
        text="Instala el gestor de perfiles, configurador gráfico y actualizador automático para Hookshot.",
        bg="#0d1117",
        fg="#8b949e",
        font=("Segoe UI", 9),
    ).pack(anchor="w", padx=20, pady=(0, 14))

    path_frame = tk.Frame(root, bg="#0d1117")
    path_frame.pack(fill="x", padx=20, pady=6)

    tk.Label(path_frame, text="Carpeta de destino:", bg="#0d1117", fg="#e6edf3", font=("Segoe UI", 9, "bold")).pack(
        anchor="w"
    )

    row = tk.Frame(path_frame, bg="#0d1117")
    row.pack(fill="x", pady=4)

    dir_var = tk.StringVar(value=detect_default_target())
    entry = tk.Entry(row, textvariable=dir_var, bg="#21262d", fg="#e6edf3", insertbackground="#e6edf3", relief="flat", font=("Segoe UI", 10))
    entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))

    def _browse():
        d = filedialog.askdirectory(initialdir=dir_var.get(), title="Seleccionar carpeta de Hookshot")
        if d:
            dir_var.set(d)

    tk.Button(
        row, text="Examinar...", command=_browse, bg="#1f2630", fg="#e6edf3", relief="flat", padx=10, pady=4
    ).pack(side="right")

    desktop_var = tk.BooleanVar(value=True)
    startmenu_var = tk.BooleanVar(value=True)
    launch_var = tk.BooleanVar(value=True)

    opts = tk.Frame(root, bg="#0d1117")
    opts.pack(fill="x", padx=20, pady=8)

    tk.Checkbutton(
        opts, text="Crear acceso directo en el Escritorio", variable=desktop_var,
        bg="#0d1117", fg="#e6edf3", selectcolor="#21262d", activebackground="#0d1117", activeforeground="#d4af37"
    ).pack(anchor="w")
    tk.Checkbutton(
        opts, text="Crear acceso directo en el Menú Inicio", variable=startmenu_var,
        bg="#0d1117", fg="#e6edf3", selectcolor="#21262d", activebackground="#0d1117", activeforeground="#d4af37"
    ).pack(anchor="w")
    tk.Checkbutton(
        opts, text="Abrir Hookshot Launcher al finalizar", variable=launch_var,
        bg="#0d1117", fg="#e6edf3", selectcolor="#21262d", activebackground="#0d1117", activeforeground="#d4af37"
    ).pack(anchor="w")

    def _do_install():
        target = dir_var.get().strip()
        if not target:
            messagebox.showwarning("Ruta vacía", "Selecciona una carpeta válida.")
            return
        try:
            install_to_directory(target, desktop_var.get(), startmenu_var.get())
            messagebox.showinfo(
                "Instalación completada",
                f"Hookshot Launcher se ha instalado correctamente en:\n{target}",
                parent=root,
            )
            if launch_var.get():
                exe = os.path.join(target, "HookshotLauncher.exe")
                if os.path.isfile(exe):
                    subprocess.Popen([exe], cwd=target)
            root.destroy()
        except Exception as e:
            messagebox.showerror("Error de instalación", str(e), parent=root)

    tk.Button(
        root,
        text="⬇  INSTALAR AHORA",
        command=_do_install,
        bg="#238636",
        fg="#ffffff",
        activebackground="#2ea043",
        activeforeground="#ffffff",
        relief="flat",
        font=("Segoe UI", 10, "bold"),
        padx=20,
        pady=8,
        cursor="hand2",
    ).pack(side="bottom", pady=16)

    root.mainloop()


if __name__ == "__main__":
    if "--silent" in sys.argv:
        target = detect_default_target()
        for i, arg in enumerate(sys.argv):
            if arg == "--target" and i + 1 < len(sys.argv):
                target = sys.argv[i + 1]
        shortcuts = install_to_directory(target, True, True)
        print("Installed to:", target)
        for s in shortcuts:
            print("Shortcut created:", s)
        sys.exit(0)
    run_gui_installer()
