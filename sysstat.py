#!/usr/bin/env python3
# 
# SysStat (System Status) - MAIN
# 
# Autor: Axel O'BRIEN (LiGNUxMan) axelobrien@gmail.com
# 
# Colaboradores: ChatGPT (OpenAI) · Gemini/Antigravity (Google) · Claude (Anthropic)
#
# "La perfección se alcanza, no cuando no hay nada más que añadir, sino cuando no queda nada más que quitar" (Antoine de Saint-Exupéry)
#
# =============================================
# sysstat.py - ORQUESTADOR PRINCIPAL, PARSEADOR
# =============================================
#
# Version: 022
#
# =============================================

import sys
import os
import argparse

sys.dont_write_bytecode = True  # Evita __pycache__. Sacar esta línea si algún día se quiere la precompilacion bytecode.

# Convención estándar de Python para la versión del programa
__version__ = "5.46.1.20260710f Beep"

# MODIFICADORES DE TEXTO ANSI (Para la estructura de la ayuda)
RESET     = "\033[0m"
BOLD      = "\033[1m"
DIM       = "\033[2m"
ITALIC    = "\033[3m" if os.environ.get("TERM", "") not in ("linux", "dumb") else "\033[2m"
REVERSE   = "\033[7m"
UNDERLINE = "\033[4m"
RED       = "\033[31m"
YELLOW    = "\033[33m"

class SysStatConfig:
    def __init__(self):               
        # Flags de secciones (True = mostrar, False = omitir con -flag)
        self.sys  = True      # Sistema (-s lo apaga)
        self.host = True      # Hostname/Usuario (-o lo apaga)
        self.up   = True      # Uptime (-u lo apaga)
        self.cpu  = True      # CPU (-c lo apaga)
        self.cpun = True      # Detalle por núcleo, CPU0..N (-cn lo apaga)
        self.ram  = True      # RAM (-r lo apaga)
        self.proc = True      # Procesos (-p lo apaga)
        self.load = True      # Carga del Sistema (-l lo apaga)
        self.disk = True      # Disco (-d lo apaga)
        self.lan  = True      # LAN (-a lo apaga)
        self.wifi = True      # WiFi (-w lo apaga)
        self.bat  = True      # Batería (-t lo apaga)

        # Flags de renderizado visual (True = mostrar, False = omitir con -flag)
        self.bar  = True      # Todas las barras (-b lo apaga)
        self.barc = True      # Barra CPU (-bc lo apaga)
        self.barf = True      # Barra freq (-bf lo apaga)
        self.barr = True      # Barra RAM (-br lo apaga)
        self.bard = True      # Barra Disco (-bd lo apaga)
        self.barw = True      # Barra WiFi (-bw lo apaga)
        self.bart = True      # Barra Batería (-bt lo apaga)

        self.icon = True      # Íconos decorativos (-i lo apaga)
        self.beep = True      # Alerta sonora ante nuevo rojo (-e lo apaga)

        # Interfaz
        self.cli = True       # Modo CLI (-g lo apaga (activa GUI))

        # Parámetros de control de bucle
        self.interval = None  # Intervalo en segundos
        self.cycles = None    # Cantidad de repeticiones

def parse_arguments():
    """Procesa los argumentos de la línea de comandos usando tu formateador personalizado."""
    class CustomHelpFormatter(argparse.RawTextHelpFormatter):
        def _format_action_invocation(self, action):
            invocation = super()._format_action_invocation(action)
            if action.dest in ['barc', 'barf', 'barr', 'bard', 'barw', 'bart']:
                return "   " + invocation
            return invocation

    parser = argparse.ArgumentParser(
        usage=argparse.SUPPRESS,
        description=f"{BOLD}SysStat CLI/GUI{RESET} (System Status) - Version {__version__}\n\n"
                    f"{BOLD}Repositorio:{RESET} {UNDERLINE}https://github.com/LiGNUxMan/SysStat{RESET}\n\n"
                    f"{BOLD}Autor:{RESET} Axel O'BRIEN ({ITALIC}LiGNUxMan{RESET}) · {UNDERLINE}axelobrien@gmail.com{RESET}\n"
                    f"{BOLD}Colaboradores:{RESET} ChatGPT (OpenAI) · Gemini/Antigravity (Google) · Claude (Anthropic)\n\n"
                    f"{BOLD}Uso:{RESET} ./sysstat.py [intervalo] [-ciclos] [opciones]\n"
                    f"     Durante la ejecución, puede presionar {BOLD}Q{RESET} o {BOLD}X{RESET} para salir.\n\n"
                    f"{BOLD}Parámetros de bucle:{RESET}\n"
                    f"  {BOLD}intervalo{RESET}  Número limpio (ej. 5): Cada cuantos segundos se ejecutara el script.\n"
                    f"  {BOLD}-ciclos{RESET}    Número con guion (ej. -10): Cuantas veces se ejecutara el script.",
        epilog=f"{BOLD}Consejo:{RESET} Use -b -i para ocultar las barras de progreso e iconos\n"
               f"         (útil en terminales antiguas o sin soporte Unicode).\n\n"
               f"{BOLD}Ejemplos:{RESET}\n"
               f"  ./sysstat.py            → Ejecuta una sola vez\n"
               f"  ./sysstat.py 60         → Ejecuta cada 60 segundos\n"
               f"  ./sysstat.py -r -w      → Ejecuta una sola vez, omitiendo RAM y WiFi\n"
               f"  ./sysstat.py -s -b 10   → Ejecuta cada 10s, omit. datos del sist. y barras\n"
               f"  ./sysstat.py -g -100 15 → Ejecuta 100 veces en modo GUI, cada 15s\n\n"
               f"  ./sysstat.py -s -o -u -p -l 60\n"
               f"  CPU used: {BOLD}13%{RESET} ({ITALIC}0:{RESET} {BOLD}12%{RESET} - {ITALIC}1:{RESET} {BOLD}12%{RESET} - {ITALIC}2:{RESET} {BOLD}8%{RESET} - {ITALIC}3:{RESET} {BOLD}21%{RESET})\n"
               f"  ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░\n"
               f"  CPU frequency: {BOLD}{YELLOW}1.20GHz{RESET} ({ITALIC}0,2,3{RESET}) - Scaling governor: {BOLD}powersave{RESET}\n"
               f"  {YELLOW}████████████{RESET}░░░░░░░░░░░░░░░░░░░░░\n"
               f"  CPU temperature: {BOLD}35°C{RESET}\n"
               f"  RAM used: {BOLD}43%{RESET} ({BOLD}6.64GB/15.49GB{RESET}) - Swap used: {BOLD}0%{RESET} ({BOLD}0.00GB/0.00GB{RESET})\n"
               f"  ██████████████▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒░░ - ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░\n"
               f"  Disk used: {BOLD}52%{RESET} ({BOLD}242.59GB/467.91GB{RESET}) - R: {BOLD}0.00MB/s{RESET} - W: {BOLD}0.17MB/s{RESET}\n"
               f"  █████████████████░░░░░░░░░░░░░░░░\n"
               f"  Disk temperature: {BOLD}32°C{RESET}\n"
               f"  LAN IP: {BOLD}192.168.0.117{RESET} - Spd: {BOLD}1Gb/s(F){RESET} - D: {BOLD}0.53MB/s{RESET} - U: {BOLD}0.01MB/s{RESET}\n"
               f"  WiFi IP: {BOLD}192.168.0.208{RESET} - SSID: {BOLD}OBRIEN 5{RESET}\n"
               f"  WiFi signal: {BOLD}{YELLOW}56%{RESET} - Spd: {BOLD}234.00Mb/s{RESET} - D: {BOLD}0.01MB/s{RESET} - U: {BOLD}0.00MB/s{RESET}\n"
               f"  {YELLOW}██████████████████{RESET}░░░░░░░░░░░░░░░\n"
               f"  WiFi temperature: {BOLD}40°C{RESET}\n"
               f"  Battery: {BOLD}98%{RESET} - Time: {BOLD}5h 3m{RESET} - Mode: {BOLD}Discharging{RESET}\n"
               f"  ████████████████████████████████░\n"
               f"  {DIM}{REVERSE}Run: 1 day, 13:24:20 (150ms) | Cycles: 564 | 16.12MB | Next: 10/60s{RESET}",
        formatter_class=CustomHelpFormatter,
        add_help=False
    )

    parser._optionals.title = f"{BOLD}Opciones:{RESET} Argumentos disponibles"

    parser.add_argument("-h", "-help", "--help", action="help", default=argparse.SUPPRESS, help="Muestra este mensaje de ayuda y sale")
    parser.add_argument("interval", nargs="?", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("-s", "-sys", action="store_true", dest="sys",  help="Omite el nombre del sistema operativo y versión del kernel")
    parser.add_argument("-o", "-host", action="store_true", dest="host", help="Omite nombre de la computadora y usuario")
    parser.add_argument("-u", "-up", action="store_true", dest="up",   help="Omite tiempo de actividad, hora y fecha")
    parser.add_argument("-c", "-cpu", action="store_true", dest="cpu",  help="Omite uso, frecuencia, modo y temperatura del CPU")
    parser.add_argument("-cn", "-cpun", action="store_true", dest="cpun", help="Omite el detalle discriminado por núcleo")
    parser.add_argument("-r", "-ram", action="store_true", dest="ram",  help="Omite uso de memoria RAM y SWAP")
    parser.add_argument("-p", "-proc", action="store_true", dest="proc", help="Omite procesos y sus estados")
    parser.add_argument("-l", "-load", action="store_true", dest="load", help="Omite carga del sistema (Load average)")
    parser.add_argument("-d", "-disk", action="store_true", dest="disk", help="Omite uso y temperatura del disco")
    parser.add_argument("-a", "-lan", action="store_true", dest="lan",  help="Omite red cableada (LAN)")
    parser.add_argument("-w", "-wifi", action="store_true", dest="wifi", help="Omite red inalambrica y temperatura (WiFi)")
    parser.add_argument("-t", "-bat", action="store_true", dest="bat",  help="Omite batería")
    parser.add_argument("-b", "-bar", action="store_true", dest="bar",  help="Omite todas las barras de progreso")
    parser.add_argument("-bc", "-barc", action="store_true", dest="barc", help="Omite la barra de uso de CPU")
    parser.add_argument("-bf", "-barf", action="store_true", dest="barf", help="Omite la barra de frecuencia del CPU")
    parser.add_argument("-br", "-barr", action="store_true", dest="barr", help="Omite la barra de uso de RAM")
    parser.add_argument("-bd", "-bard", action="store_true", dest="bard", help="Omite la barra de uso de Disco")
    parser.add_argument("-bw", "-barw", action="store_true", dest="barw", help="Omite la barra de señal WiFi")
    parser.add_argument("-bt", "-bart", action="store_true", dest="bart", help="Omite la barra de Batería")
    parser.add_argument("-i", "-icon", action="store_true", dest="icon", help="Oculta los íconos decorativos")
    parser.add_argument("-e", "-beep", action="store_true", dest="beep", help="Omite la alerta sonora (beep) ante nuevos valores en rojo")
    parser.add_argument("-g", "-gui", action="store_true", dest="gui", help="Arranca en modo interfaz gráfica (GUI) (no disponible aún)")

    return parser.parse_args()

def parse_args():
    config = SysStatConfig()
    args = sys.argv[1:]
    
    # Conjunto de flags admitidos oficialmente por tu formateador
    valid_flags = {
        "-s", "-sys", "-o", "-host", "-u", "-up", "-c", "-cpu", "-cn", "-cpun", "-r", "-ram",
        "-p", "-proc", "-l", "-load", "-d", "-disk", "-a", "-lan", "-w", "-wifi",
        "-t", "-bat", "-b", "-bar", "-bc", "-barc", "-bf", "-barf", "-br", "-barr",
        "-bd", "-bard", "-bw", "-barw", "-bt", "-bart", "-i", "-icon", "-e", "-beep", "-g", "-gui",
        "-h", "-help", "--help"
    }
    
    for arg in args:
        if arg in ["-h", "-help", "--help"]:
            parse_arguments()
            sys.exit(0)
            
        # 1. Procesamiento de flags conocidos
        elif arg in valid_flags:
            if arg in ["-s", "-sys"]:   config.sys  = False
            elif arg in ["-o", "-host"]: config.host = False
            elif arg in ["-u", "-up"]:   config.up   = False
            elif arg in ["-c", "-cpu"]:   config.cpu  = False
            elif arg in ["-cn", "-cpun"]: config.cpun = False
            elif arg in ["-r", "-ram"]:   config.ram  = False
            elif arg in ["-p", "-proc"]: config.proc = False
            elif arg in ["-l", "-load"]: config.load = False
            elif arg in ["-d", "-disk"]: config.disk = False
            elif arg in ["-a", "-lan"]:  config.lan  = False
            elif arg in ["-w", "-wifi"]: config.wifi = False
            elif arg in ["-t", "-bat"]:  config.bat  = False
            elif arg in ["-b", "-bar"]:  config.bar  = False
            elif arg in ["-bc", "-barc"]: config.barc = False
            elif arg in ["-bf", "-barf"]: config.barf = False
            elif arg in ["-br", "-barr"]: config.barr = False
            elif arg in ["-bd", "-bard"]: config.bard = False
            elif arg in ["-bw", "-barw"]: config.barw = False
            elif arg in ["-bt", "-bart"]: config.bart = False
            elif arg in ["-i", "-icon"]:  config.icon = False
            elif arg in ["-e", "-beep"]:  config.beep = False

            elif arg in ["-g", "-gui"]: config.cli = False
            
        # 2. Captura de número de bucles (Ej: -10)
        elif arg.startswith("-") and arg[1:].isdigit():
            config.cycles = int(arg[1:])
            
        # 3. Captura de segundos entre bucles (Ej: 5)
        elif arg.isdigit():
            config.interval = int(arg)
            
        # 4. Detener la ejecución ante cualquier argumento desconocido
        else:
            #print(f"{BOLD}{RED}Error:{RESET} El argumento '{arg}' no es válido.", file=sys.stderr)
            #print(f"Use {BOLD}-h{RESET}, {BOLD}-help{RESET} o {BOLD}--help{RESET} para ver la ayuda.\n", file=sys.stderr)
            print(f"{BOLD}ystat:{RESET} {RED}error:{RESET} el argumento '{arg}' no es válido.", file=sys.stderr)
            print(f"Use {BOLD}'-h'{RESET}, {BOLD}'-help'{RESET} o {BOLD}'--help'{RESET} para ver la ayuda.\n", file=sys.stderr)
            sys.exit(1)

    # REGLA DE ORO: Si definió ciclos pero no intervalo, por defecto 10 segundos
    if config.cycles is not None and config.interval is None:
        config.interval = 10

    # Si es GUI y no se especificó intervalo, por defecto son 10 segundos
    if not config.cli and config.interval is None:
        config.interval = 10
        
    return config

def main():
    config = parse_args()
    
    if config.cli:
        import sysstat_cli
        sysstat_cli.start_cli(config)
    else:
        import sysstat_gui
        sysstat_gui.start_gui(config)
        
    if config.interval is not None or config.cycles is not None:
        if config.cli:
            import sysstat_cli_info
            sysstat_cli_info.show_report(config)
        else:
            import sysstat_gui_info
            sysstat_gui_info.show_report()

if __name__ == "__main__":
    main()
