#!/usr/bin/env python3
# 
# SysStat (System Status) - CORE
# 
# Autor: Axel O'BRIEN (LiGNUxMan) axelobrien@gmail.com
# 
# Colaboradores: ChatGPT (OpenAI) · Gemini/Antigravity (Google) · Claude (Anthropic)
#
# =====================================================================
# sysstat_core.py - MOTOR DE DATOS, MÉTRICAS Y ESTADÍSTICAS
# =====================================================================
# NUNCA dibuja nada en pantalla. Solo habla con el OS/hardware,
# calcula estadísticas y expone los datos via _stats_db.
# Quede proibido el uso de "print" y todas sus expreciones y variantes.
# Si uso "print" aca lo estoy haciendo mal!
# =====================================================================
#
# Version: 023
#
# =====================================================================

import datetime
import locale
import math
import os
import platform
import psutil
import pwd
import re
import socket
import subprocess
import time

# Códigos ANSI de color — exportados para que CLI/GUI puedan colorear valores
RESET  = "\033[0m"
ORANGE = "\033[38;5;208m"
RED    = "\033[31m"
YELLOW = "\033[93m"

# Variables internas de temporización
_start_time   = time.time()
_render_start = 0.0

# =============================================================
# FUNCIONES AUXILIARES
# =============================================================

def _format_duration(total_seconds: int) -> str:
    """Formatea una duración en segundos al formato 2d 01:00:40."""
    days      = total_seconds // 86400
    remaining = total_seconds % 86400
    hours     = remaining // 3600
    minutes   = (remaining % 3600) // 60
    seconds   = remaining % 60
    if days == 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"

def get_metric_color(key: str, value: float) -> str:
    """Retorna el código ANSI de color para un valor de métrica dado."""
    if value is None:
        return RESET

    if key == "cpu":
        if value < 40.0:  return RESET     # ⚪ (0-39%) Sistema relajado
        if value < 75.0:  return YELLOW    # 🟡 Actividad moderada (40-74%)
        if value < 90.0:  return ORANGE    # ⚠️ Carga pesada (75-89%)
        return RED                         # 🔴 El paciente está al límite (90-100%)

    elif key == "cpu_freq_pct":
        if value <= 25.9:  return RESET    # ⚪ (≤ 25.9%) Modo ahorro total (0.40Ghz - 0.80GHz) - ¡Cae acá el 80% del tiempo!
        if value <= 80.6:  return YELLOW   # 🟡 (26.0% - 80.6%) Ritmo de trabajo alegre / moderado
        if value < 100.0:  return ORANGE   # 🟠 (80.7% - 99.9%) Mandarina furiosa, en Turbo Boost
        return RED                         # 🔴 (=100.0%) On fire! Exigencia máxima

    elif key == "cpu_temp":
        if value < 37.0:  return RESET     # ⚪ (< 35°C) Normal
        if value < 50.0:  return YELLOW    # 🟡 (35-40°C) Atención (anterior 40)
        if value < 70.0:  return ORANGE    # 🟠 (40-60°C) Caliente (anterior 60)
        return RED                         # 🔴 (> 60°C) ¡Fiebre!

    elif key in ("ram", "swap"):
        if value < 50.0:  return RESET     # ⚪ (0-49.9%) ¡Acá cae la Swap el 100% de las veces y la RAM en reposo!
        if value < 75.0:  return YELLOW    # 🟡 (50.0-74.9%) La RAM de laburo diario.
        if value < 90.0:  return ORANGE    # 🟠 (75.0-89.9%) Mandarina de advertencia (¡Ojo con los tabs de Chrome/Firefox!)
        return RED                         # 🔴 (>= 90.0%) ¡Rojo furioso! El OOM Killer (Out Of Memory) está a la vuelta de la esquina

    elif key == "load":
        if value < _load_cpu_count * 0.70: return RESET     # ⚪ ≤ 70% — normal (¡El 95% del tiempo sale eyectado acá!)
        if value < _load_cpu_count * 0.85: return YELLOW    # 🟡 71-85% — carga alta
        if value < _load_cpu_count:        return ORANGE    # 🟠 86-100% — límite nominal
        return RED                                          # 🔴 > 100% — saturado, cola de espera

    elif key == "disk_used_pct":
        if value < 70.0:  return RESET     # ⚪ (< 70%) Normal
        if value < 80.0:  return YELLOW    # 🟡 (70-80%) Limón: Margen cómodo de maniobra
        if value < 90.0:  return ORANGE    # 🟠 (80-90%) Mandarina: Alerta seria, hay que operar
        return RED                         # 🔴 (>= 90%) ¡On Fire! A un paso del bloqueo del 95% (5% de disco reservado para root)

    elif key == "disk_temp":
        if value < 45.0:  return RESET     # ⚪ (< 45°C) Normal / Confort
        if value < 55.0:  return YELLOW    # 🟡 (45-55°C) Limón: Actividad sostenida
        if value < 65.0:  return ORANGE    # 🟠 (55-65°C) Mandarina: Throttling de hardware cercano
        return RED                         # 🔴 (>= 65°C) ¡On Fire! Peligro para los datos

    elif key == "wifi":
        if value >= 60.0: return RESET      # ⚪ OK: Blanco/Limpio (De 60% para arriba la conexión vuela)
        if value >= 40.0: return YELLOW     # 🟡 Warning: Señal media, perfectamente operativa pero bajo monitoreo
        if value >= 20.0: return ORANGE     # 🟠 High: Señal muy débil, la velocidad se desploma drásticamente
        return RED                          # 🔴 Critical: Desconexión inminente, pérdida masiva de paquetes

    elif key == "wifi_temp":
        if value < 50.0:  return RESET     # ⚪ (< 50°C) Normal
        if value < 60.0:  return YELLOW    # 🟡 (50-60°C) Atención
        if value < 70.0:  return ORANGE    # 🟠 (60-70°C) Alto
        return RED                         # 🔴 (>= 70°C) ¡Fiebre!

    elif key == "bat":
        if value <= 15.0: return RED       # 🔴 Critical: ¡Aviso de ACPI / Suspensión inminente!
        if value <= 30.0: return ORANGE    # 🟠 High: Modo ahorro estricto, hora de buscar el cargador
        if value <= 50.0: return YELLOW    # 🟡 Warning: Pasamos la mitad de la autonomía
        return RESET                       # ⚪ OK: Blanco / Limpio                      
    return RESET

# =============================================================
# _stats_db — ÚNICA FUENTE DE VERDAD
# =============================================================
# Estructura por tipo de dato:
#
#   _db_register_static(key)  →  solo value (datos que no acumulan mam)
#     "sys"          {"value": {"os_name": ..., "kernel_version": ...}}
#     "host"         {"value": {"hostname": ..., "user": ...}}
#     "up"           {"value": {"uptime": ..., "datetime": ...}}
#     "cpu_freq"     {"value": {"min_hz": ..., "max_hz": ...}}    ← hardware estático (en Hz)
#
#   _db_register_stat(key)  →  value + mam (count/min/max/sum)
#     "cpu"          {"value": {"avg": ..., "cores": ..., "color": ...}, mam...}
#     "cpu_freq_hz"  {"value": {"hz": ..., "governor": ...},             mam...}
#     "cpu_freq_pct" {"value": {"pct": ..., "color": ...},               mam...}
#     "cpu_temp"     {"value": {"temp": ..., "color": ...},              mam...}
#
# REGLA: Si el usuario pasó -cpu, cpu_init() nunca se llama
#        → ninguna clave "cpu*" existe en _stats_db
# =============================================================

_stats_db = {}
def _db_init():
    """Resetea la DB completa. Llamado una sola vez al inicio por hardware_init()."""
    global _stats_db
    _stats_db = {}

def _db_register_static(key: str):
    """Registra una clave de datos estáticos — solo value, sin mam."""
    _stats_db[key] = {"value": None}

def _db_register_stat(key: str):
    """Registra una clave con value + mam (count / min / max / sum)."""
    _stats_db[key] = {"value": None, "count": 0, "min": None, "max": None, "sum": 0.0}

def _db_set(key: str, value):
    """Escribe el valor actual de una clave."""
    _stats_db[key]["value"] = value

def _db_accumulate(key: str, numeric_value: float):
    """Acumula count/min/max/sum para claves registradas con _db_register_stat."""
    db = _stats_db[key]
    db["count"] += 1
    if db["min"] is None or numeric_value < db["min"]: db["min"] = numeric_value
    if db["max"] is None or numeric_value > db["max"]: db["max"] = numeric_value
    db["sum"]   += numeric_value

# ── API pública de la DB ──────────────────────────────────────
def get(key: str):
    """Retorna el valor actual de una clave."""
    return _stats_db[key]["value"]

def get_stats(key: str) -> dict:
    """Retorna avg/min/max (mam) de una clave."""
    db = _stats_db[key]
    return {
        "avg": db["sum"] / db["count"],
        "min": db["min"],
        "max": db["max"],
    }

def get_count(key: str) -> int:
    """Retorna el número de ciclos acumulados para una clave."""
    return _stats_db[key]["count"]

# =============================================================
# SYSTEM — OS y kernel
# 🐧 OS: Linux Mint 22.3 - ⚙️ Kernel version: 7.0.0-14-generic
# =============================================================
def sys_init():
    """Lee el OS y kernel una sola vez — son datos estáticos."""
    _db_register_static("sys")

    os_name        = "Unknown"
    kernel_version = "Unknown"

    try:
        with open("/etc/os-release", "r") as f:
            data = {}
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    data[k] = v.strip('"')
            os_name = data.get("PRETTY_NAME", "Unknown")
    except Exception:
        try:
            os_name = platform.system()
        except Exception:
            pass

    try:
        kernel_version = platform.release()
    except Exception:
        pass

    _db_set("sys", {"os_name": os_name, "kernel_version": kernel_version})

def sys_update():
    """Datos del OS son estáticos — no hay nada que actualizar en cada ciclo."""
    pass

# =============================================================
# HOST — hostname y usuario
# 🏠 Hostname: hal9001c - 👤 User: axel
# =============================================================
def host_init():
    """Lee hostname y usuario una sola vez — son datos estáticos."""
    _db_register_static("host")

    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = "Unknown"

    try:
        user = pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        user = os.environ.get("USER", "Unknown")

    _db_set("host", {"hostname": hostname, "user": user})

def host_update():
    """Datos del host son estáticos — no hay nada que actualizar en cada ciclo."""
    pass

# =============================================================
# UPTIME — tiempo de actividad y fecha/hora
# 🕒 Uptime: 1d 12:56:33 - 📅 Time and date: 22:36:40 10/06/26
# =============================================================
def uptime_init():
    """Registra la clave en la DB. La primera lectura real la hace uptime_update().
    También captura la fecha/hora de inicio de sesión — dato estático para el informe."""
    _db_register_static("up")
    _db_register_static("start_datetime")
    try:
        locale.setlocale(locale.LC_TIME, "")
        start_str = datetime.datetime.now().strftime("%X %x")
    except Exception:
        try:
            start_str = datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")
        except Exception:
            start_str = "Unknown"
    _db_set("start_datetime", start_str)

def uptime_update():
    """Lee y escribe en la DB el uptime actual y la fecha/hora."""
    uptime_str = "Unknown"
    try:
        with open("/proc/uptime", "r") as f:
            total_seconds = int(float(f.read().split()[0]))
        uptime_str = _format_duration(total_seconds)
    except Exception:
        pass

    datetime_str = "Unknown"
    try:
        locale.setlocale(locale.LC_TIME, "")
        datetime_str = datetime.datetime.now().strftime("%X %x")
    except Exception:
        try:
            datetime_str = datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")
        except Exception:
            pass

    _db_set("up", {"uptime": uptime_str, "datetime": datetime_str})

# =============================================================
# CPU — uso, frecuencia, temperatura
# 🎛️ CPU used: 12% (CPU0: 12% - CPU1: 12% - CPU2: 12% - CPU3: 13%)
# ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
# ⚡ CPU frequency: 0.80GHz - 🎚️ Scaling governor: powersave
# ████████░░░░░░░░░░░░░░░░░░░░░░░░
# 🌡️ CPU temperature: 36°C
# =============================================================
def cpu_init():
    """Detecta paths de frecuencia y sensor de temperatura. Primera lectura de CPU."""
    global _cpu_freq_cur_paths, _cpu_freq_min_path, _cpu_freq_max_path
    global _cpu_governor_path, _cpu_temp_sensor, _cpu_temp_index
    global _cpu_times_prev, _cpu_time_prev

    # Estas variables solo existen si cpu_init() fue llamado — si el usuario
    # pasó -cpu, esta función nunca se ejecuta y las variables nunca se crean.
    _cpu_freq_cur_paths = []       # ← lista de paths, uno por core
    _cpu_freq_min_path  = None
    _cpu_freq_max_path  = None
    _cpu_governor_path  = None
    _cpu_temp_sensor    = None
    _cpu_temp_index     = 0
    _cpu_times_prev     = None
    _cpu_time_prev      = None

    # Registra las claves en la DB:
    #   cpu          → uso actual (%) + mam (promedio global)
    #   cpu_core_N   → uso actual (%) + mam por core — N se conoce en cpu_init(), no en runtime
    #   cpu_freq     → datos estáticos del hardware (min_hz, max_hz)
    #   cpu_freq_hz  → frecuencia máxima actual + cores_hz + cores_at_max + governor + mam
    #   cpu_freq_pct → frecuencia actual (%) + mam ← para progress bar
    #   cpu_temp     → temperatura actual (°C) + mam
    _db_register_stat("cpu")
    _db_register_static("cpu_freq")
    _db_register_stat("cpu_freq_hz")
    _db_register_stat("cpu_freq_pct")
    _db_register_stat("cpu_temp")
    # cpu_core_N — registro aquí, donde corresponde: el CPU ya está en la PC,
    # los cores no cambian en runtime. Una sola lectura, nunca más.
    num_cores = len(psutil.cpu_times(percpu=True))
    for i in range(num_cores):
        _db_register_stat(f"cpu_core_{i}")

    # Detección de paths de frecuencia — de todos los cores, no solo cpu0
    cpu_sys_path = "/sys/devices/system/cpu"
    first_freq_path = None
    if os.path.isdir(cpu_sys_path):
        for cpu in sorted(os.listdir(cpu_sys_path)):
            if not cpu.startswith("cpu") or not cpu[3:].isdigit():
                continue
            freq_path = os.path.join(cpu_sys_path, cpu, "cpufreq")
            if os.path.isdir(freq_path):
                cur_path = os.path.join(freq_path, "scaling_cur_freq")
                if os.path.exists(cur_path):
                    _cpu_freq_cur_paths.append(cur_path)
                if first_freq_path is None:
                    first_freq_path = freq_path  # ← el primero sirve para min/max/governor
    if first_freq_path:
        _cpu_freq_min_path = os.path.join(first_freq_path, "cpuinfo_min_freq")
        _cpu_freq_max_path = os.path.join(first_freq_path, "cpuinfo_max_freq")
        _cpu_governor_path = os.path.join(first_freq_path, "scaling_governor")

        # Lee los valores estáticos del hardware una sola vez — se guardan en Hz
        try:
            with open(_cpu_freq_min_path) as f: min_hz = int(f.read().strip())
            with open(_cpu_freq_max_path) as f: max_hz = int(f.read().strip())
            _db_set("cpu_freq", {"min_hz": min_hz, "max_hz": max_hz})
        except Exception:
            pass

    # Detección de sensor de temperatura
    try:
        temps = psutil.sensors_temperatures()
        for name in ("coretemp", "k10temp", "acpitz"):
            if name in temps:
                _cpu_temp_sensor = name
                break
    except Exception:
        pass

    # Primera lectura — pausa breve para que el primer delta sea significativo
    try:
        _cpu_times_prev = psutil.cpu_times(percpu=True)
        _cpu_time_prev  = time.time()
        time.sleep(0.2)
    except Exception:
        pass

def cpu_update():
    """Lee CPU, frecuencia y temperatura, y escribe los resultados en la DB."""
    global _cpu_times_prev, _cpu_time_prev

    # ── Uso por core y promedio ───────────────────────────────
    try:
        cpu_times_now = psutil.cpu_times(percpu=True)
        core_usage    = []
        for prev, now in zip(_cpu_times_prev, cpu_times_now):
            total_diff = sum(now) - sum(prev)
            idle_diff  = now.idle - prev.idle
            u = 100.0 * (1 - idle_diff / total_diff) if total_diff else 0.0
            core_usage.append(round(max(0.0, min(100.0, u))))
        _cpu_times_prev = cpu_times_now
        _cpu_time_prev  = time.time()
        avg = sum(core_usage) / len(core_usage) if core_usage else 0.0
        _db_accumulate("cpu", avg)
        _db_set("cpu", {
            "avg":   round(avg),
            "cores": core_usage,
            "color": get_metric_color("cpu", avg),
        })
        # Acumula min/avg/max por core individual — claves ya registradas en cpu_init()
        for i, usage in enumerate(core_usage):
            _db_accumulate(f"cpu_core_{i}", usage)
            _db_set(f"cpu_core_{i}", {"pct": usage, "color": get_metric_color("cpu", usage)})
    except Exception:
        _db_set("cpu", {"avg": 0, "cores": [], "color": RESET})

    # ── Frecuencia — todos los cores leídos de una sola vez ──
    if _cpu_freq_cur_paths:
        try:
            hw      = get("cpu_freq") or {}
            max_hz  = hw.get("max_hz", 0)
            # Lee TODOS los cores en una sola pasada — sin condición de carrera
            cores_hz = []
            for p in _cpu_freq_cur_paths:
                try:
                    with open(p) as f: cores_hz.append(int(f.read().strip()))
                except Exception:
                    cores_hz.append(0)
            cur_hz       = max(cores_hz) if cores_hz else 0
            # 5KHz de tolerancia — granularidad real de intel_pstate (saltos de 10 en 10MHz)
            cores_at_max = [i for i, hz in enumerate(cores_hz) if hz >= cur_hz - 5_000]
            with open(_cpu_governor_path) as f: governor = f.read().strip()
            pct        = (cur_hz / max_hz) * 100.0 if max_hz > 0 else 0.0
            pct_capped = min(pct, 100.0)
            _db_accumulate("cpu_freq_hz", cur_hz)
            _db_set("cpu_freq_hz", {
                "hz":          cur_hz,
                "cores_hz":    cores_hz,       # ← Hz de cada core — misma lectura, sin carrera
                "cores_at_max": cores_at_max,  # ← cores dentro del margen de 10KHz del máximo
                "governor":    governor,
            })
            _db_accumulate("cpu_freq_pct", pct_capped)
            _db_set("cpu_freq_pct", {
                "pct":   pct_capped,
                "color": get_metric_color("cpu_freq_pct", pct_capped),
            })
        except Exception:
            pass

    # ── Temperatura ───────────────────────────────────────────
    if _cpu_temp_sensor:
        try:
            temps = psutil.sensors_temperatures()
            if _cpu_temp_sensor in temps:
                t = temps[_cpu_temp_sensor][_cpu_temp_index].current
                _db_accumulate("cpu_temp", float(round(t)))
                _db_set("cpu_temp", {"temp": int(round(t)), "color": get_metric_color("cpu_temp", t)})
        except Exception:
            pass

# =============================================================
# RAM / SWAP — uso de memoria
# 📟 RAM used: 53% (8.16GB / 15.49GB) - 💾 Swap used: 0% (0.00GB / 0.00GB)
# ████████████████▒▒▒▒▒▒▒▒▒▒░░░░░░ - ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
# =============================================================
def ram_init():
    """Registra las claves RAM y Swap en la DB — % y KB para mam de ambos."""
    _db_register_stat("ram")
    _db_register_stat("ram_kb")
    _db_register_stat("swap")
    _db_register_stat("swap_kb")

def ram_update():
    """Lee /proc/meminfo y escribe RAM y Swap en la DB."""
    try:
        with open("/proc/meminfo") as f:
            valores = {}
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    valores[parts[0].rstrip(":")] = int(parts[1])

        # RAM — valores en KB, se convierten a GB para guardar
        mem_total     = valores["MemTotal"]
        mem_available = valores["MemAvailable"]
        mem_free      = valores["MemFree"]
        mem_used      = mem_total - mem_available
        mem_pct       = (mem_used / mem_total) * 100 if mem_total > 0 else 0.0
        apps_ratio    = mem_used / mem_total if mem_total > 0 else 0.0
        free_ratio    = mem_free / mem_total if mem_total > 0 else 0.0

        _db_accumulate("ram", mem_pct)
        _db_accumulate("ram_kb", mem_used)
        _db_set("ram", {
            "pct":        round(mem_pct),
            "used_kb":    mem_used,
            "total_kb":   mem_total,
            "apps_ratio": apps_ratio,
            "free_ratio": free_ratio,
            "color":      get_metric_color("ram", mem_pct),
        })

        # Swap
        swap_total = valores.get("SwapTotal", 0)
        swap_free  = valores.get("SwapFree",  0)
        swap_used  = swap_total - swap_free
        swap_pct   = (swap_used / swap_total) * 100 if swap_total > 0 else 0.0

        _db_accumulate("swap", swap_pct)
        _db_accumulate("swap_kb", swap_used)
        _db_set("swap", {
            "pct":      round(swap_pct),
            "used_kb":  swap_used,
            "total_kb": swap_total,
            "color":    get_metric_color("swap", swap_pct),
        })

    except Exception:
        pass

# =============================================================
# PROCESSES — conteo y estados de procesos
# 📋 Processes: 346 (R: 1 - S: 243 - D: 0 - I: 101 - T: 0 - Z: 0)
# =============================================================
def proc_init():
    """Registra 'proc' en la DB con mam — acumula el total de procesos."""
    _db_register_stat("proc")

def proc_update():
    """Mundo de Procesos e Hilos unificado con matemática exacta basada en Hilos (Opción A)."""
    try:
        running = 0
        blocked = 0
        total_threads = 0

        # 1. Contar Procesos Base (PIDs principales en /proc)
        total_proc = sum(1 for pid in os.listdir("/proc") if pid.isdigit())

        # 2. Hilos activos directamente desde el planificador del kernel
        with open("/proc/stat", "r") as f:
            for line in f:
                if line.startswith("procs_running"):
                    running = int(line.split()[1])
                elif line.startswith("procs_blocked"):
                    blocked = int(line.split()[1])
                    break

        # 3. Total absoluto de Hilos (Tasks) en el sistema
        with open("/proc/loadavg", "r") as f:
            total_threads = int(f.read().split()[3].split("/")[1])

        # 4. Opción A: Hilos durmientes exactos (Total Hilos - Activos - Bloqueos)
        sleeping_threads = total_threads - running - blocked

        _db_accumulate("proc", total_proc)
        _db_set("proc", {
            "total":      total_proc,
            "threads":    total_threads,
            "running":    running,
            "disk_sleep": blocked,
            "sleeping":   max(0, sleeping_threads)
        })
    except Exception:
        pass

# =============================================================
# LOAD AVERAGE — carga del sistema
# 📊 Load average: 0.45 0.32 0.28
# =============================================================
def load_init():
    """Detecta la cantidad de hilos del CPU y registra 'load' en la DB."""
    global _load_cpu_count
    _load_cpu_count = os.cpu_count() or 1
    _db_register_stat("load")

def load_update():
    """Lee /proc/loadavg y escribe los 3 valores con sus colores en la DB.
    Solo load1 (X) se acumula en mam — load5 y load15 se guardan solo como valor."""
    try:
        with open("/proc/loadavg") as f:
            parts  = f.read().split()
            load1  = float(parts[0])
            load5  = float(parts[1])
            load15 = float(parts[2])
        _db_accumulate("load", load1)
        _db_set("load", {
            "load1":   load1,
            "load5":   load5,
            "load15":  load15,
            "color1":  get_metric_color("load", load1),
            "color5":  get_metric_color("load", load5),
            "color15": get_metric_color("load", load15),
        })
    except Exception:
        pass

# =============================================================
# DISK — uso, velocidad I/O y temperatura
# 🗄️ Disk used: 55% (258.92GB/467.91GB) - 📥 R: 0.00MB/s - 📤 W: 0.17MB/s
# █████████████████░░░░░░░░░░░░░░░
# 🌡️ Disk temperature: 33°C
# =============================================================
def disk_init():
    """Detecta sensor de temperatura NVMe. Primera lectura de I/O para el delta."""
    global _disk_temp_sensor, _disk_temp_label
    global _disk_io_prev, _disk_io_time_prev

    _disk_temp_sensor  = None
    _disk_temp_label   = None
    _disk_io_prev      = None
    _disk_io_time_prev = None

    _db_register_stat("disk")
    _db_register_stat("disk_kb")
    _db_register_stat("disk_read")
    _db_register_stat("disk_write")
    _db_register_stat("disk_temp")

    try:
        temps = psutil.sensors_temperatures()
        if "nvme" in temps:
            for entry in temps["nvme"]:
                if entry.current is not None:
                    _disk_temp_sensor = "nvme"
                    _disk_temp_label  = entry.label
                    break
    except Exception:
        pass

    try:
        _disk_io_prev      = psutil.disk_io_counters()
        _disk_io_time_prev = time.time()
    except Exception:
        pass

def disk_update():
    """Lee uso de '/', velocidad I/O y temperatura, y escribe en la DB."""
    global _disk_io_prev, _disk_io_time_prev

    # ── Uso de disco — punto de montaje fijo "/" ──────────────
    try:
        st       = os.statvfs("/")
        total_kb = st.f_blocks * st.f_frsize / 1024
        used_kb  = (st.f_blocks - st.f_bfree) * st.f_frsize / 1024
        used_pct = (used_kb / total_kb) * 100 if total_kb > 0 else 0.0

        # ── Velocidad I/O — delta de bytes / delta de tiempo ──
        read_speed  = 0.0
        write_speed = 0.0
        io_now      = psutil.disk_io_counters()
        time_now    = time.time()
        if _disk_io_prev:
            interval    = time_now - _disk_io_time_prev or 0.0001
            read_diff   = max(0, io_now.read_bytes  - _disk_io_prev.read_bytes)
            write_diff  = max(0, io_now.write_bytes - _disk_io_prev.write_bytes)
            read_speed  = read_diff  / (1_048_576 * interval)
            write_speed = write_diff / (1_048_576 * interval)
        _disk_io_prev, _disk_io_time_prev = io_now, time_now

        _db_accumulate("disk", used_pct)
        _db_accumulate("disk_kb", used_kb)
        _db_set("disk", {
            "pct":         round(used_pct),
            "used_kb":     used_kb,
            "total_kb":    total_kb,
            "read_speed":  read_speed,
            "write_speed": write_speed,
            "color":       get_metric_color("disk_used_pct", used_pct),
        })

        _db_accumulate("disk_read", read_speed)
        _db_set("disk_read", {"speed": read_speed})

        _db_accumulate("disk_write", write_speed)
        _db_set("disk_write", {"speed": write_speed})
    except Exception:
        pass

    # ── Temperatura NVMe ───────────────────────────────────────
    if _disk_temp_sensor:
        try:
            temps   = psutil.sensors_temperatures()
            entries = temps.get(_disk_temp_sensor, [])
            t = None
            if _disk_temp_label:
                for entry in entries:
                    if entry.label == _disk_temp_label:
                        t = entry.current
                        break
            elif entries:
                t = entries[0].current
            if t is not None:
                _db_accumulate("disk_temp", float(round(t)))
                _db_set("disk_temp", {"temp": int(round(t)), "color": get_metric_color("disk_temp", t)})
        except Exception:
            pass

# =============================================================
# LAN — IP, velocidad, duplex e I/O (placa cableada)
# 🌐 LAN IP: 192.168.0.117 - Speed: 100Mb/s(F) - ⬇️ D: 0.00MB/s - ⬆️ U: 0.00MB/s
# =============================================================
# Se busca en CADA ciclo (no en lan_init) por la misma razón que WiFi:
# puede ser USB y conectarse/desconectarse en caliente. Solo se muestra
# si hay placa Y tiene IP asignada. Si hay dos placas, se toma la primera.
# =============================================================
def lan_init():
    """Registra las claves LAN en la DB. No detecta hardware — eso es en caliente, en lan_update()."""
    global _lan_io_prev, _lan_io_time_prev, _lan_iface_prev

    _lan_io_prev      = None
    _lan_io_time_prev = None
    _lan_iface_prev   = None

    _db_register_static("lan")
    _db_register_stat("lan_speed")
    _db_register_stat("lan_down")
    _db_register_stat("lan_up")

def _lan_find_iface():
    """Busca en caliente una placa cableada activa y con IP asignada. None si no hay."""
    try:
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        for name, stat in stats.items():
            if name == "lo" or not stat.isup:
                continue
            if os.path.isdir(f"/sys/class/net/{name}/wireless"):
                continue
            if any(a.family == socket.AF_INET for a in addrs.get(name, [])):
                return name
    except Exception:
        pass
    return None

def lan_update():
    """Detecta la placa LAN en caliente y, si está conectada, escribe sus datos en la DB."""
    global _lan_io_prev, _lan_io_time_prev, _lan_iface_prev

    iface = _lan_find_iface()
    if not iface:
        _db_set("lan", None)
        _lan_iface_prev = None
        return

    if iface != _lan_iface_prev:
        _lan_io_prev    = None
        _lan_iface_prev = iface

    try:
        addrs = psutil.net_if_addrs()
        ip    = next((a.address for a in addrs.get(iface, []) if a.family == socket.AF_INET), "N/A")

        stat   = psutil.net_if_stats().get(iface)
        speed  = stat.speed if stat else 0
        duplex = "F" if stat and stat.duplex == 2 else "H"

        down, up = 0.0, 0.0
        io_now   = psutil.net_io_counters(pernic=True).get(iface)
        time_now = time.time()
        if _lan_io_prev and io_now:
            interval = time_now - _lan_io_time_prev or 0.0001
            down     = max(0, io_now.bytes_recv - _lan_io_prev.bytes_recv) / (1_048_576 * interval)
            up       = max(0, io_now.bytes_sent - _lan_io_prev.bytes_sent) / (1_048_576 * interval)
        _lan_io_prev, _lan_io_time_prev = io_now, time_now

        _db_accumulate("lan_speed", speed)
        _db_accumulate("lan_down", down)
        _db_accumulate("lan_up", up)
        _db_set("lan", {"ip": ip, "speed": speed, "duplex": duplex, "down": down, "up": up})
    except Exception:
        _db_set("lan", None)

# =============================================================
# 🗼 WIFI — IP, SSID, señal, velocidad, I/O y temperatura
# 📶 WiFi IP: 192.168.0.208 - SSID: OBRIEN 5
# 📡 WiFi signal: 54% - Speed: 117.00Mb/s - ⬇️ D: 0.01MB/s - ⬆️ U: 0.00MB/s
# 🌡️ WiFi temperature: 43°C
# =============================================================
# La placa se busca en CADA ciclo (no en wifi_init) porque puede ser
# USB y el usuario la conecta/desconecta en caliente. Solo se muestra
# si hay placa Y tiene IP asignada — sin IP, es como si no existiera.
# =============================================================
def wifi_init():
    """Registra las claves WiFi en la DB. No detecta hardware — eso es en caliente, en wifi_update()."""
    global _wifi_io_prev, _wifi_io_time_prev, _wifi_iface_prev

    _wifi_io_prev      = None
    _wifi_io_time_prev = None
    _wifi_iface_prev   = None

    _db_register_stat("wifi")
    _db_register_stat("wifi_speed")
    _db_register_stat("wifi_down")
    _db_register_stat("wifi_up")
    _db_register_stat("wifi_temp")

def _wifi_find_iface():
    """Busca en caliente una placa WiFi activa y con IP asignada. None si no hay."""
    try:
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        for name, stat in stats.items():
            if name == "lo" or not stat.isup:
                continue
            if not os.path.isdir(f"/sys/class/net/{name}/wireless"):
                continue
            if any(a.family == socket.AF_INET for a in addrs.get(name, [])):
                return name
    except Exception:
        pass
    return None

def wifi_update():
    """Detecta la placa WiFi en caliente y, si está conectada, escribe sus datos en la DB."""
    global _wifi_io_prev, _wifi_io_time_prev, _wifi_iface_prev

    iface = _wifi_find_iface()
    if not iface:
        _db_set("wifi", None)
        _wifi_iface_prev = None
        return

    # Cambio de placa (USB distinta) → reinicia el delta de I/O
    if iface != _wifi_iface_prev:
        _wifi_io_prev    = None
        _wifi_iface_prev = iface

    try:
        addrs  = psutil.net_if_addrs()
        ip     = next((a.address for a in addrs.get(iface, []) if a.family == socket.AF_INET), "N/A")

        output = subprocess.run(["iw", "dev", iface, "link"], capture_output=True, text=True, timeout=1).stdout
        if "Not connected" in output or not output:
            _db_set("wifi", None)
            return

        ssid_m   = re.search(r"SSID: (.+)", output)
        signal_m = re.search(r"signal: (-?\d+) dBm", output)
        speed_m  = re.search(r"bitrate: ([\d.]+) MBit/s", output)
        if not (ssid_m and signal_m and speed_m):
            _db_set("wifi", None)
            return

        ssid       = ssid_m.group(1).strip()
        signal_dbm = int(signal_m.group(1))
        speed      = float(speed_m.group(1))
        signal_pct = max(0, min(100, 2 * (signal_dbm + 100)))

        # ── Velocidad I/O — delta de bytes / delta de tiempo ──
        down, up = 0.0, 0.0
        io_now   = psutil.net_io_counters(pernic=True).get(iface)
        time_now = time.time()
        if _wifi_io_prev and io_now:
            interval = time_now - _wifi_io_time_prev or 0.0001
            down     = max(0, io_now.bytes_recv - _wifi_io_prev.bytes_recv) / (1_048_576 * interval)
            up       = max(0, io_now.bytes_sent - _wifi_io_prev.bytes_sent) / (1_048_576 * interval)
        _wifi_io_prev, _wifi_io_time_prev = io_now, time_now

        _db_accumulate("wifi", signal_pct)
        _db_accumulate("wifi_speed", speed)
        _db_accumulate("wifi_down", down)
        _db_accumulate("wifi_up", up)
        _db_set("wifi", {
            "ip":     ip,
            "ssid":   ssid,
            "signal": round(signal_pct),
            "speed":  speed,
            "down":   down,
            "up":     up,
            "color":  get_metric_color("wifi", signal_pct),
        })

        # ── Temperatura — sensor buscado en caliente, junto con la placa ──
        temp = None
        try:
            temps = psutil.sensors_temperatures()
            for name in temps:
                if "iwlwifi" in name:
                    temp = temps[name][0].current
                    break
        except Exception:
            pass
        if temp is not None:
            _db_accumulate("wifi_temp", float(round(temp)))
            _db_set("wifi_temp", {"temp": int(round(temp)), "color": get_metric_color("wifi_temp", temp)})
        else:
            _db_set("wifi_temp", None)

    except Exception:
        _db_set("wifi", None)

# =============================================================
# CONTROL DE BUCLE Y BARRA DE ESTADO
# 🔁 Run: 00:36:15 (27ms) | Cycles: 216 | 15.27MB | Next: 9/10s
# =============================================================
def setup_cycle_control(config):
    """Determina el comportamiento del bucle y el valor inicial del contador."""
    if config.interval is None and config.cycles is None:
        return False, 1
    elif config.cycles is None:
        return True, 1
    else:
        return True, config.cycles

def start_render_timer():
    """Registra el inicio exacto del procesamiento de datos."""
    global _render_start
    _render_start = time.perf_counter()

def get_runtime() -> str:
    """Retorna el tiempo total transcurrido desde el arranque — para el informe final."""
    total_seconds = int(time.time() - _start_time)
    return _format_duration(total_seconds)

def get_start_timestamp() -> str:
    """Retorna la hora de arranque del script en formato fijo AñoMesDía_HoraMinSeg.
    Independiente del locale — pensado para nombres de archivo (informe TXT/LOG)."""
    return datetime.datetime.fromtimestamp(_start_time).strftime("%Y%m%d_%H%M%S")

def get_status_data(cycle_counter, cycles, interval=None, elapsed_wait=0) -> dict:
    """Retorna los datos de la barra de estado — valores puros, sin presentación."""
    total_seconds = int(time.time() - _start_time)
    elapsed_str   = _format_duration(total_seconds)

    delta     = time.perf_counter() - _render_start
    render_ms = int(delta * 1000)
    if render_ms == 0 and delta > 0:
        render_ms = 1

    cycle_display = f"-{cycle_counter}" if cycles is not None else str(cycle_counter)

    try:
        mem_mb  = psutil.Process().memory_info().rss / 1_048_576
        mem_str = f"{mem_mb:.2f}MB"
    except Exception:
        mem_str = "N/A"

    next_str = ""
    if interval is not None:
        remaining = max(1, math.ceil(interval - elapsed_wait))
        next_str  = f" | Next: {remaining}/{interval}s"

    return {
        "runtime_str":   elapsed_str,
        "render_ms":     render_ms,
        "cycle_display": cycle_display,
        "mem_str":       mem_str,
        "next_str":      next_str,
    }

# =============================================================
# INIT PRINCIPAL — llamado una sola vez al arranque
# =============================================================

def hardware_init(config):
    """Único punto de entrada. Llama solo a los _init que el usuario no omitió.
    Si una sección fue omitida con -flag, su clave NUNCA entra a _stats_db."""
    _db_init()
    if config.sys:  sys_init()
    if config.host: host_init()
    if config.up:   uptime_init()
    if config.cpu:  cpu_init()
    if config.ram:  ram_init()
    if config.proc: proc_init()
    if config.load: load_init()
    if config.disk: disk_init()
    if config.lan:  lan_init()
    if config.wifi: wifi_init()
    # if config.bat:  bat_init()    ← próximamente
