/*
 * HookshotLauncher.exe — Native Win32 GUI Bootstrap
 * Links with hookshot.res (official multi-size game icon) and launches hookshot_launcher.py
 * without any console window flash.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <shlobj.h>
#include <stdio.h>
#include <wchar.h>

static int file_exists(const wchar_t *path) {
    DWORD attr = GetFileAttributesW(path);
    return (attr != INVALID_FILE_ATTRIBUTES && !(attr & FILE_ATTRIBUTE_DIRECTORY));
}

int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPWSTR lpCmdLine, int nCmdShow) {
    (void)hInstance; (void)hPrevInstance; (void)nCmdShow;

    SetCurrentProcessExplicitAppUserModelID(L"sephirods.hookshot.launcher.1");

    wchar_t exe_path[MAX_PATH * 2];
    DWORD len = GetModuleFileNameW(NULL, exe_path, MAX_PATH * 2);
    if (!len || len >= MAX_PATH * 2) return 1;

    wchar_t dir[MAX_PATH * 2];
    wcsncpy(dir, exe_path, MAX_PATH * 2);
    wchar_t *slash = wcsrchr(dir, L'\\');
    if (slash) *slash = 0;

    wchar_t script_path[MAX_PATH * 2];
    _snwprintf(script_path, MAX_PATH * 2, L"%ls\\hookshot_launcher.py", dir);

    if (!file_exists(script_path)) {
        MessageBoxW(NULL,
            L"No se encontró hookshot_launcher.py junto a HookshotLauncher.exe.\n"
            L"Asegúrate de mantener ambos archivos en la misma carpeta.",
            L"Hookshot Launcher", MB_OK | MB_ICONERROR);
        return 1;
    }

    /* Candidate Python GUI interpreters (pythonw.exe avoids console flash) */
    wchar_t cmd[MAX_PATH * 4];
    const wchar_t *extra = (lpCmdLine && *lpCmdLine) ? lpCmdLine : L"";

    /* 1. Try pythonw.exe via PATH */
    wchar_t found_py[MAX_PATH * 2];
    if (SearchPathW(NULL, L"pythonw.exe", NULL, MAX_PATH * 2, found_py, NULL)) {
        _snwprintf(cmd, MAX_PATH * 4, L"\"%ls\" \"%ls\" %ls", found_py, script_path, extra);
    } else if (SearchPathW(NULL, L"pyw.exe", NULL, MAX_PATH * 2, found_py, NULL)) {
        _snwprintf(cmd, MAX_PATH * 4, L"\"%ls\" \"%ls\" %ls", found_py, script_path, extra);
    } else {
        /* Fallback to python.exe with CREATE_NO_WINDOW */
        _snwprintf(cmd, MAX_PATH * 4, L"python.exe \"%ls\" %ls", script_path, extra);
    }

    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));

    if (CreateProcessW(NULL, cmd, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, dir, &si, &pi)) {
        CloseHandle(pi.hThread);
        CloseHandle(pi.hProcess);
        return 0;
    }

    MessageBoxW(NULL,
        L"No se pudo encontrar Python (pythonw.exe) para iniciar la interfaz gráfica.\n"
        L"Instala Python 3.10+ desde python.org.",
        L"Hookshot Launcher", MB_OK | MB_ICONERROR);
    return 1;
}
