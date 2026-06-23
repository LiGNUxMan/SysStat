#!/usr/bin/env python3
# 
# SysStat (System Status) Version 3.47.4.20260604ia
# 
# Autor: Axel O'BRIEN (LiGNUxMan) axelobrien@gmail.com
# 
# Colaboradores: ChatGPT - Google Gemini
#

import argparse
import os
import psutil
import re
import termios
import tty
import select
import socket
import subprocess
import sys
import time
from datetime import timedelta

# =====================================================================
# 1.0_init_and_config - INICIALIZACIÓN, ENTORNO Y HARDWARE
# =====================================================================
# Define constantes, colores ANSI, variables de caché global y ejecuta
# detect_hardware(). Establece el "suelo" base del script.

ICON_PAPIRUS_NAME = "sysstat_icon_papirus.png"
ICON_STANDARD_NAME = "sysstat_icon.png"

OS_INFO_PATH = "/etc/os-release"
OS_RELEASE_PATH = "/proc/sys/kernel/osrelease"

CPU_FREQ_PATH = None
CPU_FREQ_MIN_PATH = None
CPU_FREQ_MAX_PATH = None
CPU_FREQ_CUR_PATH = None
CPU_GOVERNOR_PATH = None

CPU_SYS_PATH = "/sys/devices/system/cpu"

MEMINFO_PATH = "/proc/meminfo"

PROC_PATH = "/proc"

BATTERY_PATH = None
POWER_SUPPLY_PATH = "/sys/class/power_supply"

CPU_TEMP_SENSOR = None
CPU_TEMP_INDEX = 0
NVME_TEMP_SENSOR = None
NVME_TEMP_LABEL = None
WIFI_TEMP_SENSOR = None

# Variables para métricas
cpu_times_start = None
cpu_time_start = None
disk_io_start = None
disk_time_start = None
lan_io_start = None
lan_time_start = None
lan_last_iface = None
wifi_io_start = None
wifi_time_start = None
wifi_last_iface = None

# Variables para promedios, mínimos y máximos (acumuladores para GUI)
promedios_db = {
    "cpu": {"sum": 0.0, "count": 0, "min": None, "max": None},
    "freq": {"sum": 0.0, "count": 0, "min": None, "max": None},
    "ram": {"sum": 0.0, "count": 0, "min": None, "max": None},
    "swap": {"sum": 0.0, "count": 0, "min": None, "max": None},
    "disk": {"sum": 0.0, "count": 0, "min": None, "max": None},
    "wifi": {"sum": 0.0, "count": 0, "min": None, "max": None},
    "bat": {"sum": 0.0, "count": 0, "min": None, "max": None}
}

# Diccionario estático para congelar el ÚLTIMO valor porcentual enviado a las barras gráficas
ultimos_valores_gui = {
    "cpu": 0.0,
    "freq": 0.0,
    "ram": 0.0,
    "swap": 0.0,
    "disk": 0.0,
    "wifi": 0.0,
    "bat": 0.0
}

def update_promedio(key, value):
    if value is not None:
        db = proredios_db = promedios_db[key]
        db["sum"] += value
        db["count"] += 1
        if db["min"] is None or value < db["min"]:
            db["min"] = value
        if db["max"] is None or value > db["max"]:
            db["max"] = value

def get_promedio(key):
    db = promedios_db.get(key)
    if not db or db["count"] == 0:
        return None
    return db["sum"] / db["count"]

def get_min_metric(key):
    db = promedios_db.get(key)
    return db["min"] if db else None

def get_max_metric(key):
    db = promedios_db.get(key)
    return db["max"] if db else None

def get_metric_color(key, value, max_freq=None):
    if value is None:
        return RESET
    if key == "cpu":
        ru = round(value)
        if ru > 99: return RED
        if ru > 66: return ORANGE
        if ru > 33: return YELLOW
        return RESET
    elif key == "freq":
        # Lógica exacta basada puramente en el porcentaje (0-100%)
        if value >= 100.0: return RED
        if value > 80.0: return ORANGE
        if value > 25.0: return YELLOW
        return RESET
    elif key in ("ram", "swap"):
        if value >= 90: return RED
        if value >= 75: return YELLOW
        return RESET
    elif key == "disk":
        if value >= 90: return RED
        if value >= 80: return YELLOW
        return RESET
    elif key == "wifi":
        if value < 25: return RED
        if value < 50: return ORANGE
        if value < 75: return YELLOW
        return RESET
    elif key == "bat":
        if value <= 10: return RED
        if value <= 25: return ORANGE
        if value <= 50: return YELLOW
        return RESET
    return RESET

# ==========================================================
# DETECCIÓN DE HARDWARE Y MÉTRICAS
# ==========================================================

def detect_hardware():
    global CPU_FREQ_PATH, CPU_FREQ_MIN_PATH, CPU_FREQ_MAX_PATH, CPU_FREQ_CUR_PATH, CPU_GOVERNOR_PATH
    global BATTERY_PATH
    global CPU_TEMP_SENSOR, CPU_TEMP_INDEX
    global NVME_TEMP_SENSOR, NVME_TEMP_LABEL
    global WIFI_TEMP_SENSOR

    if not args.cpu:
        if os.path.isdir(CPU_SYS_PATH):
            for cpu in os.listdir(CPU_SYS_PATH):
                if not cpu.startswith("cpu"):
                    continue
                path = os.path.join(CPU_SYS_PATH, cpu, "cpufreq")
                if os.path.isdir(path):
                    CPU_FREQ_PATH = path
                    break

        if CPU_FREQ_PATH:
            CPU_FREQ_MIN_PATH = os.path.join(CPU_FREQ_PATH, "cpuinfo_min_freq")
            CPU_FREQ_MAX_PATH = os.path.join(CPU_FREQ_PATH, "cpuinfo_max_freq")
            CPU_FREQ_CUR_PATH = os.path.join(CPU_FREQ_PATH, "scaling_cur_freq")
            CPU_GOVERNOR_PATH = os.path.join(CPU_FREQ_PATH, "scaling_governor")

    if not args.bat:
        if os.path.isdir(POWER_SUPPLY_PATH):
            for dev in os.listdir(POWER_SUPPLY_PATH):
                dev_path = os.path.join(POWER_SUPPLY_PATH, dev)
                try:
                    with open(os.path.join(dev_path, "type")) as f:
                        if f.read().strip() != "Battery": continue
                    with open(os.path.join(dev_path, "scope")) as f:
                        if f.read().strip() != "System": continue
                    BATTERY_PATH = dev_path
                    break
                except FileNotFoundError: continue

    if not args.cpu or not args.disk or not args.wifi:
        temps = psutil.sensors_temperatures()
        
        if not args.cpu:
            for name in ("coretemp", "k10temp", "acpitz"):
                if name in temps:
                    CPU_TEMP_SENSOR = name
                    break
                    
        if not args.disk and "nvme" in temps:
            for entry in temps["nvme"]:
                if entry.current is not None:
                    NVME_TEMP_SENSOR = "nvme"
                    NVME_TEMP_LABEL = entry.label
                    break
                    
        if not args.wifi:
            for name in temps:
                if "iwlwifi" in name:
                    WIFI_TEMP_SENSOR = name
                    break

def init_metrics():
    global cpu_times_start, cpu_time_start
    global disk_io_start, disk_time_start

    if not args.cpu:
        cpu_times_start = psutil.cpu_times(percpu=True)
        cpu_time_start = time.time()

    if not args.disk:
        disk_io_start = psutil.disk_io_counters()
        disk_time_start = time.time()

# =====================================================================
# COLORES Y ESTILOS ANSI
# =====================================================================

RESET      = "\033[0m"
BOLD       = "\033[1m"
ITALIC     = "\033[3m" if os.environ.get("TERM", "") not in ("linux", "dumb") else "\033[2m"
UNDERLINE  = "\033[4m"
DIM        = "\033[2m"
GREEN      = "\033[92m"
ORANGE     = "\033[38;5;208m"
RED        = "\033[31m"
YELLOW     = "\033[93m"

# =====================================================================
# FUNCIONES DE UTILIDAD CLI
# =====================================================================

def terminal_supports_unicode() -> bool:
    if args.icon: return False
    term = os.environ.get("TERM", "").lower()
    encoding = (sys.stdout.encoding or "").lower()
    if any(x in term for x in ["linux", "vt100", "xterm-color", "dumb", "ansi"]): return False
    if not encoding.startswith("utf"): return False
    try:
        sys.stdout.write("🔁\r\033[K")
        sys.stdout.flush()
        return True
    except Exception: return False

def barra_progreso(valor, total=100, ancho=32, color=RESET):
    bloques_llenos = int((valor / total) * ancho)
    bloques_llenos = max(0, min(ancho, bloques_llenos))
    chars = ["█"] * bloques_llenos + ["░"] * (ancho - bloques_llenos)
    barra = "".join(chars)
    return f"{color}{barra}{RESET}"

def format_uptime(seconds):
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days > 0:
        return f"{days}d {hours}:{minutes:02}:{secs:02}"
    else:
        return f"{hours:02}:{minutes:02}:{secs:02}"

def get_keypress(timeout=1):
    dr, _, _ = select.select([sys.stdin], [], [], timeout)
    if dr:
        raw = os.read(sys.stdin.fileno(), 3).decode(errors='ignore')
        return raw if len(raw) == 1 else None
    return None

def enable_raw_mode():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    return old_settings

def disable_raw_mode(old_settings):
    fd = sys.stdin.fileno()
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

# =====================================================================
# 2.0_metrics_engine - MOTOR DE MÉTRICAS (CORE / MODEL)
# =====================================================================
# Núcleo puro de recolección. Lee /proc, /sys o psutil, procesa los 
# datos matemáticamente, actualiza promedios y devuelve diccionarios limpios.

_cached_system_info = None

def get_system_info():
    global _cached_system_info
    if _cached_system_info is not None:
        return _cached_system_info

    try:
        with open(OS_INFO_PATH) as f:
            os_name = "Unknown"
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    os_name = line.strip().split("=")[1].strip('"')
                    break
    except FileNotFoundError: os_name = "Unknown"
    try:
        with open(OS_RELEASE_PATH) as f: kernel_version = f.read().strip()
    except FileNotFoundError: kernel_version = "Unknown"
    
    _cached_system_info = {"os_name": os_name, "kernel_version": kernel_version}
    return _cached_system_info

_cached_host_user_info = None

def get_host_user_info():
    global _cached_host_user_info
    if _cached_host_user_info is not None:
        return _cached_host_user_info

    import getpass
    hostname = socket.gethostname()
    try: username = getpass.getuser()
    except Exception: username = "Unknown"
    
    _cached_host_user_info = {"hostname": hostname, "username": username}
    return _cached_host_user_info

def get_uptime_and_time():
    uptime_seconds = time.time() - psutil.boot_time()
    uptime_str = str(timedelta(seconds=int(uptime_seconds)))
    current_time = time.strftime("%H:%M:%S %d/%m/%Y")
    return {"uptime_str": uptime_str, "current_time": current_time}

def get_cpu_usage():
    global cpu_times_start, cpu_time_start
    cpu_times_current = psutil.cpu_times(percpu=True)
    cpu_time_current = time.time()
    uso_nucleos = []
    for start, current in zip(cpu_times_start, cpu_times_current):
        total_diff = sum(current) - sum(start)
        idle_diff = current.idle - start.idle
        uso = 100 * (1 - idle_diff / total_diff) if total_diff else 0.0
        uso_nucleos.append(uso)
    promedio_uso = sum(uso_nucleos) / len(uso_nucleos) if uso_nucleos else 0.0
    update_promedio("cpu", promedio_uso)
    cpu_times_start = cpu_times_current
    cpu_time_start = cpu_time_current
    return {"promedio": promedio_uso, "nucleos": uso_nucleos}

def get_cpu_frequency():
    if not CPU_FREQ_CUR_PATH: return None
    try:
        with open(CPU_FREQ_MIN_PATH) as f: min_freq = int(f.read().strip()) / 1_000_000
        with open(CPU_FREQ_MAX_PATH) as f: max_freq = int(f.read().strip()) / 1_000_000
        with open(CPU_FREQ_CUR_PATH) as f: cur_freq = int(f.read().strip()) / 1_000_000
        with open(CPU_GOVERNOR_PATH) as f: scaling_governor = f.read().strip()
        pct = (cur_freq / max_freq) * 100 if max_freq > 0 else 0.0
        update_promedio("freq", pct)
        return {"min_freq": min_freq, "max_freq": max_freq, "cur_freq": cur_freq, "scaling_governor": scaling_governor}
    except Exception: return None

def get_cpu_temperature():
    if not CPU_TEMP_SENSOR: return None
    try:
        temps = psutil.sensors_temperatures()
        if CPU_TEMP_SENSOR in temps:
            temp = temps[CPU_TEMP_SENSOR][CPU_TEMP_INDEX].current
            return {"current": temp}
        return None
    except Exception: return None

def get_memory_usage():
    with open(MEMINFO_PATH) as f: meminfo = f.readlines()
    valores = {}
    for linea in meminfo:
        partes = linea.split(":")
        clave = partes[0]
        valor = int(partes[1].strip().split()[0]) / 1024 / 1024
        valores[clave] = valor
    mem_total = valores["MemTotal"]
    mem_available = valores["MemAvailable"]
    mem_free = valores["MemFree"]
    mem_used = mem_total - mem_available
    mem_percent = (mem_used / mem_total) * 100
    apps_ratio = mem_used / mem_total
    free_ratio = mem_free / mem_total
    sys_ratio = 1 - apps_ratio - free_ratio
    swap_total = valores.get("SwapTotal", 0)
    swap_free = valores.get("SwapFree", 0)
    swap_used = swap_total - swap_free
    swap_percent = (swap_used / swap_total) * 100 if swap_total > 0 else 0
    update_promedio("ram", mem_percent)
    update_promedio("swap", swap_percent)
    return {
        "mem_percent": mem_percent, "mem_used": mem_used, "mem_total": mem_total,
        "swap_percent": swap_percent, "swap_used": swap_used, "swap_total": swap_total,
        "apps_ratio": apps_ratio, "free_ratio": free_ratio, "sys_ratio": sys_ratio
    }

def get_process_count():
    try:
        process_states = {"running": 0, "sleeping": 0, "idle": 0, "stopped": 0, "zombie": 0, "other": 0}
        total_processes = 0
        for pid in os.listdir(PROC_PATH):
            if pid.isdigit():
                total_processes += 1
                try:
                    with open(os.path.join(PROC_PATH, pid, "stat")) as f:
                        state = f.read().split()[2]
                        if state == "R": process_states["running"] += 1
                        elif state == "S": process_states["sleeping"] += 1
                        elif state == "D": process_states["other"] += 1
                        elif state == "T": process_states["stopped"] += 1
                        elif state == "Z": process_states["zombie"] += 1
                        elif state == "I": process_states["idle"] += 1
                        else: process_states["other"] += 1
                except Exception: continue
        return {"total": total_processes, "states": process_states}
    except Exception: return None

def get_load_average():
    cpu_count = os.cpu_count()
    load1, load5, load15 = os.getloadavg()
    return {"cpu_count": cpu_count, "load1": load1, "load5": load5, "load15": load15}

def get_disk_usage():
    st = os.statvfs("/")
    total = st.f_blocks * st.f_frsize / (1024 ** 3)
    used = (st.f_blocks - st.f_bfree) * st.f_frsize / (1024 ** 3)
    percent = (used / total) * 100
    global disk_io_start, disk_time_start
    disk_io_current = psutil.disk_io_counters()
    disk_time_current = time.time()
    interval = disk_time_current - disk_time_start or 0.0001
    
    disk_read_diff = max(0, disk_io_current.read_bytes - disk_io_start.read_bytes)
    disk_write_diff = max(0, disk_io_current.write_bytes - disk_io_start.write_bytes)
    
    disk_read_speed = disk_read_diff / (1024 * 1024 * interval)
    disk_write_speed = disk_write_diff / (1024 * 1024 * interval)
    disk_io_start, disk_time_start = disk_io_current, disk_time_current
    update_promedio("disk", percent)
    return {"percent": percent, "used": used, "total": total, "read_speed": disk_read_speed, "write_speed": disk_write_speed}

def get_nvme_temperature():
    if not NVME_TEMP_SENSOR: return None
    try:
        temps = psutil.sensors_temperatures()
        if NVME_TEMP_SENSOR in temps:
            if NVME_TEMP_LABEL:
                for entry in temps[NVME_TEMP_SENSOR]:
                    if entry.label == NVME_TEMP_LABEL:
                        return {"current": entry.current}
            return {"current": temps[NVME_TEMP_SENSOR][0].current}
        return None
    except Exception: return None

def get_lan_info():
    global lan_io_start, lan_time_start, lan_last_iface
    try:
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        iface = None
        for name, stat in stats.items():
            if name == "lo" or not stat.isup: continue
            if os.path.isdir(f"/sys/class/net/{name}/wireless"): continue
            if any(addr.family == socket.AF_INET for addr in addrs.get(name, [])):
                iface = name
                break
                
        if not iface: return None
        if iface != lan_last_iface:
            lan_io_start = None
            lan_last_iface = iface
            
        ip = next((addr.address for addr in addrs.get(iface) if addr.family == socket.AF_INET), None)
        stats_info = stats.get(iface)
        io_end = psutil.net_io_counters(pernic=True).get(iface)
        time_end = time.time()
        
        if not lan_io_start:
            lan_io_start, lan_time_start = io_end, time_end
            return {"ip": ip, "speed": stats_info.speed, "duplex": "Full" if stats_info.duplex == 2 else "Half", "down": 0.0, "up": 0.0, "partial": True}
            
        interval = time_end - lan_time_start or 0.0001
        down = max(0, io_end.bytes_recv - lan_io_start.bytes_recv) / (1024 * 1024) / interval
        up = max(0, io_end.bytes_sent - lan_io_start.bytes_sent) / (1024 * 1024) / interval
        
        lan_io_start, lan_time_start = io_end, time_end
        return {"ip": ip, "speed": stats_info.speed, "duplex": "Full" if stats_info.duplex == 2 else "Half", "down": down, "up": up, "partial": False}
    except Exception: return None

def get_wifi_info():
    global wifi_io_start, wifi_time_start, wifi_last_iface
    try:
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        iface = None
        for name, stat in stats.items():
            if name == "lo" or not stat.isup: continue
            if os.path.isdir(f"/sys/class/net/{name}/wireless"):
                if any(addr.family == socket.AF_INET for addr in addrs.get(name, [])):
                    iface = name
                    break
                    
        if not iface: return None
        if iface != wifi_last_iface:
            wifi_io_start = None
            wifi_last_iface = iface
            
        output = subprocess.run(["iw", "dev", iface, "link"], capture_output=True, text=True).stdout
        if "Not connected" in output: return None
        ssid = re.search(r'SSID: (.+)', output).group(1).strip()
        signal_dbm = int(re.search(r'signal: (-?\d+) dBm', output).group(1))
        speed = float(re.search(r'bitrate: ([\d\.]+) MBit/s', output).group(1))
        ip = next((addr.address for addr in addrs.get(iface, []) if addr.family == socket.AF_INET), "N/A")
        signal_percent = max(0, min(100, 2 * (signal_dbm + 100)))
        
        io_current = psutil.net_io_counters(pernic=True).get(iface)
        time_current = time.time()
        
        if not wifi_io_start:
            wifi_io_start, wifi_time_start = io_current, time_current
            down, up = 0.0, 0.0
        else:
            interval = time_current - wifi_time_start or 0.0001
            down = max(0, io_current.bytes_recv - wifi_io_start.bytes_recv) / (1024 * 1024 * interval)
            up = max(0, io_current.bytes_sent - wifi_io_start.bytes_sent) / (1024 * 1024 * interval)
            wifi_io_start, wifi_time_start = io_current, time_current
            
        wifi_temp = None
        if WIFI_TEMP_SENSOR:
            temps = psutil.sensors_temperatures()
            if WIFI_TEMP_SENSOR in temps:
                wifi_temp = temps[WIFI_TEMP_SENSOR][0].current
        update_promedio("wifi", signal_percent)
        return {"ip": ip, "ssid": ssid, "signal": signal_percent, "speed": speed, "down": down, "up": up, "temp": wifi_temp}
    except Exception: return None

def get_battery_info():
    if not BATTERY_PATH: return None
    try:
        with open(os.path.join(BATTERY_PATH, "capacity")) as f:
            percent = int(f.read().strip())
        with open(os.path.join(BATTERY_PATH, "status")) as f:
            status = f.read().strip()
            
        mode = status
        time_str = ""
        
        if status == "Discharging":
            try:
                with open(os.path.join(BATTERY_PATH, "energy_now")) as f: energy_now = int(f.read().strip())
                with open(os.path.join(BATTERY_PATH, "power_now")) as f: power_now = int(f.read().strip())
                if power_now > 0:
                    secsleft = int((energy_now / power_now) * 3600)
                    h, m = divmod(secsleft // 60, 60)
                    time_str = f" - Time: {BOLD}{h}h {m}m{RESET}"
            except Exception: pass
            
        update_promedio("bat", percent)
        return {"percent": percent, "mode": mode, "time_str": time_str}
    except Exception: return None

# =====================================================================
# 3.0_cli_view - CONTROLADOR Y VISTA DE CONSOLA (CLI VIEW)
# =====================================================================
# Formatea y dibuja los datos en la terminal usando print() y bloques ANSI.
# Controla el bucle de temporización clásico de consola.

def print_info(icono, texto_con_icono, texto_sin_icono=None):
    if texto_sin_icono is None: texto_sin_icono = texto_con_icono
    if not args.icon: print(f"{icono} {texto_con_icono}")
    else: print(f"{texto_sin_icono}")

def print_barra_cli(texto_barra):
    if not args.icon: print("   " + texto_barra)
    else: print(texto_barra)

def print_system_info(data):
    if not data: return
    prefix = "🐧 " if not args.icon else ""
    kernel_prefix = "⚙️  " if not args.icon else ""
    print(f"{prefix}OS: {BOLD}{data['os_name']}{RESET} - {kernel_prefix}Kernel version: {BOLD}{data['kernel_version']}{RESET}")

def print_host_user_info(data):
    if not data: return
    print_info("🏠", f"Hostname: {BOLD}{data['hostname']}{RESET} - 👤 User: {BOLD}{data['username']}{RESET}",
                     f"Hostname: {BOLD}{data['hostname']}{RESET} - User: {BOLD}{data['username']}{RESET}")

def print_uptime_and_time(data):
    if not data: return
    print_info("⏱️ ", f"Uptime: {BOLD}{data['uptime_str']}{RESET} - 🕒 Time and date: {BOLD}{data['current_time']}{RESET}",
                       f"Uptime: {BOLD}{data['uptime_str']}{RESET} - Time and date: {BOLD}{data['current_time']}{RESET}")

def print_cpu_usage(data):
    if not data: return
    usage = data["promedio"]
    ru = round(usage)
    color = RESET
    if ru > 99: color = RED
    elif ru > 66: color = ORANGE
    elif ru > 33: color = YELLOW
    
    nucleos_str_parts = []
    for i, u in enumerate(data["nucleos"]):
        ru_n = round(u)
        c_color = RESET
        if ru_n > 99: c_color = RED
        elif ru_n > 66: c_color = ORANGE
        elif ru_n > 33: c_color = YELLOW
        nucleos_str_parts.append(f"{ITALIC}CPU{i}{RESET}: {c_color}{BOLD}{u:.0f}%{RESET}")
    nucleos_str = " - ".join(nucleos_str_parts)
    
    print_info("🤖", f"CPU used: {color}{BOLD}{usage:.0f}%{RESET} ({nucleos_str})",
                     f"CPU used: {color}{BOLD}{usage:.0f}%{RESET} ({nucleos_str})")
    if not args.bar and not args.barc:
        print_barra_cli(barra_progreso(usage, color=color))

def print_cpu_frequency(data):
    if not data: return
    cur_freq = round(data["cur_freq"], 2)
    max_freq = round(data["max_freq"], 2)
    pct_freq = (cur_freq / max_freq) * 100 if max_freq > 0 else 0.0
    color = get_metric_color("freq", pct_freq)
    print_info("🚀", f"CPU frequency: {color}{BOLD}{cur_freq:.2f}GHz{RESET} - 🎚️  Scaling governor: {BOLD}{data['scaling_governor']}{RESET}",
                     f"CPU frequency: {color}{BOLD}{cur_freq:.2f}GHz{RESET} - Scaling governor: {BOLD}{data['scaling_governor']}{RESET}")
    if not args.bar and not args.barf:
        print_barra_cli(barra_progreso(pct_freq, color=color))

def print_cpu_temperature(data):
    if not data: return
    temp = data["current"]
    color = RED if temp > 60 else ORANGE if temp > 40 else YELLOW if temp > 35 else RESET
    print_info("🌡️ ", f"CPU temperature: {color}{BOLD}{temp:.0f}°C{RESET}", f"CPU temperature: {color}{BOLD}{temp:.0f}°C{RESET}")

def print_memory_usage(data):
    if not data: return
    mem_p = data["mem_percent"]
    mem_color = RED if mem_p >= 90 else YELLOW if mem_p >= 75 else RESET
    swap_p = data["swap_percent"]
    swap_color = RED if swap_p >= 90 else YELLOW if swap_p >= 75 else RESET
    print_info("🧮", f"RAM used: {mem_color}{BOLD}{mem_p:.0f}%{RESET} ({BOLD}{data['mem_used']:.2f}GB/{data['mem_total']:.2f}GB{RESET}) - 💾 Swap used: {swap_color}{BOLD}{swap_p:.0f}%{RESET} ({BOLD}{data['swap_used']:.2f}GB/{data['swap_total']:.2f}GB{RESET})",
                    f"RAM used: {mem_color}{BOLD}{mem_p:.0f}%{RESET} ({BOLD}{data['mem_used']:.2f}GB/{data['mem_total']:.2f}GB{RESET}) - Swap used: {swap_color}{BOLD}{swap_p:.0f}%{RESET} ({BOLD}{data['swap_used']:.2f}GB/{data['swap_total']:.2f}GB{RESET})")
    if not args.bar and not args.barr:
        ancho = 32
        apps = int(ancho * data["apps_ratio"])
        free = int(ancho * data["free_ratio"])
        sys_b = ancho - apps - free
        barra_ram = f"{mem_color}{'█' * apps}{'▒' * sys_b}{'░' * free}{RESET}"
        barra_swap = barra_progreso(swap_p, color=swap_color)
        print_barra_cli(f"{barra_ram} - {barra_swap}")

def print_process_count(data):
    if not data: return
    s = data["states"]
    info = f"Processes: {BOLD}{data['total']}{RESET} ({ITALIC}run{RESET}={BOLD}{s['running']}{RESET}, {ITALIC}sleep{RESET}={BOLD}{s['sleeping']}{RESET}, {ITALIC}idle{RESET}={BOLD}{s['idle']}{RESET}, {ITALIC}stop{RESET}={BOLD}{s['stopped']}{RESET}, {ITALIC}zombie{RESET}={BOLD}{s['zombie']}{RESET})"
    print_info("🧩", info, info)

def print_load_average(data):
    if not data: return
    c = data["cpu_count"]
    def col(v): return f"{RED}{v:.2f}{RESET}" if v >= c else f"{YELLOW}{v:.2f}{RESET}" if v >= c*0.75 else f"{v:.2f}"
    print_info("📊", f"Load average: {BOLD}{col(data['load1'])}{RESET} {BOLD}{col(data['load5'])}{RESET} {BOLD}{col(data['load15'])}{RESET}",
                     f"Load average: {BOLD}{col(data['load1'])}{RESET} {BOLD}{col(data['load5'])}{RESET} {BOLD}{col(data['load15'])}{RESET}")

def print_disk_usage(data):
    if not data: return
    p = data["percent"]
    color = RED if p >= 90 else YELLOW if p >= 80 else RESET
    print_info("🗄️ ", f"Disk used: {color}{BOLD}{p:.0f}%{RESET} ({BOLD}{data['used']:.2f}GB/{data['total']:.2f}GB{RESET}) - Read: {BOLD}{data['read_speed']:.2f}MB/s{RESET} - Write: {BOLD}{data['write_speed']:.2f}MB/s{RESET}",
                      f"Disk used: {color}{BOLD}{p:.0f}%{RESET} ({BOLD}{data['used']:.2f}GB/{data['total']:.2f}GB{RESET}) - Read: {BOLD}{data['read_speed']:.2f}MB/s{RESET} - Write: {BOLD}{data['write_speed']:.2f}MB/s{RESET}")
    if not args.bar and not args.bard:
        print_barra_cli(barra_progreso(p, color=color))

def print_nvme_temperature(data):
    if not data: return
    t = data["current"]
    color = RED if t >= 70 else YELLOW if t >= 50 else RESET
    print_info("🌡️ ", f"Disk temperature: {color}{BOLD}{t:.0f}°C{RESET}", f"Disk temperature: {color}{BOLD}{t:.0f}°C{RESET}")

def print_lan_info(data):
    if not data: return
    if data["partial"]: print(f"LAN IP: {BOLD}{data['ip']}{RESET} - Speed: {BOLD}{data['speed']}Mb/s{RESET} ({BOLD}{data['duplex']}{RESET})"); return
    print_info("🌐", f"LAN IP: {BOLD}{data['ip']}{RESET} - Speed: {BOLD}{data['speed']}Mb/s{RESET} ({BOLD}{data['duplex']}{RESET}) - Down: {BOLD}{data['down']:.2f}MB/s{RESET} - Up: {BOLD}{data['up']:.2f}MB/s{RESET}",
                     f"LAN IP: {BOLD}{data['ip']}{RESET} - Speed: {BOLD}{data['speed']}Mb/s{RESET} ({BOLD}{data['duplex']}{RESET}) - Down: {BOLD}{data['down']:.2f}MB/s{RESET} - Up: {BOLD}{data['up']:.2f}MB/s{RESET}")

def print_wifi_info(data):
    if not data: return
    p = data["signal"]
    color = RED if p < 25 else ORANGE if p < 50 else YELLOW if p < 75 else RESET
    print_info("📶", f"WiFi IP: {BOLD}{data['ip']}{RESET} - SSID: {BOLD}{data['ssid']}{RESET}", f"WiFi IP: {BOLD}{data['ip']}{RESET} - SSID: {BOLD}{data['ssid']}{RESET}")
    print_info("📡", f"WiFi signal: {color}{BOLD}{p:.0f}%{RESET} - Speed: {BOLD}{data['speed']:.2f}Mb/s{RESET} - Down: {BOLD}{data['down']:.2f}MB/s{RESET} - Up: {BOLD}{data['up']:.2f}MB/s{RESET}",
                     f"WiFi signal: {color}{BOLD}{p:.0f}%{RESET} - Speed: {BOLD}{data['speed']:.2f}Mb/s{RESET} - Down: {BOLD}{data['down']:.2f}MB/s{RESET} - Up: {BOLD}{data['up']:.2f}MB/s{RESET}")
    if not args.bar and not args.barw:
        print_barra_cli(barra_progreso(p, color=color))
    if data["temp"]:
        t = data["temp"]
        tc = RED if t > 70 else YELLOW if t > 50 else RESET
        print_info("🌡️ ", f"WiFi temperature: {tc}{BOLD}{t:.0f}°C{RESET}", f"WiFi temperature: {tc}{BOLD}{t:.0f}°C{RESET}")

def print_battery_info(data):
    if not data: return
    p = data["percent"]
    color = RED if p <= 10 else ORANGE if p <= 25 else YELLOW if p <= 50 else RESET
    print_info("🔋", f"Battery: {color}{BOLD}{p}%{RESET}{data['time_str']} - Mode: {BOLD}{data['mode']}{RESET}",
                     f"Battery: {color}{BOLD}{p}%{RESET}{data['time_str']} - Mode: {BOLD}{data['mode']}{RESET}")
    if not args.bar and not args.bart:
        print_barra_cli(barra_progreso(p, color=color))

def print_all_stats():
    if not args.sys: print_system_info(get_system_info())
    if not args.host: print_host_user_info(get_host_user_info())
    if not args.up: print_uptime_and_time(get_uptime_and_time())
    if not args.cpu:
        print_cpu_usage(get_cpu_usage())
        print_cpu_frequency(get_cpu_frequency())
        print_cpu_temperature(get_cpu_temperature())
    if not args.ram: print_memory_usage(get_memory_usage())
    if not args.proc: print_process_count(get_process_count())
    if not args.load: print_load_average(get_load_average())
    if not args.disk:
        print_disk_usage(get_disk_usage())
        print_nvme_temperature(get_nvme_temperature())
    if not args.lan: print_lan_info(get_lan_info())
    if not args.wifi: print_wifi_info(get_wifi_info())
    if not args.bat: print_battery_info(get_battery_info())

def render_cli(interval):
    if interval > 0:
        start_time = time.time(); count = 1; old_s = enable_raw_mode()
        try:
            while True:
                exec_start = time.time(); os.system('clear'); print_all_stats()
                elapsed = int(time.time() - start_time)
                uptime = format_uptime(elapsed)
                exec_dur = (time.time() - exec_start) * 1000
                mem_p = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
                for i in range(interval, 0, -1):
                    prefix = "🔁 " if not args.icon else ""
                    sys.stdout.write(f"\r{prefix}{DIM}Run: {uptime} ({exec_dur:.0f}ms) | Cycles: {count} | {mem_p:.2f}MB | Next: {i}/{interval}s {RESET}")
                    sys.stdout.flush()
                    ts = time.time()
                    while time.time() - ts < 1:
                        key = get_keypress(0.1)
                        if key and key.lower() in ['q', 'x']: print(""); raise SystemExit
                count += 1
        finally: disable_raw_mode(old_s)
    else: print_all_stats()

# =====================================================================
# 4.0_gui_view - CONTROLADOR Y VISTA GRÁFICA (GUI VIEW)
# =====================================================================
# Interactúa con CustomTkinter. Actualiza widgets, barras de progreso
# y renderiza los marcadores estáticos (Min/Avg/Max) en pantalla.

class CanvasTooltip:
    def __init__(self, widget, db_key):
        self.widget = widget
        self.db_key = db_key
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)
        self.widget.bind("<Motion>", self.move_tip)
        
        self.widget._tooltip_instance = self

    def bind_recursively(self, child):
        child.bind("<Enter>", self.show_tip)
        child.bind("<Leave>", self.hide_tip)
        child.bind("<Motion>", self.move_tip)
        child._tooltip_instance = self

    def show_tip(self, event=None):
        if self.tip_window:
            return
        min_v = get_min_metric(self.db_key)
        avg_v = get_promedio(self.db_key)
        max_v = get_max_metric(self.db_key)
        
        if min_v is None or avg_v is None or max_v is None:
            return
            
        suffix = "GHz" if self.db_key == "freq" else "%"
        if self.db_key == "freq":
            try:
                with open(os.path.join("/sys/devices/system/cpu/cpu0/cpufreq", "cpuinfo_max_freq")) as f:
                    max_f = int(f.read().strip()) / 1_000_000
            except Exception:
                max_f = 1.0
            min_v = (min_v / 100.0) * max_f
            avg_v = (avg_v / 100.0) * max_f
            max_v = (max_v / 100.0) * max_f
            text = f" Min: {min_v:.2f}{suffix} | Avg: {avg_v:.2f}{suffix} | Max: {max_v:.2f}{suffix} "
        else:
            text = f" Min: {min_v:.0f}{suffix} | Avg: {avg_v:.0f}{suffix} | Max: {max_v:.0f}{suffix} "

        import tkinter as tk
        x = self.widget.winfo_pointerx() + 10
        y = self.widget.winfo_pointery() + 10
        
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(tw, text=text, justify="left",
                         background="#1e1e2e", foreground="#cdd6f4",
                         relief="solid", borderwidth=1,
                         font=("Monospace", 10, "bold"))
        label.pack(ipadx=4, ipady=2)

    def move_tip(self, event):
        if self.tip_window:
            x = self.widget.winfo_pointerx() + 10
            y = self.widget.winfo_pointery() + 10
            self.tip_window.wm_geometry(f"+{x}+{y}")

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()

# =====================================================================
# RENDERIZADO GUI
# =====================================================================

def render_gui(interval):
    try: import customtkinter as ctk
    except ImportError:
        print(f"{RED}Error: La librería 'customtkinter' no está instalada.{RESET}")
        sys.exit(1)

    import tkinter as tk

    BAR_WIDTH = 200
    TROUGH_COLOR = "#2e2e2e"

    ROW_HEIGHT = 18
    BAR_HEIGHT = 16
    STATUS_BAR_HEIGHT = 22
    ICON_WIDTH = 20

    ctk.set_appearance_mode("dark")
    app = ctk.CTk()
    app.title("SysStat CLI/GUI v3.47.4ia")
    app.configure(fg_color="#0a0a0a")
    app.resizable(False, False)

    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_papirus = os.path.join(current_dir, ICON_PAPIRUS_NAME)
        icon_standard = os.path.join(current_dir, ICON_STANDARD_NAME)
        icon_path = icon_papirus if os.path.exists(icon_papirus) else icon_standard
        if os.path.exists(icon_path):
            img = tk.PhotoImage(file=icon_path)
            app.wm_iconphoto(True, img)
            app._icon_photo = img
    except Exception as e:
        print(f"Error cargando icono: {e}")
    
    mono_font = ("Monospace", 12)
    mono_bold = ("Monospace", 12, "bold")
    emoji_font = ("Noto Color Emoji", 12)
    
    COLOR_MAP = {
        GREEN: "#4ade80",
        YELLOW: "#facc15",
        ORANGE: "#fb923c",
        RED: "#ff3131",
        RESET: "#ffffff",
        DIM: "#71717a"
    }

    main_container = ctk.CTkFrame(app, fg_color="transparent")
    main_container.pack(fill="both", expand=True, padx=4, pady=2)

    rows = {}
    rows_labels = {}
    rows_indent = {}
    bars = {}
    bars_frames = {}
    bars_indent = {}
    active_tags_current = []
    active_tags_last = [[]]

    def get_color(c): return COLOR_MAP.get(c, "#ffffff")

    def handle_gui_right_click(db_key, markers, parent_bar):
        val = ultimos_valores_gui[db_key]
        promedios_db[db_key] = {
            "sum": float(val),
            "count": 1,
            "min": float(val),
            "max": float(val)
        }
        render_triple_markers(markers, db_key, parent_bar)
        
        if hasattr(parent_bar, '_tooltip_instance'):
            tooltip = parent_bar._tooltip_instance
            if tooltip and tooltip.tip_window:
                tooltip.hide_tip()
                tooltip.show_tip()

    def update_gui_marker(marker, relx, color_hex, in_, pixel_height):
        if relx <= 0.005:
            marker.configure(width=2, bg="#000000")
            marker._colored_line.configure(bg=color_hex)
            marker._colored_line.place(x=0, y=0, height=pixel_height, width=1)
            marker.place(in_=in_, relx=0.0, rely=0.0, height=pixel_height, width=2, anchor="nw")
        elif relx >= 0.995:
            marker.configure(width=2, bg="#000000")
            marker._colored_line.configure(bg=color_hex)
            marker._colored_line.place(x=1, y=0, height=pixel_height, width=1)
            marker.place(in_=in_, relx=1.0, rely=0.0, height=pixel_height, width=2, anchor="ne")
        else:
            marker.configure(width=3, bg="#000000")
            marker._colored_line.configure(bg=color_hex)
            marker._colored_line.place(x=1, y=0, height=pixel_height, width=1)
            marker.place(in_=in_, relx=relx, rely=0.0, height=pixel_height, width=3, anchor="n")

    def create_triple_markers(parent_bar):
        markers = {}
        for name in ["min", "avg", "max"]:
            m = tk.Frame(parent_bar, width=3, bg="#000000", bd=0)
            c_l = tk.Frame(m, width=1, bg="#ffffff", bd=0)
            c_l.place(x=1, y=0, height=16, width=1)
            m._colored_line = c_l
            markers[name] = m
        return markers

    def render_triple_markers(markers, db_key, parent_bar):
        # 1. Mínimo -> 8 píxeles fijos
        v_min = get_min_metric(db_key)
        if v_min is not None:
            relx = max(0.0, min(1.0, v_min / 100.0))
            m = markers["min"]
            color_hex = get_color(get_metric_color(db_key, v_min))
            update_gui_marker(m, relx, color_hex, in_=parent_bar, pixel_height=8)
        else:
            markers["min"].place_forget()

        # 2. Promedio -> 12 píxeles fijos
        v_avg = get_promedio(db_key)
        if v_avg is not None:
            relx = max(0.0, min(1.0, v_avg / 100.0))
            m = markers["avg"]
            color_hex = get_color(get_metric_color(db_key, v_avg))
            update_gui_marker(m, relx, color_hex, in_=parent_bar, pixel_height=12)
        else:
            markers["avg"].place_forget()

        # 3. Máximo -> 16 píxeles fijos (Alto completo)
        v_max = get_max_metric(db_key)
        if v_max is not None:
            relx = max(0.0, min(1.0, v_max / 100.0))
            m = markers["max"]
            color_hex = get_color(get_metric_color(db_key, v_max))
            update_gui_marker(m, relx, color_hex, in_=parent_bar, pixel_height=16)
        else:
            markers["max"].place_forget()

    def set_rich_line(tag, icon, segments, indent=0):
        if tag not in rows:
            f = ctk.CTkFrame(main_container, fg_color="transparent", height=ROW_HEIGHT)
            rows[tag] = f
            rows_labels[tag] = {"icon": None, "segs": []}
        rows_indent[tag] = indent
        active_tags_current.append(tag)
        
        if icon and not args.icon:
            if not rows_labels[tag]["icon"]:
                l = ctk.CTkLabel(rows[tag], text=icon, font=emoji_font, width=ICON_WIDTH, height=ROW_HEIGHT, anchor="center")
                l.pack(side="left", padx=(0, 4))
                rows_labels[tag]["icon"] = l
            else:
                rows_labels[tag]["icon"].configure(text=icon)
        elif rows_labels[tag]["icon"]:
            rows_labels[tag]["icon"].configure(text="")

        existing_segs = rows_labels[tag]["segs"]
        for i, (text, color_code, style) in enumerate(segments):
            font = emoji_font if style == "emoji" else (mono_bold if style else mono_font)
            color = get_color(color_code)
            if i < len(existing_segs):
                lbl = existing_segs[i]
                lbl.configure(text=text, text_color=color, font=font)
                lbl.pack(side="left")
            else:
                lbl = ctk.CTkLabel(rows[tag], text=text, font=font, text_color=color, height=ROW_HEIGHT, anchor="w")
                lbl.pack(side="left", padx=0)
                existing_segs.append(lbl)
        
        for j in range(len(segments), len(existing_segs)):
            existing_segs[j].pack_forget()

    def set_bar(tag, value, color_code, indent=None):
        db_key_map = {"cpu_b": "cpu", "freq_b": "freq", "disk_b": "disk", "wf_b": "wifi", "bat_b": "bat"}
        db_key = db_key_map.get(tag)
        
        if indent is None:
            indent = 0 if args.icon else ICON_WIDTH + 4
        if tag not in bars:
            f = ctk.CTkFrame(main_container, fg_color="transparent", height=ROW_HEIGHT)
            b = ctk.CTkProgressBar(f, width=BAR_WIDTH, height=BAR_HEIGHT, progress_color=get_color(color_code), fg_color=TROUGH_COLOR, corner_radius=0)
            b.pack(side="left", pady=(1, 1))
            
            CanvasTooltip(b, db_key)
            b._markers = create_triple_markers(b)
            
            b.bind("<Button-3>", lambda e, k=db_key, m=b._markers, p=b: handle_gui_right_click(k, m, p))
            
            bars[tag] = b
            bars_frames[tag] = f
        else:
            b = bars[tag]
            
        bars_indent[tag] = indent
        active_tags_current.append(tag)
        b.set(value / 100)
        b.configure(progress_color=get_color(color_code))
        
        if db_key:
            render_triple_markers(b._markers, db_key, b)

    def set_segmented_ram(tag, apps_ratio, sys_ratio, free_ratio, apps_color, sys_color, indent=None):
        if indent is None:
            indent = 0 if args.icon else ICON_WIDTH + 4
        if tag not in bars:
            f = ctk.CTkFrame(main_container, fg_color="transparent", height=ROW_HEIGHT)
            
            ram_container = ctk.CTkFrame(f, fg_color=TROUGH_COLOR, width=BAR_WIDTH, height=BAR_HEIGHT, corner_radius=0) 
            ram_container.pack(side="left", pady=(1, 1))
            ram_container.pack_propagate(False)

            b_sys = ctk.CTkFrame(ram_container, fg_color=get_color(sys_color) if sys_color != RESET else "#52525b", height=BAR_HEIGHT, corner_radius=0, border_width=0)
            b_sys.place(relx=0, x=0, rely=0, relheight=1)
            
            b_apps = ctk.CTkFrame(ram_container, fg_color=get_color(apps_color), height=BAR_HEIGHT, corner_radius=0, border_width=0)
            b_apps.place(relx=0, x=0, rely=0, relheight=1)
            
            ram_tip = CanvasTooltip(ram_container, "ram")
            ram_tip.bind_recursively(b_sys)
            ram_tip.bind_recursively(b_apps)
            
            ram_container._tooltip_instance = ram_tip
            b_sys._tooltip_instance = ram_tip
            b_apps._tooltip_instance = ram_tip
            
            sep = ctk.CTkLabel(f, text=" - ", font=mono_font, height=ROW_HEIGHT)
            sep.pack(side="left", padx=0)
            
            b_swap = ctk.CTkProgressBar(f, width=BAR_WIDTH, height=BAR_HEIGHT, progress_color="#ffffff", fg_color=TROUGH_COLOR, corner_radius=0)
            b_swap.pack(side="left", pady=(1, 1))
            
            swap_tip = CanvasTooltip(b_swap, "swap")
            b_swap._tooltip_instance = swap_tip
            
            ram_markers = create_triple_markers(ram_container)
            swap_markers = create_triple_markers(b_swap)
            
            ram_container.bind("<Button-3>", lambda e, k="ram", m=ram_markers, p=ram_container: handle_gui_right_click(k, m, p))
            b_sys.bind("<Button-3>", lambda e, k="ram", m=ram_markers, p=ram_container: handle_gui_right_click(k, m, p))
            b_apps.bind("<Button-3>", lambda e, k="ram", m=ram_markers, p=ram_container: handle_gui_right_click(k, m, p))
            b_swap.bind("<Button-3>", lambda e, k="swap", m=swap_markers, p=b_swap: handle_gui_right_click(k, m, p))
            
            bars[tag] = (b_apps, b_sys, b_swap, ram_container, ram_markers, swap_markers)
            bars_frames[tag] = f
        else:
            b_apps, b_sys, b_swap, ram_container, ram_markers, swap_markers = bars[tag]
            
        bars_indent[tag] = indent
        active_tags_current.append(tag)
        
        px_apps = int(apps_ratio * BAR_WIDTH)
        px_sys = int(sys_ratio * BAR_WIDTH)
        
        b_sys.configure(width=px_apps + px_sys)
        b_apps.configure(width=px_apps, fg_color=get_color(apps_color))
        
        render_triple_markers(ram_markers, "ram", ram_container)
        return b_swap

    status_bar = ctk.CTkFrame(app, height=STATUS_BAR_HEIGHT, fg_color="#18181b")
    status_bar.pack(fill="x", side="bottom")
    
    status_icon_lbl = ctk.CTkLabel(status_bar, text="", font=emoji_font, width=ICON_WIDTH, height=STATUS_BAR_HEIGHT, anchor="center")
    if not args.icon:
        status_icon_lbl.pack(side="left", padx=(4, 4))
    status_text_lbl = ctk.CTkLabel(status_bar, text="", font=("Monospace", 11), text_color="#a1a1aa", height=STATUS_BAR_HEIGHT, anchor="w")
    if args.icon:
        status_text_lbl.pack(side="left", padx=(4, 4))
    else:
        status_text_lbl.pack(side="left", padx=0)

    start_time = time.time()
    it_count = [1]
    next_timer = [interval]
    last_exec_ms = [0]

    def update():
        t_start = time.time()
        active_tags_current.clear()

        if not args.sys:
            # Ahora get_system_info() maneja de forma transparente el caché global compartida con la CLI
            d = get_system_info()
            kernel_segs = [(" - ", RESET, False), ("⚙️", RESET, "emoji"), (" Kernel version: ", RESET, False)] if not args.icon else [(" - Kernel version: ", RESET, False)]
            # El formato real y limpio, mostrando el OS y los segmentos del Kernel sin repetir nada
            set_rich_line("sys", "🐧", [("OS: ", RESET, False), (d['os_name'], RESET, True)] + kernel_segs + [(d['kernel_version'], RESET, True)])
        
        if not args.host:
            # Ahora get_host_user_info() recupera las variables almacenadas sin llamadas redundantes a socket
            d = get_host_user_info()
            host_segs = [(" - ", RESET, False), ("👤", RESET, "emoji"), (" User: ", RESET, False)] if not args.icon else [(" - User: ", RESET, False)]
            set_rich_line("host", "🏠", [("Hostname: ", RESET, False), (d['hostname'], RESET, True)] + host_segs + [(d['username'], RESET, True)])
            
        if not args.up:
            d = get_uptime_and_time()
            up_segs = [(" - ", RESET, False), ("🕒", RESET, "emoji"), (" Time and date: ", RESET, False)] if not args.icon else [(" - Time and date: ", RESET, False)]
            set_rich_line("up", "⏱️", [("Uptime: ", RESET, False), (d['uptime_str'], RESET, True)] + up_segs + [(d['current_time'], RESET, True)])

        if not args.cpu:
            d = get_cpu_usage()
            use = d["promedio"]
            ultimos_valores_gui["cpu"] = use
            ru = round(use)
            c = RED if ru > 99 else ORANGE if ru > 66 else YELLOW if ru > 33 else RESET
            segs = [("CPU used: ", RESET, False), (f"{use:.0f}%", c, True), (" (", RESET, False)]
            for i, u in enumerate(d["nucleos"]):
                ru_n = round(u)
                uc = RED if ru_n > 99 else ORANGE if ru_n > 66 else YELLOW if ru_n > 33 else RESET
                segs.append((f"CPU{i}: ", DIM, False))
                segs.append((f"{u:.0f}%", uc, True))
                if i < len(d["nucleos"]) - 1: segs.append((" - ", RESET, False))
            segs.append((")", RESET, False))
            set_rich_line("cpu", "🤖", segs)
            if not args.bar and not args.barc: set_bar("cpu_b", use, c)
            
            df = get_cpu_frequency()
            if df:
                cf = round(df['cur_freq'], 2)
                mf = round(df['max_freq'], 2)
                pct_freq = (cf / mf) * 100 if mf > 0 else 0.0
                ultimos_valores_gui["freq"] = pct_freq
                
                # Evaluación unificada basada estrictamente en el porcentaje
                fc = get_metric_color("freq", pct_freq)
                
                gov_segs = [(" - ", RESET, False), ("🎚️", RESET, "emoji"), (" Scaling governor: ", RESET, False)] if not args.icon else [(" - Scaling governor: ", RESET, False)]
                set_rich_line("freq", "🚀", [("CPU frequency: ", RESET, False), (f"{cf:.2f}GHz", fc, True)] + gov_segs + [(df['scaling_governor'], RESET, True)])
                if not args.bar and not args.barf: set_bar("freq_b", pct_freq, fc)
                
            dt = get_cpu_temperature()
            if dt:
                tc = RED if dt['current'] > 60 else ORANGE if dt['current'] > 40 else YELLOW if dt['current'] > 35 else RESET
                set_rich_line("temp", "🌡️", [("CPU temperature: ", RESET, False), (f"{dt['current']:.0f}°C", tc, True)])

        if not args.ram:
            d = get_memory_usage()
            ultimos_valores_gui["ram"] = d['mem_percent']
            ultimos_valores_gui["swap"] = d['swap_percent']
            mc = RED if d['mem_percent'] >= 90 else YELLOW if d['mem_percent'] >= 75 else RESET
            sc = RED if d['swap_percent'] >= 90 else YELLOW if d['swap_percent'] >= 75 else RESET
            swap_segs = [(" - ", RESET, False), ("💾", RESET, "emoji"), (" Swap used: ", RESET, False)] if not args.icon else [(" - Swap used: ", RESET, False)]
            set_rich_line("ram", "🧮", [("RAM used: ", RESET, False), (f"{d['mem_percent']:.0f}%", mc, True), (f" ({d['mem_used']:.2f}GB/{d['mem_total']:.2f}GB)", RESET, True)] + swap_segs + [(f"{d['swap_percent']:.0f}%", sc, True), (f" ({d['swap_used']:.2f}GB/{d['swap_total']:.2f}GB)", RESET, True)])
            if not args.bar and not args.barr: 
                b_swap = set_segmented_ram("ram_swap_b", d['apps_ratio'], d['sys_ratio'], d['free_ratio'], mc, DIM)
                sp = d['swap_percent']
                b_swap.set(sp / 100)
                b_swap.configure(progress_color=get_color(sc) if sp > 0 else TROUGH_COLOR)
                render_triple_markers(bars["ram_swap_b"][5], "swap", b_swap)

        if not args.proc:
            d = get_process_count()
            if d:
                s = d["states"]
                set_rich_line("proc", "🧩", [("Processes: ", RESET, False), (str(d['total']), RESET, True), (" (", RESET, False), ("run=", DIM, False), (str(s['running']), RESET, True), (", ", RESET, False), ("sleep=", DIM, False), (str(s['sleeping']), RESET, True), (", ", RESET, False), ("idle=", DIM, False), (str(s['idle']), RESET, True), (", ", RESET, False), ("stop=", DIM, False), (str(s['stopped']), RESET, True), (", ", RESET, False), ("zombie=", DIM, False), (str(s['zombie']), RESET, True), (")", RESET, False)])
                
        if not args.load:
            d = get_load_average()
            cpus = d["cpu_count"]
            def lcol(v): return RED if v >= cpus else YELLOW if v >= cpus*0.75 else RESET
            set_rich_line("load", "📊", [("Load average: ", RESET, False), (f"{d['load1']:.2f}", lcol(d['load1']), True), (" ", RESET, False), (f"{d['load5']:.2f}", lcol(d['load5']), True), (" ", RESET, False), (f"{d['load15']:.2f}", lcol(d['load15']), True)])

        if not args.disk:
            d = get_disk_usage()
            ultimos_valores_gui["disk"] = d['percent']
            dc = RED if d['percent'] >= 90 else YELLOW if d['percent'] >= 80 else RESET
            set_rich_line("disk", "🗄️", [("Disk used: ", RESET, False), (f"{d['percent']:.0f}%", dc, True), (f" ({d['used']:.2f}GB/{d['total']:.2f}GB)", RESET, True), (" - Read: ", RESET, False), (f"{d['read_speed']:.2f}MB/s", RESET, True), (" - Write: ", RESET, False), (f"{d['write_speed']:.2f}MB/s", RESET, True)])
            if not args.bar and not args.bard: set_bar("disk_b", d['percent'], dc)
            
            dt = get_nvme_temperature()
            if dt:
                tc = RED if dt['current'] >= 70 else YELLOW if dt['current'] >= 50 else RESET
                set_rich_line("dtemp", "🌡️", [("Disk temperature: ", RESET, False), (f"{dt['current']:.0f}°C", tc, True)])

        if not args.lan:
            d = get_lan_info()
            if d: set_rich_line("lan", "🌐", [("LAN IP: ", RESET, False), (d['ip'], RESET, True), (" - Speed: ", RESET, False), (f"{d['speed']}Mb/s", RESET, True)])

        if not args.wifi:
            d = get_wifi_info()
            if d:
                set_rich_line("wf_ip", "📶", [("WiFi IP: ", RESET, False), (d['ip'], RESET, True), (" - SSID: ", RESET, False), (d['ssid'], RESET, True)])
                ultimos_valores_gui["wifi"] = d['signal']
                wc = RED if d['signal'] < 25 else ORANGE if d['signal'] < 50 else YELLOW if d['signal'] < 75 else RESET
                set_rich_line("wf_sig", "📡", [("WiFi signal: ", RESET, False), (f"{d['signal']:.0f}%", wc, True), (" - Speed: ", RESET, False), (f"{d['speed']:.2f}Mb/s", RESET, True), (" - Down: ", RESET, False), (f"{d['down']:.2f}MB/s", RESET, True), (" - Up: ", RESET, False), (f"{d['up']:.2f}MB/s", RESET, True)])
                if not args.bar and not args.barw: set_bar("wf_b", d['signal'], wc)
                if d['temp']:
                    tc = RED if d['temp'] > 70 else YELLOW if d['temp'] > 50 else RESET
                    set_rich_line("wtemp", "🌡️", [("WiFi temperature: ", RESET, False), (f"{d['temp']:.0f}°C", tc, True)])

        if not args.bat:
            d = get_battery_info()
            if d:
                ultimos_valores_gui["bat"] = d['percent']
                bc = RED if d['percent'] <= 10 else ORANGE if d['percent'] <= 25 else YELLOW if d['percent'] <= 50 else RESET
                set_rich_line("bat", "🔋", [("Battery: ", RESET, False), (f"{d['percent']}%", bc, True), (d['time_str'], RESET, False), (" - Mode: ", RESET, False), (d['mode'], RESET, True)])
                if not args.bar and not args.bart: set_bar("bat_b", d['percent'], bc)

        if active_tags_current != active_tags_last[0]:
            for f in rows.values(): f.pack_forget()
            for f in bars_frames.values(): f.pack_forget()
            for tag in active_tags_current:
                if tag in rows:
                    rows[tag].pack(fill="x", padx=rows_indent.get(tag, 0), pady=0)
                elif tag in bars_frames:
                    bars_frames[tag].pack(fill="x", padx=bars_indent.get(tag, 0), pady=0)
            active_tags_last[0] = active_tags_current.copy()

        last_exec_ms[0] = (time.time() - t_start) * 1000
        it_count[0] += 1
        next_timer[0] = interval
        app.update_idletasks()
        app.wm_geometry("") 
        app.after(interval * 1000 if interval > 0 else 1000, update)

    def status_tick():
        uptime = format_uptime(int(time.time() - start_time))
        mem = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        icon = "🔁" if not args.icon else ""
        next_str = f" | Next: {next_timer[0]}/{interval}s" if interval > 0 else ""
        
        status_icon_lbl.configure(text=icon)
        status_text_lbl.configure(text=f"Run: {uptime} ({last_exec_ms[0]:.0f}ms) | Cycles: {it_count[0]} | {mem:.2f}MB{next_str}")
        
        if next_timer[0] > 0: next_timer[0] -= 1
        app.after(1000, status_tick)

    app.bind("<KeyPress-q>", lambda e: app.destroy())
    app.bind("<KeyPress-x>", lambda e: app.destroy())
    app.bind("<KeyPress-Q>", lambda e: app.destroy())
    app.bind("<KeyPress-X>", lambda e: app.destroy())

    status_tick()
    update()
    app.mainloop()

# =====================================================================
# 5.0_main_orchestrator - PUNTO DE ENTRADA Y ORQUESTADOR DE MODO
# =====================================================================
# Procesa argumentos (argparse), inicializa el hardware común y 
# decide si arranca el modo terminal (Bloque 3) o el modo gráfico (Bloque 4).

def parse_arguments():
    class CustomHelpFormatter(argparse.RawTextHelpFormatter):
        def _format_action_invocation(self, action):
            invocation = super()._format_action_invocation(action)
            if action.dest in ['barc', 'barf', 'barr', 'bard', 'barw', 'bart']:
                return "   " + invocation
            return invocation

    parser = argparse.ArgumentParser(
        usage=argparse.SUPPRESS,
        description=f"{BOLD}SysStat CLI/GUI{RESET} (System Status) - Version 3.47.4.20260604ia\n\n"
                    f"{BOLD}Repositorio:{RESET} {UNDERLINE}https://github.com/LiGNUxMan/SysStatCLI{RESET}\n\n"
                    f"{BOLD}Autor:{RESET} Axel O'BRIEN ({ITALIC}LiGNUxMan{RESET}) · {UNDERLINE}axelobrien@gmail.com{RESET}\n"
                    f"{BOLD}Colaboradores:{RESET} ChatGPT · OpenAI / Google Antigravity & Gemini\n\n"
                    f"{BOLD}Uso:{RESET} python3 sysstat_3.47.4i.py [tiempo] [opciones]\n"
                    f"     Durante la ejecución, puede presionar {BOLD}Q{RESET} o {BOLD}X{RESET} para salir.\n\n"
                    f"{BOLD}Tiempo:{RESET} Intervalo en segundos para repetir el script",
        epilog=f"{BOLD}Consejo:{RESET} Use -b -i para ocultar las barras de progreso e iconos\n"
               f"         (útil en terminales antiguas o sin soporte Unicode).",
        formatter_class=CustomHelpFormatter,
        add_help=False
    )

    parser._optionals.title = f"{BOLD}Opciones:{RESET} (Argumentos disponibles para omitir secciones)"

    parser.add_argument("-h", "-help", "--help", action="help", default=argparse.SUPPRESS, help="Muestra este mensaje de ayuda y sale")
    parser.add_argument("interval", nargs="?", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("-s", "-sys", action="store_true", dest="sys",  help="Muestra el nombre del sistema operativo y versión del kernel")
    parser.add_argument("-o", "-host", action="store_true", dest="host", help="Omitir nombre de la computadora y usuario")
    parser.add_argument("-u", "-up", action="store_true", dest="up",   help="Omitir tiempo de actividad, hora y fecha")
    parser.add_argument("-c", "-cpu", action="store_true", dest="cpu",  help="Omitir uso, frecuencia, modo y temperatura del CPU")
    parser.add_argument("-r", "-ram", action="store_true", dest="ram",  help="Omitir uso de memoria RAM y SWAP")
    parser.add_argument("-p", "-proc", action="store_true", dest="proc", help="Omitir procesos y sus estados")
    parser.add_argument("-l", "-load", action="store_true", dest="load", help="Omitir carga del sistema (Load average)")
    parser.add_argument("-d", "-disk", action="store_true", dest="disk", help="Omitir uso y temperatura del disco")
    parser.add_argument("-a", "-lan", action="store_true", dest="lan",  help="Omitir red cableada (LAN)")
    parser.add_argument("-w", "-wifi", action="store_true", dest="wifi", help="Omitir red WiFi y temperatura")
    parser.add_argument("-t", "-bat", action="store_true", dest="bat",  help="Omitir batería")
    parser.add_argument("-b", "-bar", action="store_true", dest="bar",  help="Omitir todas las barras de progreso")
    parser.add_argument("-bc", "-barc", action="store_true", dest="barc", help="Omitir la barra de uso de CPU")
    parser.add_argument("-bf", "-barf", action="store_true", dest="barf", help="Omitir la barra de frecuencia del CPU")
    parser.add_argument("-br", "-barr", action="store_true", dest="barr", help="Omitir la barra de uso de RAM")
    parser.add_argument("-bd", "-bard", action="store_true", dest="bard", help="Omitir la barra de uso de Disco")
    parser.add_argument("-bw", "-barw", action="store_true", dest="barw", help="Omitir la barra de señal WiFi")
    parser.add_argument("-bt", "-bart", action="store_true", dest="bart", help="Omitir la barra de Batería")
    parser.add_argument("-i", "-icon", action="store_true", dest="icon", help="Oculta los íconos decorativos")
    parser.add_argument("-g", "-gui", action="store_true", dest="gui", help="Arranca en modo interfaz gráfica (GUI)")

    return parser.parse_args()

args = parse_arguments()
if not terminal_supports_unicode():
    args.icon = True

def main():
    detect_hardware()
    init_metrics()
    time.sleep(1)
    if args.gui: render_gui(args.interval)
    else: render_cli(args.interval)

if __name__ == "__main__":
    main()
