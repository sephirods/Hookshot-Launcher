# 🛡 Hookshot Launcher & Profile Manager

[![Release](https://img.shields.io/github/v/release/sephirods/Hookshot-Launcher?color=d4af37&label=Release&style=for-the-badge)](https://github.com/sephirods/Hookshot-Launcher/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-238636?style=for-the-badge)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/Platform-Windows%2010%2F11%20x64-58a6ff?style=for-the-badge)](https://github.com/sephirods/Hookshot-Launcher/releases/latest)

Un **Launcher, Gestor de Perfiles de Guardado (Save Profiles), Configurador Gráfico y Actualizador/Instalador Automático** con interfaz moderna oscura para **Hookshot** (*The Legend of Zelda: Ocarina of Time Remake* PC Port).

> **Diseñado como herramienta independiente:** Se ejecuta junto a `hookshot.exe` sin modificar el código fuente del motor, por lo que **conservas todas las actualizaciones oficiales automáticas de `NotRexed/Hookshot`** sin perder nunca tus perfiles ni tu configuración.

---

## ✨ Características Principales

### 1. 🗂 Gestor de Perfiles de Guardado (Save Profiles) con Vista Previa Real
- **Múltiples Perfiles Independientes:** Crea, clona, renombra y cambia entre distintos perfiles de usuario (ej. *Principal*, *Master Quest / Reto*, *Hermano*, *Pruebas*) igual que en un emulador.
- **Visor de Capturas de Partida (`caption.sav`):** Extrae y muestra en directo la **captura JPEG real de 543×306** guardada dentro de cada slot (`slot_00` a `slot_05`), junto con:
  - 📍 **Nombre de la Zona** (ej. *Llanura de Hyrule*, *Lago Hylia*, *Bosque Kokiri*).
  - 🗡 **Estado / Edad de Link** (*Link Niño* / *Link Adulto*).
  - 🕒 **Fecha y hora exacta del último guardado**.
- **Backups en 1 Clic:** Comprime y restaura copias de seguridad `.zip` con marca de tiempo en la carpeta `backups/`.
- **Sincronización con Emuladores y NX2navi:** Importa y exporta partidas directamente hacia/desde **Eden, Lichii, Fritchii** y **NX2navi**.

### 2. 🖥 Configurador Pre-Lanzamiento Completo (`hookshot_options.ini` y `language.txt`)
Configura absolutamente todos los parámetros del motor antes de abrir el juego (preservando intactos tus mapeos de botones `pad_*` y `key_*`):
- **Gráficos y VRAM:**
  - Presets de memoria VRAM (`Mínimo 4GB`, `Bajo 6GB`, `Equilibrado 8GB (RTX 3070)`, `Alto 12GB`, `Ultra 16GB+`).
  - Resolución de Salida (`1080p`, `2048×1152`, `1440p`, `4K`, `5120×1440 Super Ultrawide`).
  - Escaladores IA (`NVIDIA DLSS`, `NVIDIA DLAA`, `Propio del Juego`) y selector de modelos Transformer (`Preset K / M / L`).
  - Límite de FPS (`60`, `90`, `120`, `144`, `165`, `240 FPS`) y **Frame Generation** (`2x` a `8x`).
  - Soporte **Ultrawide (21:9 / 32:9)**, **HDR10** (con ajuste de nits), **NVIDIA Reflex** y cachés de descriptores/samplers Vulkan.
- **Idioma, Audio y Sistema:**
  - Selector directo de idioma para `language.txt` (**Español Latinoamérica `es-419`**, **Español España `es`**, **Inglés `en-US`**, **Japonés `ja`**, etc.).
  - Velocidad de diálogos (`Normal`, `2x`, `4x`, `Instantáneo`), salida de audio (`Estéreo` / `5.1`), micrófono para la Ocarina, Discord Rich Presence y activación de herramientas **Debug / Cheats** en el menú `Insert`.
- **Controles y Cámara:**
  - Disposición de botones (`Nintendo`, `Xbox / PC`, `Swap A/B`), iconos en pantalla (`Switch`, `Xbox`, `PS4`, `PS5`, `Steam Deck`), cámara nativa con ratón 1:1 y apuntado por giroscopio.

### 3. 🔄 Actualizador Automático y Modo Auto-Instalador (Bootstrap)
- **Aviso de Nueva Versión:** Al abrir el Launcher, consulta la API de GitHub (`NotRexed/Hookshot/releases/latest`) y compara la versión con tu `hookshot_version.txt`. Si hay una actualización disponible, muestra un banner con botón de **Actualizar en 1 clic** (`HookshotBuilder.exe --update`).
- **Auto-Descarga si Hookshot no está instalado:** Si ejecutas el Launcher en una carpeta donde aún no existe `hookshot.exe`, el Launcher descarga automáticamente el `HookshotBuilder.exe` oficial desde GitHub con barra de progreso y lo inicia por ti.

---

## 🚀 Instalación Rápida

### Opción A: Instalador Automático (Recomendado)
1. Ve a la sección de [**Releases**](https://github.com/sephirods/Hookshot-Launcher/releases/latest).
2. Descarga y ejecuta **`HookshotLauncher-Setup.exe`** (o descomprime **`HookshotLauncher-Portable.zip`** en tu carpeta de Hookshot).
3. El instalador detectará automáticamente tu carpeta de Hookshot, instalará el Launcher con el icono oficial y creará los accesos directos en tu **Escritorio** y **Menú Inicio**.

### Opción B: Desde el Código Fuente
```powershell
git clone https://github.com/sephirods/Hookshot-Launcher.git
cd Hookshot-Launcher
pip install pillow
python install.py
```

---

## 🛠 Estructura del Proyecto

| Archivo | Descripción |
| :--- | :--- |
| `hookshot_launcher.py` | Aplicación principal (GUI oscura, gestor de perfiles, visor de capturas `caption.sav`, editor `.ini` y cliente de actualización GitHub). |
| `install.py` | Instalador gráfico y silencioso (`--silent`) con generador de accesos directos `.lnk` en Escritorio y Menú Inicio. |
| `src/launcher_stub.c` | Ejecutable nativo Win32 (`HookshotLauncher.exe`) en C que enlaza el recurso de icono oficial (`hookshot.res`) e inicia la interfaz sin ventana de consola. |
| `src/make_icon_res.py` | Generador determinista de iconos multi-resolución (`16px` a `256px`) para `.ico` y `.res`. |

---

## 📄 Licencia
Distribuido bajo la licencia **MIT**. Consulta el archivo [`LICENSE`](LICENSE) para más detalles.
