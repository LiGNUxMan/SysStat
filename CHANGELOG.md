# Changelog

Todas las versiones notables de SysStat se documentan en este archivo.

## [5.46.1.20260710f] "Beep" — 2026-07-10

### Añadido
- **Alerta sonora**: beep ante métricas que pasan a rojo. Edge-triggered — solo suena en la *transición* a rojo, no mientras se mantiene sostenido, para no saturar en bucles cortos (`sysstat.py 1`, por ejemplo).
- Un solo beep por ciclo, sin importar cuántas métricas entren en rojo juntas en el mismo ciclo.
- Fallback de tres niveles en `play_beep()`: `sox` (`play`) → `beep` → bell ASCII (`\a`) — cae al siguiente nivel solo si el comando no está instalado.
- Nueva flag `-e` / `-beep` para desactivar la alerta (sonido activo por defecto, como el resto de las flags de presentación).

### Técnico
- Set `prev_red_keys` en `sysstat_cli.py` para trackear qué métricas estaban en rojo en el ciclo anterior — comparación por diferencia de conjuntos (`current_red_keys - prev_red_keys`) para detectar solo entradas nuevas.
- Lógica de beep vive enteramente en `sysstat_cli.py` (capa de presentación) — `sysstat_core.py` no se modificó, solo expone los colores que ya calculaba.

---

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
