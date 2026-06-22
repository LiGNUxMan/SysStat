#!/usr/bin/env python3
# 
# SysStat (System Status) - GUI
# 
# Autor: Axel O'BRIEN (LiGNUxMan) axelobrien@gmail.com
# 
# Colaboradores: ChatGPT (OpenAI) · Gemini/Antigravity (Google) · Claude (Anthropic)
#
# =========================================
# sysstat_gui.py - INTERFAZ DEL USUARIO GUI
# =========================================
#
# Version: 003
#
# =============================================

import os
import sys

# Constantes exclusivas de la interfaz visual
ICON_PAPIRUS_NAME = "sysstat_icon_papirus.png"
ICON_STANDARD_NAME = "sysstat_icon.png"

def start_gui(config):
    """Inicializa la ventana gráfica y dibuja los paneles."""
    print("🚧 GUI en construcción... ¡Seguí participando! 🚧")
    print("-" * 38)
    print(f"Intervalo recibido: {config.interval}s")
    print("-" * 38)

