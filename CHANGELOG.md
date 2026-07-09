# Changelog

Todas las versiones notables de SysStat se documentan en este archivo.

## [5.46.0.20260708e] "Starship" — 2026-07-08

### Añadido
- **LAN**: monitoreo de red cableada completo (IP, velocidad, dúplex, throughput de bajada/subida), con detección en caliente cada ciclo — igual que WiFi, soporta adaptadores USB.
- **Batería**: implementación completa en core, CLI e informe final (porcentaje, tiempo restante, estado de carga/descarga).

### Cambiado
- Ícono de frecuencia de CPU: ⚡ → 🚀 (guiño a Starship de SpaceX).
- Auditoría de íconos: `hostname_icon` 🏠→💻, `user_icon` 👤→🧑, `cpu_usage_icon` 🔲→🔳, `wifi_signal_icon` 📶→🛜.
- Auditoría de nombres: todas las variables y funciones renombradas a inglés descriptivo (sufijo `_icon` para íconos, prefijos semánticos para variables de datos).
- Reordenamiento de funciones en `sysstat_cli.py`: helpers → chequeo de Unicode → `draw_statusbar_and_wait` → `start_cli`.
- README actualizado: instrucciones de exportación PDF, enlaces a informes de ejemplo, capturas movidas a `images/`, estados de hilos de procesos (T/R/D/S), temperatura de disco cubre NVMe+SSD, batería marcada como implementada.

### Corregido
- Parpadeo de pantalla eliminado: salida por buffer único (`sys.stdout.write`) + `\033[H` en vez de `\033[2J`.
- `sys.dont_write_bytecode = True` en `sysstat.py` para no generar `__pycache__`.

### Técnico
- Exportación a PDF vía `fpdf2`, con parseo de ANSI, limpieza de emojis por rango Unicode y ajuste de alineación.
- Cero imports sin usar confirmado en los cuatro archivos principales.

---

## Versiones anteriores

Historial previo a este changelog disponible en los commits del repositorio.
