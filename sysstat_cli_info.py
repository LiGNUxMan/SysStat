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
# Version: 049
#
# =======================================

import importlib.util
import json
import os
import re
import select
import sys
import sysstat_core
from sysstat import __version__

RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
REVERSE = "\033[7m"

COL_LABEL = 13 #Distancia del borde a Mim
COL_VAL = 13 #Separacion entre columnas min / avg / max

#REPORTS_DIR = os.path.expanduser("~/sysstat_reports")
REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sysstat_reports")
_ANSI_RE = re.compile(r"\033\[[0-9;]*m")
_PDF_AVAILABLE = importlib.util.find_spec("fpdf") is not None  # ← chequeo sin importar fpdf2 todavía

# =============================================================
# 1.0 — HELPERS DE FORMATO Y ENTORNO
# =============================================================

def _check_unicode(config) -> bool:
    """Verifica si el entorno soporta Unicode — misma lógica que cli.py."""
    if not config.icon:
        return False
    term     = os.environ.get("TERM", "").lower()
    encoding = (sys.stdout.encoding or "").lower()
    if any(x in term for x in ["linux", "vt100", "xterm-color", "dumb", "ansi"]):
        config.icon = False
        return False
    if not encoding.startswith("utf"):
        config.icon = False
        return False
    try:
        sys.stdout.write("🔁\r\033[K")
        sys.stdout.flush()
        return True
    except Exception:
        config.icon = False
        return False

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
    _check_unicode(config)

    # ── Íconos resueltos una sola vez ────────────────────────
    ghost_icon = "   " + " " * COL_LABEL if config.icon else " " * COL_LABEL
    icon_pad   = "   " if config.icon else ""
    icon_bar   = "   " if config.icon else ""

    if config.sys:
        penguin = "🐧 " if config.icon else ""
        gear    = "⚙️  " if config.icon else ""

    if config.host:
        house  = "🏠 " if config.icon else ""
        person = "👤 " if config.icon else ""

    if config.up:
        clock     = "🕒 " if config.icon else ""
        calendar  = "📅 " if config.icon else ""
        stopwatch = "⏱️  " if config.icon else ""
        loop      = "🔄 " if config.icon else ""

    if config.cpu:
        robot     = "🔲 " if config.icon else "" # Alternativas 🤖 🎛️ 🔲
        lightning = "⚡ " if config.icon else "" # Alternatica ⚡ 🚀
        thermcpu  = "🌡️  " if config.icon else ""

    if config.ram:
        ram_icon  = "📟 " if config.icon else ""
        swap_icon = "💾 " if config.icon else ""

    if config.proc:
        puzzle = "📋 " if config.icon else ""

    if config.load:
        chart = "📊 " if config.icon else ""

    if config.disk:
        disk_icon  = "🗄️  " if config.icon else ""
        read_icon  = "📥 " if config.icon else ""
        write_icon = "📤 " if config.icon else ""
        thermdisk  = "🌡️  " if config.icon else ""

    if config.lan:
        lan_icon  = "🖧 " if config.icon else "" # Alternativas 🌐 🖧 🔌
        ldn_icon  = "⬇️  " if config.icon else ""
        lup_icon  = "⬆️  " if config.icon else ""

    if config.wifi:
        wifi_icon = "📶 " if config.icon else ""
        wifi_d    = "⬇️  " if config.icon else ""
        wifi_u    = "⬆️  " if config.icon else ""
        therm_w   = "🌡️  " if config.icon else ""

    # ── Encabezado ───────────────────────────────────────────
    # SysStat CLI/GUI v5.23.0.20260615a
    buffer.append(f"{BOLD}SysStat CLI/GUI{RESET} v{__version__}")

    # ── Sistema ───────────────────────────────────────────────
    # 🐧 OS: Linux Mint 22.3 - ⚙️  Kernel version: 7.0.0-14-generic
    if config.sys:
        d = sysstat_core.get("sys")
        buffer.append(f"{penguin}OS: {BOLD}{d['os_name']}{RESET} - {gear}Kernel version: {BOLD}{d['kernel_version']}{RESET}")

    # 🏠 Hostname: hal9001c - 👤 User: axel
    if config.host:
        d = sysstat_core.get("host")
        buffer.append(f"{house}Hostname: {BOLD}{d['hostname']}{RESET} - {person}User: {BOLD}{d['user']}{RESET}")

    # 🕒 Start: 19:26:40 15/06/26 - 📅 End: 19:58:11 15/06/26 - 🔄 Cycles: 189
    if config.up:
        up       = sysstat_core.get("up")
        start_dt = sysstat_core.get("start_datetime")
        cycles   = sysstat_core.get_count("cpu") if config.cpu else 0
        buffer.append(f"{clock}Start: {BOLD}{start_dt}{RESET} - {calendar}End: {BOLD}{up['datetime']}{RESET}")
        buffer.append(f"{stopwatch}Runtime: {BOLD}{sysstat_core.get_runtime()}{RESET} - {loop}Cycles: {BOLD}{cycles}{RESET}")

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
        buffer.append(f"{robot}{f'CPU used:':<{COL_LABEL}}"
            f"{_color_val(_color('cpu', cpu_s['min']), _pct(cpu_s['min']))} "
            f"{_color_val(_color('cpu', cpu_avg),      _pct(cpu_avg))} "
            f"{_color_val(_color('cpu', cpu_s['max']), _pct(cpu_s['max']))}"
        )

        freq_s     = sysstat_core.get_stats("cpu_freq_hz")
        freq_pct_s = sysstat_core.get_stats("cpu_freq_pct")
        buffer.append(f"{lightning}{f'CPU freq:':<{COL_LABEL}}"
            f"{_color_val(_color('cpu_freq_pct', freq_pct_s['min']), _ghz(freq_s['min']))} "
            f"{_color_val(_color('cpu_freq_pct', freq_pct_s['avg']), _ghz(freq_s['avg']))} "
            f"{_color_val(_color('cpu_freq_pct', freq_pct_s['max']), _ghz(freq_s['max']))}"
        )

        if sysstat_core.get("cpu_temp"):
            temp_s   = sysstat_core.get_stats("cpu_temp")
            temp_avg = round(temp_s["avg"])
            buffer.append(f"{thermcpu}{f'CPU temp:':<{COL_LABEL}}"
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
        buffer.append(f"{puzzle}{f'Processes:':<{COL_LABEL}}"
            f"{_color_val('', str(int(proc_s['min'])))} "
            f"{_color_val('', str(int(proc_s['avg'])))} "
            f"{_color_val('', str(int(proc_s['max'])))}"
        )

    # ── Load average ──────────────────────────────────────────
    # 📊 Load avg:    0.03          1.13          4.88
    if config.load:
        load_s = sysstat_core.get_stats("load")
        def _load_fmt(v): return f"{v:.2f}"
        buffer.append(f"{chart}{f'Load avg:':<{COL_LABEL}}"
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
        buffer.append(f"{read_icon}{f'Disk read:':<{COL_LABEL}}"
            f"{_color_val('', _mbs(read_s['min']))} "
            f"{_color_val('', _mbs(read_s['avg']))} "
            f"{_color_val('', _mbs(read_s['max']))}"
        )

        write_s = sysstat_core.get_stats("disk_write")
        buffer.append(f"{write_icon}{f'Disk write:':<{COL_LABEL}}"
            f"{_color_val('', _mbs(write_s['min']))} "
            f"{_color_val('', _mbs(write_s['avg']))} "
            f"{_color_val('', _mbs(write_s['max']))}"
        )

        if sysstat_core.get("disk_temp"):
            dtemp_s   = sysstat_core.get_stats("disk_temp")
            dtemp_avg = round(dtemp_s["avg"])
            buffer.append(f"{thermdisk}{f'Disk temp:':<{COL_LABEL}}"
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
        buffer.append(f"{ldn_icon}{f'Lan down:':<{COL_LABEL}}"
            f"{_color_val('', _mbs(down_s['min']))} "
            f"{_color_val('', _mbs(down_s['avg']))} "
            f"{_color_val('', _mbs(down_s['max']))}"
        )

        up_s = sysstat_core.get_stats("lan_up")
        buffer.append(f"{lup_icon}{f'Lan up:':<{COL_LABEL}}"
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
        buffer.append(f"{wifi_icon}{f'WiFi signal:':<{COL_LABEL}}"
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
        buffer.append(f"{wifi_d}{f'WiFi down:':<{COL_LABEL}}"
            f"{_color_val('', _mbs(down_s['min']))} "
            f"{_color_val('', _mbs(down_s['avg']))} "
            f"{_color_val('', _mbs(down_s['max']))}"
        )

        up_s = sysstat_core.get_stats("wifi_up")
        buffer.append(f"{wifi_u}{f'WiFi up:':<{COL_LABEL}}"
            f"{_color_val('', _mbs(up_s['min']))} "
            f"{_color_val('', _mbs(up_s['avg']))} "
            f"{_color_val('', _mbs(up_s['max']))}"
        )

        if sysstat_core.get_count("wifi_temp") > 0:
            wtemp_s   = sysstat_core.get_stats("wifi_temp")
            wtemp_avg = round(wtemp_s["avg"])
            buffer.append(f"{therm_w}{f'WiFi temp:':<{COL_LABEL}}"
                f"{_color_val(_color('wifi_temp', wtemp_s['min']), _temp(wtemp_s['min']))} "
                f"{_color_val(_color('wifi_temp', wtemp_avg),      _temp(wtemp_avg))} "
                f"{_color_val(_color('wifi_temp', wtemp_s['max']), _temp(wtemp_s['max']))}"
            )

    # ── Se imprime todo el informe junto, ya armado en el buffer ──
    print("\n".join(buffer))

    # ── Barra de acciones finales — Salir / Guardar TXT / Guardar LOG ─────
    # Para habilitar la opcion "(P) Save PDF" instalar la libreria fpdf2: "pip install fpdf2 --break-system-packages"
    pdf_hint = " | (P) Save PDF" if _PDF_AVAILABLE else ""
    bar_text = f"{icon_bar}{REVERSE}{DIM}(Q/X) Exit | (T) Save TXT | (L) Save LOG{pdf_hint}{RESET}"
    sys.stdout.write(bar_text)
    sys.stdout.flush()
    _wait_final_keypress(buffer)

    # 4.0 — VOLCADO DE DEBUG (DB COMPLETA)
    # Excepción consciente a la regla 6: accede directo a _stats_db porque esto
    # nunca corre en el flujo real del script — solo si descomentás la línea
    # de abajo, para curiosear/depurar.
    # _show_db_dump() # Descomentar esta linea para ver la _stats_db completa

# =============================================================
# 3.0 — GUARDADO DE ARCHIVOS Y CONTROL DE TECLADO (POST-INFORME)
# =============================================================

def _strip_ansi(text: str) -> str:
    """Remueve todos los códigos de color/estilo ANSI — usado para el TXT limpio."""
    return _ANSI_RE.sub("", text)

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

def _save_pdf(buffer):
    """Vuelca el buffer a PDF via fpdf2. Sin emojis — fuentes core son Latin-1."""
    try:
        from fpdf import FPDF
        os.makedirs(REPORTS_DIR, exist_ok=True)
        timestamp = sysstat_core.get_start_timestamp()
        filename  = f"sysstat_{timestamp}.pdf"
        filepath  = os.path.join(REPORTS_DIR, filename)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Courier", size=10)
        for line in buffer:
            clean = _strip_ansi(line).encode("latin-1", errors="ignore").decode("latin-1")
            pdf.cell(0, 5, text=clean, new_x="LMARGIN", new_y="NEXT")
        pdf.output(filepath)
        return filepath
    except Exception:
        return None

def _wait_final_keypress(buffer):
    """Espera Q/X (salir), T (guardar TXT) o L (guardar LOG). Tras guardar, sale directo."""
    import tty
    import termios
    fd           = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            rlist, _, _ = select.select([sys.stdin], [], [], 0.5)
            if not rlist:
                continue
            key = sys.stdin.read(1).lower()
            if key in ("q", "x"):
                break
            elif key == "t":
                saved_path = _save_file(buffer, "txt", strip_colors=True)
                sys.stdout.write(f"\nView: cat {saved_path}")
                break
            elif key == "l":
                saved_path = _save_file(buffer, "log", strip_colors=False)
                sys.stdout.write(f"\nView: cat {saved_path}")
                break
            elif key == "p" and _PDF_AVAILABLE:
                saved_path = _save_pdf(buffer)
                sys.stdout.write(f"\nView: xdg-open {saved_path}" if saved_path else "\nError: no se pudo generar el PDF")
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        print()

# =============================================================
# 4.0 — VOLCADO DE DEBUG (DB COMPLETA)
# =============================================================

def _show_db_dump():
    print()
    print(f"{BOLD}=== _stats_db (volcado completo) ==={RESET}")
    print(json.dumps(sysstat_core._stats_db, indent=2, default=str))
    print()
