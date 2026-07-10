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
# Version: 037
#
# =============================================

import os
import select
import subprocess
import sys
import sysstat_core
import time

# Estilos ANSI — locales a CLI
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
ITALIC  = "\033[3m"
REVERSE = "\033[7m"

def build_bar(pct: float, key: str, width: int = 33) -> str:
    """Construye una barra de progreso coloreada"""
    color  = sysstat_core.get_metric_color(key, pct)
    filled = max(0, min(width, int((pct / 100.0) * width)))
    return f"{color}{'█' * filled}{RESET}{'░' * (width - filled)}"

def build_bar_ram(ram: dict, width: int = 33) -> str:
    """Construye una barra de progreso coloreada. Especial de RAM con 3 segmentos: apps █ / sys(cache+buf) ▒ / free ░"""
    color       = ram['color']
    apps_width  = int(width * ram['apps_ratio'])
    free_width  = int(width * ram['free_ratio'])
    sys_width   = width - apps_width - free_width
    return f"{color}{'█' * apps_width}{RESET}{'▒' * sys_width}{'░' * free_width}"

def format_speed(mbps: int) -> str:
    """Convierte Mb/s a Gb/s si supera 1000, para ahorrar espacio."""
    return f"{mbps / 1000:g}Gb/s" if mbps >= 1000 else f"{mbps}Mb/s"

def play_beep():
    """Alerta sonora ante una nueva métrica en rojo. Cadena de 3 niveles, cada uno
    cae al siguiente SOLO si el comando no está instalado (FileNotFoundError):
      1. sox ('play')  → método principal, confirmado funcional en HW real
      2. beep          → alternativa via pcspkr/evdev si no hay sox
      3. bell ASCII    → último recurso nativo, sin dependencias externas
    Nota: esto NO detecta un comando instalado que falla en silencio (ej. sox sin
    placa de sonido) — Popen no bloqueante no permite chequear eso sin trabar el loop.
    Para habilitar el nivel 1 instalar sox: "sudo apt install sox".
    Para habilitar el nivel 2 instalar beep: "sudo apt install beep"."""
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

def check_unicode_support(config) -> bool:
    """Verifica si el entorno soporta Unicode.
    Esta función desactiva emojis/iconos e itálica en terminales que no los soportan —
    es el mismo diagnóstico (terminal vieja/básica) para ambos casos, así que se resuelve
    en un solo lugar en vez de repetir la detección dos veces."""
    global ITALIC
    if not config.icon:
        return False
    term     = os.environ.get("TERM", "").lower()
    encoding = (sys.stdout.encoding or "").lower()
    if any(x in term for x in ["linux", "vt100", "xterm-color", "dumb", "ansi"]):
        config.icon = False
        ITALIC = DIM
        return False
    if not encoding.startswith("utf"):
        config.icon = False
        ITALIC = DIM
        return False
    try:
        sys.stdout.write("🔁\r\033[K")
        sys.stdout.flush()
        return True
    except Exception:
        config.icon = False
        ITALIC = DIM
        return False

# =============================================================
# CONTROL DE BUCLE Y BARRA DE ESTADO
# 🔁 Run: 00:36:15 (27ms) | Cycles: 216 | 15.27MB | Next: 9/10s
# =============================================================
def draw_statusbar_and_wait(seconds, loop_icon, mute_icon, frozen_render_ms, cycle_counter, config) -> bool:
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
            status_data = sysstat_core.get_status_data(cycle_counter, config.cycles, config.interval, elapsed)
            status_line = f"{loop_icon}{DIM}{REVERSE}Run: {status_data['runtime_str']} ({frozen_render_ms}ms) | Cycles: {status_data['cycle_display']} | {status_data['mem_str']}{status_data['next_str']}{mute_icon}{RESET}"
            sys.stdout.write(f"\r{status_line}\033[K")
            sys.stdout.flush()
            ready_fds, _, _ = select.select([sys.stdin], [], [], 1)
            if ready_fds:
                key_pressed = sys.stdin.read(1).lower()
                if key_pressed in ['q', 'x']:
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

    # elapsed_wait = 0.0

    # ── Íconos resueltos una sola vez antes del bucle ────────────────────────
    # Cada grupo solo se crea si su sección NO fue omitida por el usuario (-i) y la terminal soporta unicode.
    if config.sys:
        os_name_icon = "🐧 " if config.icon else ""
        kernel_icon  = "⚙️  " if config.icon else ""

    if config.host:
        hostname_icon = "💻 " if config.icon else "" # Alternativas 🏠 💻 🖥️
        user_icon     = "🧑 " if config.icon else "" # Alternativas 👤 🧑 🧑‍🦱

    if config.up:
        uptime_icon   = "🕒 " if config.icon else "" # Alternativas 📅 🕒 ⏱️
        datetime_icon = "📅 "  if config.icon else ""

    if config.cpu:
        cpu_usage_icon = "🔳 " if config.icon else "" # Alternativas 🤖 🎛️ 🔲 🔳
        cpu_freq_icon  = "🚀 " if config.icon else "" # Alternatica ⚡ 🚀
        governor_icon  = "🎚️  " if config.icon else ""
        cpu_temp_icon  = "🌡️  " if config.icon else ""
        cpu_bar_indent = "   " if config.icon else ""

    if config.ram:
        ram_icon       = "📟 " if config.icon else "" # Alternativas 🧮 📟
        swap_icon      = "🔀 " if config.icon else "" # Alternativas 💾 🔀
        ram_bar_indent = "   " if config.icon else ""

    if config.proc:
        proc_icon = "📋 " if config.icon else "" # Alternativas 🧩 📋

    if config.load:
        load_icon = "📊 " if config.icon else ""

    if config.disk:
        disk_icon       = "🗄️  " if config.icon else ""
        disk_read_icon  = "📥 " if config.icon else ""
        disk_write_icon = "📤 " if config.icon else ""
        disk_temp_icon  = "🌡️  " if config.icon else ""
        disk_bar_indent = "   " if config.icon else ""

    if config.lan:
        lan_icon      = "🖧  " if config.icon else "" # Alternativas 🌐 🖧 🔌
        lan_down_icon = "⬇️  " if config.icon else ""
        lan_up_icon   = "⬆️  " if config.icon else ""

    if config.wifi:
        wifi_ip_icon     = "🗼 " if config.icon else ""
        wifi_signal_icon = "🛜 " if config.icon else "" # Alternativas 🛜 📶
        wifi_down_icon   = "⬇️  " if config.icon else ""
        wifi_up_icon     = "⬆️  " if config.icon else ""
        wifi_temp_icon   = "🌡️  " if config.icon else ""
        wifi_bar_indent  = "   " if config.icon else ""

    if config.bat:
        bat_icon       = "🔋 " if config.icon else ""
        bat_bar_indent = "   " if config.icon else ""

    if is_looping:
        loop_icon = "🔁 " if config.icon else ""
        mute_icon = " 🔇" if config.icon and not config.beep else ""

    # Rojos del ciclo anterior — para detectar SOLO transiciones a rojo (no repetir beep)
    prev_red_keys = set()

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

            output_lines = []  # ← Buffer: acumula todas las líneas, se vuelcan en un solo write (anti-parpadeo)

            # =============================================================
            # SYSTEM — OS y kernel
            # 🐧 OS: Linux Mint 22.3 - ⚙️ Kernel version: 7.0.0-14-generic
            # =============================================================
            if config.sys:
                sysstat_core.sys_update()
                sys_data = sysstat_core.get("sys")
                output_lines.append(f"{os_name_icon}OS: {BOLD}{sys_data['os_name']}{RESET} - {kernel_icon}Kernel version: {BOLD}{sys_data['kernel_version']}{RESET}")

            # =============================================================
            # HOST — hostname y usuario
            # 🏠 Hostname: hal9001c - 👤 User: axel
            # =============================================================
            if config.host:
                sysstat_core.host_update()
                host_data = sysstat_core.get("host")
                output_lines.append(f"{hostname_icon}Hostname: {BOLD}{host_data['hostname']}{RESET} - {user_icon}User: {BOLD}{host_data['user']}{RESET}")

            # =============================================================
            # UPTIME — tiempo de actividad y fecha/hora
            # 🕒 Uptime: 1d 12:56:33 - 📅 Time and date: 22:36:40 10/06/26
            # =============================================================
            if config.up:
                sysstat_core.uptime_update()
                uptime_data = sysstat_core.get("up")
                output_lines.append(f"{uptime_icon}Uptime: {BOLD}{uptime_data['uptime']}{RESET} - {datetime_icon}Time and date: {BOLD}{uptime_data['datetime']}{RESET}")

            # =============================================================
            # CPU — uso, frecuencia, temperatura
            # 🔲 CPU used: 12% (CPU0: 12% - CPU1: 12% - CPU2: 12% - CPU3: 13%)
            # ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
            # ⚡ CPU frequency: 0.80GHz (CPU0,1,2,3) - 🎚️ Scaling governor: powersave
            # ████████░░░░░░░░░░░░░░░░░░░░░░░░
            # 🌡️ CPU temperature: 36°C
            # =============================================================
            if config.cpu:
                sysstat_core.cpu_update()
                cpu_data      = sysstat_core.get("cpu")
                cpu_freq_hz   = sysstat_core.get("cpu_freq_hz")
                cpu_freq_ghz  = f"{cpu_freq_hz['hz'] / 1_000_000:.2f}"
                cpu_freq_pct  = sysstat_core.get("cpu_freq_pct")
                cpu_temp_data = sysstat_core.get("cpu_temp")

                if config.cpun:
                    cores_str = " - ".join(
                        f"{ITALIC}{i}:{RESET} {sysstat_core.get_metric_color('cpu', u)}{BOLD}{u}%{RESET}"
                        for i, u in enumerate(cpu_data['cores'])
                    )
                    output_lines.append(f"{cpu_usage_icon}CPU used: {cpu_data['color']}{BOLD}{cpu_data['avg']}%{RESET} ({cores_str})")
                else:
                    output_lines.append(f"{cpu_usage_icon}CPU used: {cpu_data['color']}{BOLD}{cpu_data['avg']}%{RESET}")
                if config.bar and config.barc:
                    output_lines.append(f"{cpu_bar_indent}{build_bar(cpu_data['avg'], 'cpu')}")

                # Arma "(2)" o "(0,2,3)" segun cuantos cores esten al maximo
                cores_tag = f" ({ITALIC}" + ",".join(str(i) for i in cpu_freq_hz['cores_at_max']) + f"{RESET})" if config.cpun else ""

                output_lines.append(f"{cpu_freq_icon}CPU frequency: {cpu_freq_pct['color']}{BOLD}{cpu_freq_ghz}GHz{RESET}{cores_tag} - {governor_icon}Scaling governor: {BOLD}{cpu_freq_hz['governor']}{RESET}")
                if config.bar and config.barf:
                    output_lines.append(f"{cpu_bar_indent}{build_bar(cpu_freq_pct['pct'], 'cpu_freq_pct')}")

                if cpu_temp_data:
                    output_lines.append(f"{cpu_temp_icon}CPU temperature: {cpu_temp_data['color']}{BOLD}{cpu_temp_data['temp']}°C{RESET}")

            # =============================================================
            # RAM / SWAP — uso de memoria
            # 📟 RAM used: 53% (8.16GB / 15.49GB) - 💾 Swap used: 0% (0.00GB / 0.00GB)
            # ████████████████▒▒▒▒▒▒▒▒▒▒░░░░░░ - ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
            # =============================================================
            if config.ram:
                sysstat_core.ram_update()
                ram_data  = sysstat_core.get("ram")
                swap_data = sysstat_core.get("swap")

                ram_used_gb   = f"{ram_data['used_kb']  / 1_048_576:.2f}"
                ram_total_gb  = f"{sysstat_core.get('ram_hw')['total_kb'] / 1_048_576:.2f}"
                swap_used_gb  = f"{swap_data['used_kb']  / 1_048_576:.2f}"
                swap_total_gb = f"{swap_data['total_kb'] / 1_048_576:.2f}"

                output_lines.append(f"{ram_icon}RAM used: {ram_data['color']}{BOLD}{ram_data['pct']}%{RESET} ({BOLD}{ram_used_gb}GB{RESET}/{BOLD}{ram_total_gb}GB{RESET}) - {swap_icon}Swap used: {swap_data['color']}{BOLD}{swap_data['pct']}%{RESET} ({BOLD}{swap_used_gb}GB{RESET}/{BOLD}{swap_total_gb}GB{RESET})")
                if config.bar and config.barr:
                    output_lines.append(f"{ram_bar_indent}{build_bar_ram(ram_data)} - {build_bar(swap_data['pct'], 'swap')}")

            # =============================================================
            # PROCESSES — conteo y estados de procesos (Jerarquía de Hilos)
            # 📋 Processes: 346 (T: 1386 - R: 2 - D: 0 - S: 1384)
            # =============================================================
            if config.proc:
                sysstat_core.proc_update()
                proc_data = sysstat_core.get("proc")

                output_lines.append(f"{proc_icon}Processes: {BOLD}{proc_data['total']}{RESET} "
                      f"({ITALIC}T: {RESET}{BOLD}{proc_data['threads']}{RESET} - "
                      f"{ITALIC}R: {RESET}{BOLD}{proc_data['running']}{RESET} - "
                      f"{ITALIC}D: {RESET}{BOLD}{proc_data['disk_sleep']}{RESET} - "
                      f"{ITALIC}S: {RESET}{BOLD}{proc_data['sleeping']}{RESET})")

            # =============================================================
            # LOAD AVERAGE — carga del sistema
            # 📊 Load average: 0.45 0.32 0.28
            # =============================================================
            if config.load:
                sysstat_core.load_update()
                load_data = sysstat_core.get("load")
                output_lines.append(f"{load_icon}Load average: "
                      f"{load_data['color1']}{BOLD}{load_data['load1']:.2f}{RESET} "
                      f"{load_data['color5']}{BOLD}{load_data['load5']:.2f}{RESET} "
                      f"{load_data['color15']}{BOLD}{load_data['load15']:.2f}{RESET}")

            # =============================================================
            # DISK — uso, velocidad I/O y temperatura
            # 🗄️ Disk used: 55% (258.92GB/467.91GB) - 📥 R: 0.00MB/s - 📤 W: 0.17MB/s
            # █████████████████░░░░░░░░░░░░░░░
            # 🌡️ Disk temperature: 33°C
            # =============================================================
            if config.disk:
                sysstat_core.disk_update()
                disk_data = sysstat_core.get("disk")

                disk_used_gb  = f"{disk_data['used_kb']  / 1_048_576:.2f}"
                disk_total_gb = f"{disk_data['total_kb'] / 1_048_576:.2f}"

                output_lines.append(f"{disk_icon}Disk used: {disk_data['color']}{BOLD}{disk_data['pct']}%{RESET} ({BOLD}{disk_used_gb}GB{RESET}/{BOLD}{disk_total_gb}GB{RESET}) - {disk_read_icon}R: {BOLD}{disk_data['read_speed']:.2f}MB/s{RESET} - {disk_write_icon}W: {BOLD}{disk_data['write_speed']:.2f}MB/s{RESET}")
                if config.bar and config.bard:
                    output_lines.append(f"{disk_bar_indent}{build_bar(disk_data['pct'], 'disk_used_pct')}")

                disk_temp_data = sysstat_core.get("disk_temp")
                if disk_temp_data:
                    output_lines.append(f"{disk_temp_icon}Disk temperature: {disk_temp_data['color']}{BOLD}{disk_temp_data['temp']}°C{RESET}")

            # =============================================================
            # LAN — IP, velocidad, duplex e I/O (placa cableada)
            # 🖧 LAN IP: 192.168.0.117 - Spd: 100Mb/s(F) - ⬇️ D: 0.00MB/s - ⬆️ U: 0.00MB/s
            # =============================================================
            if config.lan:
                sysstat_core.lan_update()
                lan_data = sysstat_core.get("lan")
                if lan_data:
                    speed_str = format_speed(lan_data['speed'])
                    output_lines.append(f"{lan_icon}LAN IP: {BOLD}{lan_data['ip']}{RESET} - Spd: {BOLD}{speed_str}({lan_data['duplex']}){RESET} - {lan_down_icon}D: {BOLD}{lan_data['down']:.2f}MB/s{RESET} - {lan_up_icon}U: {BOLD}{lan_data['up']:.2f}MB/s{RESET}")

            # =============================================================
            # WIFI — IP, SSID, señal, velocidad I/O y temperatura
            # 🗼 WiFi IP: 192.168.0.208 - SSID: OBRIEN 5
            # 📶 WiFi signal: 54% - Spd: 117.00Mb/s - ⬇️ D: 0.01MB/s - ⬆️ U: 0.00MB/s
            #    ████████████████░░░░░░░░░░░░░░░░░
            # 🌡️ WiFi temperature: 43°C
            # =============================================================
            if config.wifi:
                sysstat_core.wifi_update()
                wifi_data = sysstat_core.get("wifi")
                if wifi_data:
                    output_lines.append(f"{wifi_ip_icon}WiFi IP: {BOLD}{wifi_data['ip']}{RESET} - SSID: {BOLD}{wifi_data['ssid']}{RESET}")
                    output_lines.append(f"{wifi_signal_icon}WiFi signal: {wifi_data['color']}{BOLD}{wifi_data['signal']}%{RESET} - Spd: {BOLD}{wifi_data['speed']:.2f}Mb/s{RESET} - {wifi_down_icon}D: {BOLD}{wifi_data['down']:.2f}MB/s{RESET} - {wifi_up_icon}U: {BOLD}{wifi_data['up']:.2f}MB/s{RESET}")
                    if config.bar and config.barw:
                        output_lines.append(f"{wifi_bar_indent}{build_bar(wifi_data['signal'], 'wifi')}")

                    wifi_temp_data = sysstat_core.get("wifi_temp")
                    if wifi_temp_data:
                        output_lines.append(f"{wifi_temp_icon}WiFi temperature: {wifi_temp_data['color']}{BOLD}{wifi_temp_data['temp']}°C{RESET}")

            # =============================================================
            # BATTERY — porcentaje, tiempo restante y estado
            # 🔋 Battery: 86% - Time: 3h 45m - Mode: Discharging
            # ████████████████████████████░░░░
            # =============================================================
            if config.bat:
                sysstat_core.bat_update()
                bat_data = sysstat_core.get("bat")
                if bat_data:
                    time_part = f" - Time: {BOLD}{bat_data['time_str']}{RESET}" if bat_data['time_str'] else ""
                    output_lines.append(f"{bat_icon}Battery: {bat_data['color']}{BOLD}{bat_data['percent']}%{RESET}{time_part} - Mode: {BOLD}{bat_data['state']}{RESET}")
                    if config.bar and config.bart:
                        output_lines.append(f"{bat_bar_indent}{build_bar(bat_data['percent'], 'bat')}")

            # =============================================================
            # BEEP — alerta sonora ante nuevas métricas en rojo
            # Un solo beep por ciclo, sin importar cuántas métricas entraron en rojo juntas.
            # Si ya estaba en rojo el ciclo anterior, no vuelve a sonar.
            # =============================================================
            if config.beep:
                current_red_keys = set()
                if config.cpu:
                    if cpu_data['color'] == sysstat_core.RED: current_red_keys.add('cpu')
                    if cpu_freq_pct['color'] == sysstat_core.RED: current_red_keys.add('cpu_freq')
                    if cpu_temp_data and cpu_temp_data['color'] == sysstat_core.RED: current_red_keys.add('cpu_temp')
                if config.ram:
                    if ram_data['color'] == sysstat_core.RED: current_red_keys.add('ram')
                    if swap_data['color'] == sysstat_core.RED: current_red_keys.add('swap')
                if config.load:
                    if load_data['color1'] == sysstat_core.RED: current_red_keys.add('load')
                if config.disk:
                    if disk_data['color'] == sysstat_core.RED: current_red_keys.add('disk')
                    if disk_temp_data and disk_temp_data['color'] == sysstat_core.RED: current_red_keys.add('disk_temp')
                if config.wifi and wifi_data:
                    if wifi_data['color'] == sysstat_core.RED: current_red_keys.add('wifi')
                    if wifi_temp_data and wifi_temp_data['color'] == sysstat_core.RED: current_red_keys.add('wifi_temp')
                if config.bat and bat_data:
                    if bat_data['color'] == sysstat_core.RED: current_red_keys.add('bat')

                if current_red_keys - prev_red_keys:
                    play_beep()
                prev_red_keys = current_red_keys

            # ── Volcado único a pantalla — anti-parpadeo ──────────────────
            # \033[H mueve el cursor a home (NO borra, evita el flash negro).
            # \033[K al final de cada línea limpia restos de la pasada anterior
            # si la línea nueva es más corta (ej: SSID que cambió de largo).
            if is_looping:
                screen = "\033[H" + "\033[K\n".join(output_lines) + "\033[K\n\033[J"
                sys.stdout.write(screen)
                sys.stdout.flush()
            else:
                print("\n".join(output_lines))

            # =============================================================
            # CONTROL DE BUCLE Y BARRA DE ESTADO
            # 🔁 Run: 00:36:15 (27ms) | Cycles: 216 | 15.27MB | Next: 9/10s
            # =============================================================
            if is_looping:
                status_data      = sysstat_core.get_status_data(cycle_counter, config.cycles, config.interval, 0)
                frozen_render_ms = status_data['render_ms']

            if not loop_active:
                break

            if draw_statusbar_and_wait(config.interval, loop_icon, mute_icon, frozen_render_ms, cycle_counter, config):
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
