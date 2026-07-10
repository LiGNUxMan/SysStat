#!/usr/bin/env python3
# 
# SysStat (System Status) - CLI_Info
# 
# Autor: Axel O'BRIEN (LiGNUxMan) axelobrien@gmail.com
# 
# Colaboradores: ChatGPT (OpenAI) · Gemini/Antigravity (Google) · Claude (Anthropic)
#
# =======================================
# sysstat_cli_info.py - INFORME FINAL CLI
# =======================================
#
# Version: 065
#
# =======================================

import importlib.util
import json
import os
import re
import select
import subprocess
import sys
import sysstat_core
from sysstat import __version__

RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
REVERSE = "\033[7m"

COL_LABEL = 13 #Distancia del borde a Mim
COL_VAL = 13 #Separacion entre columnas min / avg / max
ICON_ZONE_WIDTH = 3 #Ancho de la "zona de ícono" en columnas (con o sin ícono real) — ghost_icon/icon_pad/icon_bar usan "   "

#REPORTS_DIR = os.path.expanduser("~/sysstat_reports")
REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sysstat_reports")
_ANSI_RE       = re.compile(r"\033\[[0-9;]*m")
_ANSI_SPLIT_RE = re.compile(r"(\033\[[0-9;]*m)")  # ← misma regex, pero con grupo, para partir y conservar los códigos
_PDF_AVAILABLE = importlib.util.find_spec("fpdf") is not None  # ← chequeo sin importar fpdf2 todavía

# Regex de emojis por RANGO Unicode — cubre íconos actuales y futuros sin
# necesidad de listarlos uno por uno. El "\s*" final es la clave de la
# alineación: se come TODOS los espacios que el ícono dejaba reservados a
# su alrededor (1, 2 o los que sea), así el PDF no depende del ancho
# particular de cada ícono — sin tocar líneas "fantasma" que no tienen
# ningún emoji (esas mantienen su indentación intacta, tal cual vienen).
_EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"  # banderas (regional indicators)
    "\U0001F300-\U0001FAFF"  # pictogramas, emoticones, transporte, símbolos suplementarios
    "\U00002600-\U000027BF"  # símbolos varios y dingbats (⚙️ ⚡ etc.)
    "\U00002300-\U000023FF"  # técnico misceláneo (⏱️ ⌚ etc.)
    "\U00002B00-\U00002BFF"  # flechas y símbolos varios (⬆️ ⬇️ etc.)
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200D"             # zero width joiner
    "]+\\s*"
)

# Mapa de código ANSI → RGB. BOLD/RESET se manejan aparte (no son color).
_ANSI_COLOR_MAP = {
    "\033[31m":       (200, 30, 30),    # RED
    "\033[93m":       (170, 130, 0),    # YELLOW (oscurecido para fondo blanco)
    "\033[38;5;208m": (230, 120, 0),    # ORANGE
    "\033[2m":        (130, 130, 130),  # DIM (gris)
}
_PDF_BLACK = (0, 0, 0)

# =============================================================
# 1.0 — HELPERS DE FORMATO Y ENTORNO
# =============================================================

def _play_beep():
    """Aviso sonoro al terminar el informe final — señal de que el script paró y
    espera una tecla (Q/X/T/L/P). Cadena de 3 niveles, cada uno cae al siguiente
    SOLO si el comando no está instalado (FileNotFoundError):
      1. sox ('play')  → método principal, confirmado funcional en HW real
      2. beep          → alternativa via pcspkr/evdev si no hay sox
      3. bell ASCII    → último recurso nativo, sin dependencias externas
    Copia propia de sysstat_cli.play_beep() — regla 9: sin helpers compartidos."""
    try:
        subprocess.Popen(
            ["play", "-q", "-n", "synth", "0.1", "sin", "880", "vol", "0.2"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return
    except FileNotFoundError:
        pass
    try:
        subprocess.Popen(
            ["beep", "-f", "880", "-l", "100"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return
    except FileNotFoundError:
        pass
    sys.stdout.write("\a")
    sys.stdout.flush()

def _color(key, value):
    return sysstat_core.get_metric_color(key, value)

def _color_val(color, text):
    padded = f"{text:<{COL_VAL}}"
    return f"{color}{BOLD}{padded}{RESET}"

def _ghz(hz):
    return f"{hz / 1_000_000:.2f}GHz"

def _gb(kb):
    return f"{kb / 1_048_576:.2f}GB"

def _pct(value):
    return f"{value:.0f}%"

def _temp(value):
    return f"{value:.0f}°C"

def _mbs(value):
    return f"{value:.2f}MB/s"

def _mbits(value):
    return f"{value:.2f}Mb/s"

def _speed(mbps):
    return f"{mbps / 1000:g}Gb/s" if mbps >= 1000 else f"{mbps}Mb/s"

# =============================================================
# 2.0 — INFORME FINAL (FLUJO PRINCIPAL)
# =============================================================

def show_report(config):
    buffer = []

    print(f"\n")

    # ── Íconos resueltos una sola vez ────────────────────────
    ghost_icon    = "   " + " " * COL_LABEL if config.icon else " " * COL_LABEL
    icon_pad      = "   " if config.icon else ""
    icon_bar      = "   " if config.icon else ""
    exit_icon     = "🚪 " if config.icon else ""
    save_txt_icon = "📝 " if config.icon else ""
    save_log_icon = "📜 " if config.icon else ""
    save_pdf_icon = "📄 " if config.icon else ""

    if config.sys:
        os_name_icon = "🐧 " if config.icon else ""
        kernel_icon  = "⚙️  " if config.icon else ""

    if config.host:
        hostname_icon = "💻 " if config.icon else "" # Alternativas 🏠 💻 🖥️
        user_icon     = "🧑 " if config.icon else "" # Alternativas 👤 🧑 🧑‍🦱

    if config.up:
        uptime_icon   = "🕒 " if config.icon else ""
        datetime_icon = "📅 " if config.icon else ""
        runtime_icon  = "⏱️  " if config.icon else ""
        cycles_icon   = "🔄 " if config.icon else ""

    if config.cpu:
        cpu_usage_icon = "🔳 " if config.icon else "" # Alternativas 🤖 🎛️ 🔲 🔳
        cpu_freq_icon  = "🚀 " if config.icon else "" # Alternatica ⚡ 🚀
        cpu_temp_icon  = "🌡️  " if config.icon else ""

    if config.ram:
        ram_icon  = "📟 " if config.icon else "" # Alternativas 🧮 📟
        swap_icon = "🔀 " if config.icon else "" # Alternativas 💾 🔀

    if config.proc:
        proc_icon = "📋 " if config.icon else "" # Alternativas 🧩 📋

    if config.load:
        load_icon = "📊 " if config.icon else ""

    if config.disk:
        disk_icon       = "🗄️  " if config.icon else ""
        disk_read_icon  = "📥 " if config.icon else ""
        disk_write_icon = "📤 " if config.icon else ""
        disk_temp_icon  = "🌡️  " if config.icon else ""

    if config.lan:
        lan_icon      = "🖧  " if config.icon else "" # Alternativas 🌐 🖧 🔌
        lan_down_icon = "⬇️  " if config.icon else ""
        lan_up_icon   = "⬆️  " if config.icon else ""

    if config.wifi:
        wifi_signal_icon = "🛜 " if config.icon else "" # Alternativas 🛜 📶
        wifi_down_icon   = "⬇️  " if config.icon else ""
        wifi_up_icon     = "⬆️  " if config.icon else ""
        wifi_temp_icon   = "🌡️  " if config.icon else ""

    if config.bat:
        bat_icon = "🔋 " if config.icon else ""

    # ── Encabezado ───────────────────────────────────────────
    # SysStat CLI/GUI v5.23.0.20260615a
    buffer.append(f"{BOLD}SysStat CLI/GUI{RESET} v{__version__}")

    # ── Sistema ───────────────────────────────────────────────
    # 🐧 OS: Linux Mint 22.3 - ⚙️  Kernel version: 7.0.0-14-generic
    if config.sys:
        sys_data = sysstat_core.get("sys")
        buffer.append(f"{os_name_icon}OS: {BOLD}{sys_data['os_name']}{RESET} - {kernel_icon}Kernel version: {BOLD}{sys_data['kernel_version']}{RESET}")

    # 🏠 Hostname: hal9001c - 👤 User: axel
    if config.host:
        host_data = sysstat_core.get("host")
        buffer.append(f"{hostname_icon}Hostname: {BOLD}{host_data['hostname']}{RESET} - {user_icon}User: {BOLD}{host_data['user']}{RESET}")

    # 🕒 Uptime: 4d 20:02:28 - ⏱️  Runtime: 4d 18:07:53 - 🔄 Cycles: 15258
    # 📅 Start: 18:14:32 24/06/26 - 📅 End: 12:22:18 29/06/26
    if config.up:
        uptime_data    = sysstat_core.get("up")
        start_datetime = sysstat_core.get("start_datetime")
        cycle_count    = sysstat_core.get_count("cpu") if config.cpu else 0
        buffer.append(f"{uptime_icon}Uptime: {BOLD}{uptime_data['uptime']}{RESET} - {runtime_icon}Runtime: {BOLD}{sysstat_core.get_runtime()}{RESET} - {cycles_icon}Cycles: {BOLD}{cycle_count}{RESET}")
        buffer.append(f"{datetime_icon}Start: {BOLD}{start_datetime}{RESET} - {datetime_icon}End: {BOLD}{uptime_data['datetime']}{RESET}")

    # ── Cabecera de columnas ──────────────────────────────────
    #                 Min           Avg           Max
    buffer.append(f"{ghost_icon}{DIM}{'Min':<{COL_VAL}} {'Avg':<{COL_VAL}} {'Max':<{COL_VAL}}{RESET}")

    # ── CPU ───────────────────────────────────────────────────
    # 🔲 CPU used:    5%            21%           79%
    # ⚡ CPU freq:    0.70GHz       1.34GHz       3.11GHz
    # 🌡️ CPU temp:    32°C          39°C          62°C
    if config.cpu:
        cpu_s   = sysstat_core.get_stats("cpu")
        cpu_avg = round(cpu_s["avg"])
        buffer.append(f"{cpu_usage_icon}{f'CPU used:':<{COL_LABEL}}"
            f"{_color_val(_color('cpu', cpu_s['min']), _pct(cpu_s['min']))} "
            f"{_color_val(_color('cpu', cpu_avg),      _pct(cpu_avg))} "
            f"{_color_val(_color('cpu', cpu_s['max']), _pct(cpu_s['max']))}"
        )

        freq_s     = sysstat_core.get_stats("cpu_freq_hz")
        freq_pct_s = sysstat_core.get_stats("cpu_freq_pct")
        buffer.append(f"{cpu_freq_icon}{f'CPU freq:':<{COL_LABEL}}"
            f"{_color_val(_color('cpu_freq_pct', freq_pct_s['min']), _ghz(freq_s['min']))} "
            f"{_color_val(_color('cpu_freq_pct', freq_pct_s['avg']), _ghz(freq_s['avg']))} "
            f"{_color_val(_color('cpu_freq_pct', freq_pct_s['max']), _ghz(freq_s['max']))}"
        )

        if sysstat_core.get("cpu_temp"):
            temp_s   = sysstat_core.get_stats("cpu_temp")
            temp_avg = round(temp_s["avg"])
            buffer.append(f"{cpu_temp_icon}{f'CPU temp:':<{COL_LABEL}}"
                f"{_color_val(_color('cpu_temp', temp_s['min']), _temp(temp_s['min']))} "
                f"{_color_val(_color('cpu_temp', temp_avg),      _temp(temp_avg))} "
                f"{_color_val(_color('cpu_temp', temp_s['max']), _temp(temp_s['max']))}"
            )

    # ── RAM / Swap ────────────────────────────────────────────
    # 📟 RAM used:    48%           50%           68%
    #                 7.37GB        7.72GB        10.50GB00
    # 💾 Swap used:   0%            0%            0%
    #                 0.00GB        0.00GB        0.00GB
    if config.ram:
        ram_s    = sysstat_core.get_stats("ram")
        ram_kb_s = sysstat_core.get_stats("ram_kb")
        ram_avg  = round(ram_s["avg"])
        buffer.append(f"{ram_icon}{f'RAM used:':<{COL_LABEL}}"
            f"{_color_val(_color('ram', ram_s['min']), _pct(ram_s['min']))} "
            f"{_color_val(_color('ram', ram_avg),      _pct(ram_avg))} "
            f"{_color_val(_color('ram', ram_s['max']), _pct(ram_s['max']))}"
        )
        buffer.append(f"{ghost_icon}"
            f"{_color_val('', _gb(ram_kb_s['min']))} "
            f"{_color_val('', _gb(ram_kb_s['avg']))} "
            f"{_color_val('', _gb(ram_kb_s['max']))}"
        )

        swap_s    = sysstat_core.get_stats("swap")
        swap_kb_s = sysstat_core.get_stats("swap_kb")
        swap_avg  = round(swap_s["avg"])
        buffer.append(f"{swap_icon}{f'Swap used:':<{COL_LABEL}}"
            f"{_color_val(_color('swap', swap_s['min']), _pct(swap_s['min']))} "
            f"{_color_val(_color('swap', swap_avg),      _pct(swap_avg))} "
            f"{_color_val(_color('swap', swap_s['max']), _pct(swap_s['max']))}"
        )
        buffer.append(f"{ghost_icon}"
            f"{_color_val('', _gb(swap_kb_s['min']))} "
            f"{_color_val('', _gb(swap_kb_s['avg']))} "
            f"{_color_val('', _gb(swap_kb_s['max']))}"
        )

    # ── Processes ─────────────────────────────────────────────
    # 📋 Processes:   296           301           310
    if config.proc:
        proc_s = sysstat_core.get_stats("proc")
        buffer.append(f"{proc_icon}{f'Processes:':<{COL_LABEL}}"
            f"{_color_val('', str(int(proc_s['min'])))} "
            f"{_color_val('', str(int(proc_s['avg'])))} "
            f"{_color_val('', str(int(proc_s['max'])))}"
        )

    # ── Load average ──────────────────────────────────────────
    # 📊 Load avg:    0.03          1.13          4.88
    if config.load:
        load_s = sysstat_core.get_stats("load")
        def _load_fmt(v): return f"{v:.2f}"
        buffer.append(f"{load_icon}{f'Load avg:':<{COL_LABEL}}"
            f"{_color_val(_color('load', load_s['min']), _load_fmt(load_s['min']))} "
            f"{_color_val(_color('load', load_s['avg']), _load_fmt(load_s['avg']))} "
            f"{_color_val(_color('load', load_s['max']), _load_fmt(load_s['max']))}"
        )

    # ── Disk ──────────────────────────────────────────────────
    # 🗄️ Disk used:   55%           55%           55%
    #                 259.24GB      259.28GB      259.33GB
    # 📥 Disk read:   0.00MB/s      0.04MB/s      13.85MB/s
    # 📤 Disk write:  0.00MB/s      0.24MB/s      6.23MB/s
    # 🌡️ Disk temp:   31°C          32°C          36°C
    if config.disk:
        disk_s    = sysstat_core.get_stats("disk")
        disk_kb_s = sysstat_core.get_stats("disk_kb")
        disk_avg  = round(disk_s["avg"])
        buffer.append(f"{disk_icon}{f'Disk used:':<{COL_LABEL}}"
            f"{_color_val(_color('disk_used_pct', disk_s['min']), _pct(disk_s['min']))} "
            f"{_color_val(_color('disk_used_pct', disk_avg),      _pct(disk_avg))} "
            f"{_color_val(_color('disk_used_pct', disk_s['max']), _pct(disk_s['max']))}"
        )
        buffer.append(f"{ghost_icon}"
            f"{_color_val('', _gb(disk_kb_s['min']))} "
            f"{_color_val('', _gb(disk_kb_s['avg']))} "
            f"{_color_val('', _gb(disk_kb_s['max']))}"
        )

        read_s = sysstat_core.get_stats("disk_read")
        buffer.append(f"{disk_read_icon}{f'Disk read:':<{COL_LABEL}}"
            f"{_color_val('', _mbs(read_s['min']))} "
            f"{_color_val('', _mbs(read_s['avg']))} "
            f"{_color_val('', _mbs(read_s['max']))}"
        )

        write_s = sysstat_core.get_stats("disk_write")
        buffer.append(f"{disk_write_icon}{f'Disk write:':<{COL_LABEL}}"
            f"{_color_val('', _mbs(write_s['min']))} "
            f"{_color_val('', _mbs(write_s['avg']))} "
            f"{_color_val('', _mbs(write_s['max']))}"
        )

        if sysstat_core.get("disk_temp"):
            dtemp_s   = sysstat_core.get_stats("disk_temp")
            dtemp_avg = round(dtemp_s["avg"])
            buffer.append(f"{disk_temp_icon}{f'Disk temp:':<{COL_LABEL}}"
                f"{_color_val(_color('disk_temp', dtemp_s['min']), _temp(dtemp_s['min']))} "
                f"{_color_val(_color('disk_temp', dtemp_avg),      _temp(dtemp_avg))} "
                f"{_color_val(_color('disk_temp', dtemp_s['max']), _temp(dtemp_s['max']))}"
            )

    # ── LAN ───────────────────────────────────────────────────
    # 
    if config.lan and sysstat_core.get_count("lan_speed") > 0:
        speed_s = sysstat_core.get_stats("lan_speed")
        buffer.append(f"{lan_icon}{f'Lan speed:':<{COL_LABEL}}"
            f"{_color_val('', _speed(speed_s['min']))} "
            f"{_color_val('', _speed(speed_s['avg']))} "
            f"{_color_val('', _speed(speed_s['max']))}"
        )

        down_s = sysstat_core.get_stats("lan_down")
        buffer.append(f"{lan_down_icon}{f'Lan down:':<{COL_LABEL}}"
            f"{_color_val('', _mbs(down_s['min']))} "
            f"{_color_val('', _mbs(down_s['avg']))} "
            f"{_color_val('', _mbs(down_s['max']))}"
        )

        up_s = sysstat_core.get_stats("lan_up")
        buffer.append(f"{lan_up_icon}{f'Lan up:':<{COL_LABEL}}"
            f"{_color_val('', _mbs(up_s['min']))} "
            f"{_color_val('', _mbs(up_s['avg']))} "
            f"{_color_val('', _mbs(up_s['max']))}"
        )

    # ── WiFi ──────────────────────────────────────────────────
    # 📶 WiFi signal: 52%           57%           64%
    #    WiFi speed:  97.60Mb/s     202.99Mb/s    260.00Mb/s
    # ⬇️ WiFi down:   0.00MB/s      0.08MB/s      1.30MB/s
    # ⬆️ WiFi up:     0.00MB/s      0.00MB/s      0.08MB/s
    # 🌡️ WiFi temp:   30°C          40°C          47°C
    if config.wifi and sysstat_core.get_count("wifi") > 0:
        wifi_s = sysstat_core.get_stats("wifi")
        buffer.append(f"{wifi_signal_icon}{f'WiFi signal:':<{COL_LABEL}}"
            f"{_color_val(_color('wifi', wifi_s['min']), _pct(wifi_s['min']))} "
            f"{_color_val(_color('wifi', wifi_s['avg']), _pct(round(wifi_s['avg'])))} "
            f"{_color_val(_color('wifi', wifi_s['max']), _pct(wifi_s['max']))}"
        )

        speed_s = sysstat_core.get_stats("wifi_speed")
        buffer.append(f"{icon_pad}{f'WiFi speed:':<{COL_LABEL}}"
            f"{_color_val('', _mbits(speed_s['min']))} "
            f"{_color_val('', _mbits(speed_s['avg']))} "
            f"{_color_val('', _mbits(speed_s['max']))}"
        )

        down_s = sysstat_core.get_stats("wifi_down")
        buffer.append(f"{wifi_down_icon}{f'WiFi down:':<{COL_LABEL}}"
            f"{_color_val('', _mbs(down_s['min']))} "
            f"{_color_val('', _mbs(down_s['avg']))} "
            f"{_color_val('', _mbs(down_s['max']))}"
        )

        up_s = sysstat_core.get_stats("wifi_up")
        buffer.append(f"{wifi_up_icon}{f'WiFi up:':<{COL_LABEL}}"
            f"{_color_val('', _mbs(up_s['min']))} "
            f"{_color_val('', _mbs(up_s['avg']))} "
            f"{_color_val('', _mbs(up_s['max']))}"
        )

        if sysstat_core.get_count("wifi_temp") > 0:
            wtemp_s   = sysstat_core.get_stats("wifi_temp")
            wtemp_avg = round(wtemp_s["avg"])
            buffer.append(f"{wifi_temp_icon}{f'WiFi temp:':<{COL_LABEL}}"
                f"{_color_val(_color('wifi_temp', wtemp_s['min']), _temp(wtemp_s['min']))} "
                f"{_color_val(_color('wifi_temp', wtemp_avg),      _temp(wtemp_avg))} "
                f"{_color_val(_color('wifi_temp', wtemp_s['max']), _temp(wtemp_s['max']))}"
            )

    # ── Battery ───────────────────────────────────────────────
    # 🔋 Battery:     15%           54%           100%
    if config.bat and sysstat_core.get_count("bat") > 0:
        bat_s   = sysstat_core.get_stats("bat")
        bat_avg = round(bat_s["avg"])
        buffer.append(f"{bat_icon}{f'Battery:':<{COL_LABEL}}"
            f"{_color_val(_color('bat', bat_s['min']), _pct(bat_s['min']))} "
            f"{_color_val(_color('bat', bat_avg),      _pct(bat_avg))} "
            f"{_color_val(_color('bat', bat_s['max']), _pct(bat_s['max']))}"
        )

    # ── Aviso sonoro: el script terminó y espera una tecla ────────
    if config.beep:
        _play_beep()

    # ── Se imprime todo el informe junto, ya armado en el buffer ──
    print("\n".join(buffer))

    # ── Barra de acciones finales — Salir / Guardar TXT / Guardar LOG / Guardar PDF ─────
    # Para habilitar la opcion "(P) Save PDF" instalar la libreria fpdf2: "pip install fpdf2 --break-system-packages"
    # 🚪 (Q/X) Exit | 📝 (T) Save TXT | 📜 (L) Save LOG | 📄 (P) Save PDF
    pdf_hint = f" | {save_pdf_icon}(P) Save PDF" if _PDF_AVAILABLE else ""
    bar_text = f"{icon_bar}{REVERSE}{DIM}{exit_icon}(Q/X) Exit | {save_txt_icon}(T) Save TXT | {save_log_icon}(L) Save LOG{pdf_hint}{RESET}"
    sys.stdout.write(bar_text)
    sys.stdout.flush()
    _wait_final_keypress(buffer, config.icon)

    # 4.0 — VOLCADO DE DEBUG (DB COMPLETA)
    # Excepción consciente a la regla 6: accede directo a _stats_db porque esto
    # nunca corre en el flujo real del script — solo si descomentás la línea
    # de abajo, para curiosear/depurar.
    # _show_db_dump() # Descomentar esta linea para ver la _stats_db completa

# =============================================================
# 3.0 — GUARDADO DE ARCHIVOS Y CONTROL DE TECLADO (POST-INFORME)
# =============================================================

def _wait_final_keypress(buffer, icon_mode: bool):
    """Espera Q/X (salir), T (guardar TXT) o L (guardar LOG) o P (guarda PDF). Tras guardar, sale directo.
    S guarda los TRES formatos juntos — tecla oculta, uso interno (ej: generar muestra para GitHub)."""
    import tty
    import termios
    fd           = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            ready_fds, _, _ = select.select([sys.stdin], [], [], 0.5)
            if not ready_fds:
                continue
            key_pressed = sys.stdin.read(1).lower()
            if key_pressed in ("q", "x"):
                break
            elif key_pressed == "t":
                saved_path = _save_file(buffer, "txt", strip_colors=True)
                sys.stdout.write(f"\nView: cat {saved_path}")
                break
            elif key_pressed == "l":
                saved_path = _save_file(buffer, "log", strip_colors=False)
                sys.stdout.write(f"\nView: cat {saved_path}")
                break
            elif key_pressed == "p" and _PDF_AVAILABLE:
                saved_path = _save_pdf(buffer, icon_mode)
                sys.stdout.write(f"\nView: xdg-open {saved_path}" if saved_path else "\nError: no se pudo generar el PDF")
                break
            elif key_pressed == "d":
                txt_path = _save_file(buffer, "txt", strip_colors=True)
                log_path = _save_file(buffer, "log", strip_colors=False)
                pdf_path = _save_pdf(buffer, icon_mode) if _PDF_AVAILABLE else None
                db_path  = _save_db_dump()
                _show_db_dump()
                sys.stdout.write(f"\nView: cat {txt_path}")
                sys.stdout.write(f"\nView: cat {log_path}")
                sys.stdout.write(f"\nView: xdg-open {pdf_path}" if pdf_path else "\nAviso: PDF no generado (fpdf2 no instalado)")
                sys.stdout.write(f"\nView: cat {db_path}")                
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        print()

def _save_file(buffer, extension: str, strip_colors: bool):
    """Vuelca el buffer de líneas a un archivo en REPORTS_DIR.
    El nombre usa la hora de ARRANQUE del script (no la de guardado) — representa
    cuándo empezó la medición, no cuándo el usuario se acordó de guardarla."""
    try:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        timestamp = sysstat_core.get_start_timestamp()
        filename  = f"sysstat_{timestamp}.{extension}"
        filepath  = os.path.join(REPORTS_DIR, filename)
        content   = "\n".join(_strip_ansi(l) if strip_colors else l for l in buffer)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content + "\n")
        return filepath
    except Exception:
        return None

def _strip_ansi(text: str) -> str:
    """Remueve todos los códigos de color/estilo ANSI — usado para el TXT limpio."""
    return _ANSI_RE.sub("", text)

def _pdf_segments(line: str, icon_mode: bool):
    """Parsea una línea con códigos ANSI y devuelve [(texto, bold, rgb), ...],
    limpiando emojis y preservando negrita/color para el PDF.

    La 'zona de ícono' (íconos reales, o relleno tipo ghost_icon/icon_pad)
    siempre vale ICON_ZONE_WIDTH columnas en la terminal — con ícono real o
    sin él. En el PDF no hay ícono que mostrar, así que esa zona se recorta
    a 0 en el PRIMER segmento de la línea, tope ICON_ZONE_WIDTH para no
    comerse la zona de COL_LABEL que sigue (la que alinea los renglones
    fantasma de RAM/Swap/Disk en GB bajo sus valores en %)."""
    segments = []
    bold     = False
    rgb      = _PDF_BLACK
    first    = True
    for part in _ANSI_SPLIT_RE.split(line):
        if not part:
            continue
        if part.startswith("\033["):
            if part == RESET:
                bold, rgb = False, _PDF_BLACK
            elif part == BOLD:
                bold = True
            elif part in _ANSI_COLOR_MAP:
                rgb = _ANSI_COLOR_MAP[part]
            # códigos desconocidos se ignoran (KISS)
            continue
        text = _EMOJI_RE.sub("", part)
        if first:
            if icon_mode:
                stripped = text.lstrip(" ")
                removed  = len(text) - len(stripped)
                text     = (" " * max(0, removed - ICON_ZONE_WIDTH)) + stripped
            first = False
        if text:
            segments.append((text, bold, rgb))
    return segments

def _save_pdf(buffer, icon_mode: bool):
    """Vuelca el buffer a PDF via fpdf2, preservando negrita y colores críticos.
    Los emojis se eliminan por regex de rango Unicode (fuentes core son Latin-1)."""
    try:
        from fpdf import FPDF
        os.makedirs(REPORTS_DIR, exist_ok=True)
        timestamp = sysstat_core.get_start_timestamp()
        filename  = f"sysstat_{timestamp}.pdf"
        filepath  = os.path.join(REPORTS_DIR, filename)
        line_h = 5
        pdf = FPDF()
        pdf.add_page()
        for line in buffer:
            for text, bold, rgb in _pdf_segments(line, icon_mode):
                pdf.set_font("Courier", style="B" if bold else "", size=12)
                pdf.set_text_color(*rgb)
                pdf.write(line_h, text)
            pdf.ln(line_h)
        pdf.output(filepath)
        return filepath
    except Exception:
        return None

# =============================================================
# 4.0 — VOLCADO DE DEBUG (DB COMPLETA)
# =============================================================

def _show_db_dump():
    print()
    print(f"┌──────────────────────────────┐")
    print(f"│ {BOLD}_stats_db (volcado completo){RESET} │")
    print(f"└──────────────────────────────┘")
    print()
    print(json.dumps(sysstat_core._stats_db, indent=2, default=str))
    print()

def _save_db_dump():
    """Guarda el volcado completo de _stats_db en un archivo TXT en REPORTS_DIR.
    Excepción consciente a la regla 6 — solo se usa en el flujo de debug (tecla D)."""
    try:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        timestamp = sysstat_core.get_start_timestamp()
        filepath  = os.path.join(REPORTS_DIR, f"stats_db_{timestamp}.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json.dumps(sysstat_core._stats_db, indent=2, default=str) + "\n")
        return filepath
    except Exception:
        return None
