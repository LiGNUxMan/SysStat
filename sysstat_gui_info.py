#!/usr/bin/env python3
# 
# SysStat (System Status) - GUI_Info
# 
# Autor: Axel O'BRIEN (LiGNUxMan) axelobrien@gmail.com
# 
# Colaboradores: ChatGPT (OpenAI) · Gemini/Antigravity (Google) · Claude (Anthropic)
#
# =======================================
# sysstat_cli:info.py - INFORME FINAL GUI
# =======================================
#
# Version: 00
#
# =============================================

from sysstat import __version__

# Códigos ANSI para formato de texto
RESET = "\033[0m"
BOLD = "\033[1m"

def show_report():
    # Línea principal con tu diseño exacto
    print(f"")
    print(f"{BOLD}SysStat GUI{RESET} v{__version__}")
    print(f"")
    
    # (Abajo de esto el Core irá inyectando los promedios calculados...)


