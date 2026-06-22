#!/usr/bin/env python3
# 
# SysStat (System Status) - CLI
# 
# Autor: Axel O'BRIEN (LiGNUxMan) axelobrien@gmail.com
# 
# Colaboradores: ChatGPT (OpenAI) · Gemini/Antigravity (Google) · Claude (Anthropic)
#
# =========================================
# sysstat_cli.py - INTERFAZ DEL USUARIO CLI
# =========================================
#
# Version: 022
#
# =============================================

import os
import select
import sys
import sysstat_core
import time

# Estilos ANSI — locales a CLI
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
ITALIC  = "\033[3m" if os.environ.get("TERM", "") not in ("linux", "dumb") else "\033[2m"
REVERSE = "\033[7m"

def check_unicode_support(config) -> bool:
    """Verifica si el entorno soporta Unicode."""
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

def build_bar(pct: float, key: str, width: int = 32) -> str:
    """Construye una barra de progreso coloreada"""
    color  = sysstat_core.get_metric_color(key, pct)
    filled = max(0, min(width, int((pct / 100.0) * width)))
    return f"{color}{'█' * filled}{'░' * (width - filled)}{RESET}"

def build_bar_ram(ram: dict, width: int = 32) -> str:
    """Construye una barra de progreso coloreada. Especial de RAM con 3 segmentos: apps █ / sys(cache+buf) ▒ / free ░"""
    color = ram['color']
    apps  = int(width * ram['apps_ratio'])
    free  = int(width * ram['free_ratio'])
    sys_b = width - apps - free
    return f"{color}{'█' * apps}{'▒' * sys_b}{'░' * free}{RESET}"

def format_speed(mbps: int) -> str:
    """Convierte Mb/s a Gb/s si supera 1000, para ahorrar espacio."""
    return f"{mbps / 1000:g}Gb/s" if mbps >= 1000 else f"{mbps}Mb/s"

# =============================================================
# CONTROL DE BUCLE Y BARRA DE ESTADO
# 🔁 Run: 00:36:15 (27ms) | Cycles: 216 | 15.27MB | Next: 9/10s
# =============================================================
def draw_statusbar_and_wait(seconds, indicator, frozen_render_ms, cycle_counter, config) -> bool:
    """Espera el intervalo redibujando la status bar una vez por segundo.
    Retorna True si el usuario pidió salir con Q o X."""
    import tty
    import termios
    fd           = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        start_wait = time.time()
        while True:
            elapsed = time.time() - start_wait
            if elapsed >= seconds:
                break
            # Redibuja la status bar una vez por segundo
            sb   = sysstat_core.get_status_data(cycle_counter, config.cycles, config.interval, elapsed)
            line = f"{indicator}{DIM}{REVERSE}Run: {sb['runtime_str']} ({frozen_render_ms}ms) | Cycles: {sb['cycle_display']} | {sb['mem_str']}{sb['next_str']}{RESET}"
            sys.stdout.write(f"\r{line}\033[K")
            sys.stdout.flush()
            rlist, _, _ = select.select([sys.stdin], [], [], 1)
            if rlist:
                char = sys.stdin.read(1).lower()
                if char in ['q', 'x']:
                    return True
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return False

def start_cli(config):
    """Lógica principal de dibujo y control del bucle CLI."""

    check_unicode_support(config)  # ← faltaba: por esto config.icon no se ajustaba en tty1

    loop_active, cycle_counter = sysstat_core.setup_cycle_control(config)
    is_looping = config.interval is not None or config.cycles is not None

    # Llama a todos los x_init de sysstat_core.py
    sysstat_core.hardware_init(config)

    elapsed_wait = 0.0

    # ── Íconos resueltos una sola vez antes del bucle ────────────────────────
    # Cada grupo solo se crea si su sección NO fue omitida por el usuario (-i) y la terminal soporta unicode.
    if config.sys:
        penguin  = "🐧 " if config.icon else ""
        gear = "⚙️  " if config.icon else ""

    if config.host:
        house  = "🏠 " if config.icon else ""
        person = "👤 " if config.icon else ""

    # 📅🕒🕒⏱️
    if config.up:
        stopwatch = "🕒 " if config.icon else ""
        clock     = "📅 "  if config.icon else ""

    if config.cpu:
        robot      = "🔲 " if config.icon else "" # Alternativas 🤖 🎛️ 🔲
        lightning  = "⚡ " if config.icon else "" # Alternatica ⚡ 🚀
        gauge      = "🎚️  " if config.icon else ""
        thermcpu   = "🌡️  " if config.icon else ""
        bar_indent_c = "   " if config.icon else ""

    if config.ram:
        ram_icon  = "📟 " if config.icon else ""
        swap_icon = "💾 " if config.icon else ""
        bar_indent_r = "   " if config.icon else ""

    if config.proc:
        puzzle = "📋 " if config.icon else ""

    if config.load:
        chart = "📊 " if config.icon else ""

    if config.disk:
        disk_icon  = "🗄️  " if config.icon else ""
        read_icon  = "📥 " if config.icon else ""
        write_icon = "📤 " if config.icon else ""
        thermdisk  = "🌡️  " if config.icon else ""
        bar_indent_d = "   " if config.icon else ""

    if config.lan:
        lan_icon  = "🖧 " if config.icon else "" # Alternativas 🌐 🖧 🔌
        ldn_icon  = "⬇️  " if config.icon else ""
        lup_icon  = "⬆️  " if config.icon else ""

    if config.wifi:
        wifi_icon    = "🗼 " if config.icon else ""
        signal_icon  = "📶 " if config.icon else ""
        wifi_down    = "⬇️  " if config.icon else ""
        wifi_up      = "⬆️  " if config.icon else ""
        thermwifi    = "🌡️  " if config.icon else ""
        bar_indent_w = "   " if config.icon else ""

    if is_looping:
        indicator = "🔁 " if config.icon else ""

    # ── Configuración del terminal para modo bucle ───────────────────────────
    if is_looping:
        import tty
        import termios
        fd           = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        sys.stdout.write("\033[?25l\033[2J\033[H")
        sys.stdout.flush()

    try:
        while True:
            if is_looping:
                sysstat_core.start_render_timer()

            out = []  # ← Buffer: acumula todas las líneas, se vuelcan en un solo write (anti-parpadeo)

            # =============================================================
            # SYSTEM — OS y kernel
            # 🐧 OS: Linux Mint 22.3 - ⚙️ Kernel version: 7.0.0-14-generic
            # =============================================================
            if config.sys:
                sysstat_core.sys_update()
                sys_data = sysstat_core.get("sys")
                out.append(f"{penguin}OS: {BOLD}{sys_data['os_name']}{RESET} - {gear}Kernel version: {BOLD}{sys_data['kernel_version']}{RESET}")

            # =============================================================
            # HOST — hostname y usuario
            # 🏠 Hostname: hal9001c - 👤 User: axel
            # =============================================================
            if config.host:
                sysstat_core.host_update()
                host_data = sysstat_core.get("host")
                out.append(f"{house}Hostname: {BOLD}{host_data['hostname']}{RESET} - {person}User: {BOLD}{host_data['user']}{RESET}")

            # =============================================================
            # UPTIME — tiempo de actividad y fecha/hora
            # 🕒 Uptime: 1d 12:56:33 - 📅 Time and date: 22:36:40 10/06/26
            # =============================================================
            if config.up:
                sysstat_core.uptime_update()
                up = sysstat_core.get("up")
                out.append(f"{stopwatch}Uptime: {BOLD}{up['uptime']}{RESET} - {clock}Time and date: {BOLD}{up['datetime']}{RESET}")

            # =============================================================
            # CPU — uso, frecuencia, temperatura
            # 🎛️ CPU used: 12% (CPU0: 12% - CPU1: 12% - CPU2: 12% - CPU3: 13%)
            # ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
            # ⚡ CPU frequency: 0.80GHz (CPU0,1,2,3) - 🎚️ Scaling governor: powersave
            # ████████░░░░░░░░░░░░░░░░░░░░░░░░
            # 🌡️ CPU temperature: 36°C
            # =============================================================
            if config.cpu:
                sysstat_core.cpu_update()
                cpu      = sysstat_core.get("cpu")
                cpu_freq_hz = sysstat_core.get("cpu_freq_hz")
                cpu_freq_ghz = f"{cpu_freq_hz['hz'] / 1_000_000:.2f}"
                cpu_freq_pct = sysstat_core.get("cpu_freq_pct")
                cpu_temp = sysstat_core.get("cpu_temp")

                if config.cpun:
                    cores_str = " - ".join(
                        f"{ITALIC}CPU{i}:{RESET} {sysstat_core.get_metric_color('cpu', u)}{BOLD}{u}%{RESET}"
                        for i, u in enumerate(cpu['cores'])
                    )
                    out.append(f"{robot}CPU used: {cpu['color']}{BOLD}{cpu['avg']}%{RESET} ({cores_str})")
                else:
                    out.append(f"{robot}CPU used: {cpu['color']}{BOLD}{cpu['avg']}%{RESET}")
                if config.bar and config.barc:
                    out.append(f"{bar_indent_c}{build_bar(cpu['avg'], 'cpu')}")

                # Arma "(CPU2)" o "(CPU0,2,3)" segun cuantos cores esten al maximo
                cores_tag = f" ({ITALIC}CPU" + ",".join(str(i) for i in cpu_freq_hz['cores_at_max']) + f"{RESET})" if config.cpun else ""

                out.append(f"{lightning}CPU frequency: {cpu_freq_pct['color']}{BOLD}{cpu_freq_ghz}GHz{RESET}{cores_tag} - {gauge}Scaling governor: {BOLD}{cpu_freq_hz['governor']}{RESET}")
                if config.bar and config.barf:
                    out.append(f"{bar_indent_c}{build_bar(cpu_freq_pct['pct'], 'cpu_freq_pct')}")

                if cpu_temp:
                    out.append(f"{thermcpu}CPU temperature: {cpu_temp['color']}{BOLD}{cpu_temp['temp']}°C{RESET}")

            # =============================================================
            # RAM / SWAP — uso de memoria
            # 📟 RAM used: 53% (8.16GB / 15.49GB) - 💾 Swap used: 0% (0.00GB / 0.00GB)
            # ████████████████▒▒▒▒▒▒▒▒▒▒░░░░░░ - ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
            # =============================================================
            if config.ram:
                sysstat_core.ram_update()
                ram  = sysstat_core.get("ram")
                swap = sysstat_core.get("swap")

                ram_used_gb  = f"{ram['used_kb']  / 1_048_576:.2f}"
                ram_total_gb = f"{ram['total_kb'] / 1_048_576:.2f}"
                swap_used_gb  = f"{swap['used_kb']  / 1_048_576:.2f}"
                swap_total_gb = f"{swap['total_kb'] / 1_048_576:.2f}"

                out.append(f"{ram_icon}RAM used: {ram['color']}{BOLD}{ram['pct']}%{RESET} ({BOLD}{ram_used_gb}GB{RESET}/{BOLD}{ram_total_gb}GB{RESET}) - {swap_icon}Swap used: {swap['color']}{BOLD}{swap['pct']}%{RESET} ({BOLD}{swap_used_gb}GB{RESET}/{BOLD}{swap_total_gb}GB{RESET})")
                if config.bar and config.barr:
                    out.append(f"{bar_indent_r}{build_bar_ram(ram)} - {build_bar(swap['pct'], 'swap')}")

            # =============================================================
            # PROCESSES — conteo y estados de procesos (Jerarquía de Hilos)
            # 📋 Processes: 346 (T: 1386 - R: 2 - D: 0 - S: 1384)
            # =============================================================
            if config.proc:
                sysstat_core.proc_update()
                p = sysstat_core.get("proc")
                
                out.append(f"{puzzle}Processes: {BOLD}{p['total']}{RESET} "
                      f"({ITALIC}T: {RESET}{BOLD}{p['threads']}{RESET} - "
                      f"{ITALIC}R: {RESET}{BOLD}{p['running']}{RESET} - "
                      f"{ITALIC}D: {RESET}{BOLD}{p['disk_sleep']}{RESET} - "
                      f"{ITALIC}S: {RESET}{BOLD}{p['sleeping']}{RESET})")

            # =============================================================
            # LOAD AVERAGE — carga del sistema
            # 📊 Load average: 0.45 0.32 0.28
            # =============================================================
            if config.load:
                sysstat_core.load_update()
                ld = sysstat_core.get("load")
                out.append(f"{chart}Load average: "
                      f"{ld['color1']}{BOLD}{ld['load1']:.2f}{RESET} "
                      f"{ld['color5']}{BOLD}{ld['load5']:.2f}{RESET} "
                      f"{ld['color15']}{BOLD}{ld['load15']:.2f}{RESET}")

            # =============================================================
            # DISK — uso, velocidad I/O y temperatura
            # 🗄️ Disk used: 55% (258.92GB/467.91GB) - 📥 R: 0.00MB/s - 📤 W: 0.17MB/s
            # █████████████████░░░░░░░░░░░░░░░
            # 🌡️ Disk temperature: 33°C
            # =============================================================
            if config.disk:
                sysstat_core.disk_update()
                disk = sysstat_core.get("disk")

                disk_used_gb  = f"{disk['used_kb']  / 1_048_576:.2f}"
                disk_total_gb = f"{disk['total_kb'] / 1_048_576:.2f}"

                out.append(f"{disk_icon}Disk used: {disk['color']}{BOLD}{disk['pct']}%{RESET} ({BOLD}{disk_used_gb}GB{RESET}/{BOLD}{disk_total_gb}GB{RESET}) - {read_icon}R: {BOLD}{disk['read_speed']:.2f}MB/s{RESET} - {write_icon}W: {BOLD}{disk['write_speed']:.2f}MB/s{RESET}")
                if config.bar and config.bard:
                    out.append(f"{bar_indent_d}{build_bar(disk['pct'], 'disk_used_pct')}")

                disk_temp = sysstat_core.get("disk_temp")
                if disk_temp:
                    out.append(f"{thermdisk}Disk temperature: {disk_temp['color']}{BOLD}{disk_temp['temp']}°C{RESET}")

            # =============================================================
            # LAN — IP, velocidad, duplex e I/O (placa cableada)
            # 🌐 LAN IP: 192.168.0.117 - Spd: 100Mb/s(F) - ⬇️ D: 0.00MB/s - ⬆️ U: 0.00MB/s
            # =============================================================
            if config.lan:
                sysstat_core.lan_update()
                lan = sysstat_core.get("lan")
                if lan:
                    speed_str = format_speed(lan['speed'])
                    out.append(f"{lan_icon}LAN IP: {BOLD}{lan['ip']}{RESET} - Spd: {BOLD}{speed_str}({lan['duplex']}){RESET} - {ldn_icon}D: {BOLD}{lan['down']:.2f}MB/s{RESET} - {lup_icon}U: {BOLD}{lan['up']:.2f}MB/s{RESET}")

            # =============================================================
            # WIFI — IP, SSID, señal, velocidad I/O y temperatura
            # 🗼 WiFi IP: 192.168.0.208 - SSID: OBRIEN 5
            # 📶 WiFi signal: 54% - Spd: 117.00Mb/s - ⬇️ D: 0.01MB/s - ⬆️ U: 0.00MB/s
            #    ████████████████░░░░░░░░░░░░░░░░░
            # 🌡️ WiFi temperature: 43°C
            # =============================================================
            if config.wifi:
                sysstat_core.wifi_update()
                wifi = sysstat_core.get("wifi")
                if wifi:
                    out.append(f"{wifi_icon}WiFi IP: {BOLD}{wifi['ip']}{RESET} - SSID: {BOLD}{wifi['ssid']}{RESET}")
                    out.append(f"{signal_icon}WiFi signal: {wifi['color']}{BOLD}{wifi['signal']}%{RESET} - Spd: {BOLD}{wifi['speed']:.2f}Mb/s{RESET} - {wifi_down}D: {BOLD}{wifi['down']:.2f}MB/s{RESET} - {wifi_up}U: {BOLD}{wifi['up']:.2f}MB/s{RESET}")
                    if config.bar and config.barw:
                        out.append(f"{bar_indent_w}{build_bar(wifi['signal'], 'wifi')}")

                    wifi_temp = sysstat_core.get("wifi_temp")
                    if wifi_temp:
                        out.append(f"{thermwifi}WiFi temperature: {wifi_temp['color']}{BOLD}{wifi_temp['temp']}°C{RESET}")

            # ── Volcado único a pantalla — anti-parpadeo ──────────────────
            # \033[H mueve el cursor a home (NO borra, evita el flash negro).
            # \033[K al final de cada línea limpia restos de la pasada anterior
            # si la línea nueva es más corta (ej: SSID que cambió de largo).
            if is_looping:
                screen = "\033[H" + "\033[K\n".join(out) + "\033[K\n\033[J"
                sys.stdout.write(screen)
                sys.stdout.flush()
            else:
                print("\n".join(out))

            # =============================================================
            # CONTROL DE BUCLE Y BARRA DE ESTADO
            # 🔁 Run: 00:36:15 (27ms) | Cycles: 216 | 15.27MB | Next: 9/10s
            # =============================================================
            if is_looping:
                metrics          = sysstat_core.get_status_data(cycle_counter, config.cycles, config.interval, 0)
                frozen_render_ms = metrics['render_ms']

            if not loop_active:
                break

            if draw_statusbar_and_wait(config.interval, indicator, frozen_render_ms, cycle_counter, config):
                break

            if config.cycles is None:
                cycle_counter += 1
            else:
                cycle_counter -= 1
                if cycle_counter <= 0:
                    break

    except KeyboardInterrupt:
        pass
    finally:
        if is_looping:
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
