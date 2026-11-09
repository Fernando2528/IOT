"""
util.py
=======
Utilidades de marca de tiempo de alta precisión y conversión de fechas ISO-8601
a época Unix para sincronización de coreografías en MicroPython.
"""

import time


def time_float() -> float:
    """Retorna marca de tiempo en segundos con resolución de microsegundos."""
    if hasattr(time, "time_ns"):
        t_ns_str = str(time.time_ns())
        if len(t_ns_str) > 9:
            return float(t_ns_str[:-9] + "." + t_ns_str[-9:-3])
    if hasattr(time, "ticks_us"):
        return time.ticks_us() / 1_000_000.0
    return float(time.time())


def parse_iso8601_to_epoch(iso_str: str):
    """
    Convierte una cadena ISO-8601 (ej. '2025-09-25T20:00:00Z' o '2026-11-03T15:30:00-05:00')
    a segundos Unix epoch (UTC). Retorna None si es 'now' o inválida.
    """
    if not iso_str or not isinstance(iso_str, str):
        return None
    s = iso_str.strip()
    if s.lower() in ("now", "immediately"):
        return None

    try:
        tz_offset_s = 0
        if s.endswith("Z") or s.endswith("z"):
            s = s[:-1]
        elif "T" in s:
            t_pos = s.find("T")
            plus_pos = s.rfind("+")
            minus_pos = s.rfind("-")
            tz_pos = max(plus_pos, minus_pos)
            if tz_pos > t_pos:
                sign = 1 if s[tz_pos] == "+" else -1
                tz_part = s[tz_pos + 1 :]
                s = s[:tz_pos]
                if ":" in tz_part:
                    tz_h, tz_m = tz_part.split(":", 1)
                else:
                    tz_h, tz_m = tz_part[:2], tz_part[2:] or "0"
                tz_offset_s = sign * (int(tz_h) * 3600 + int(tz_m) * 60)

        date_part, time_part = s.split("T", 1)
        year, month, day = [int(x) for x in date_part.split("-")]
        time_fields = time_part.split(":")
        hour = int(time_fields[0])
        minute = int(time_fields[1]) if len(time_fields) > 1 else 0
        sec_float = float(time_fields[2]) if len(time_fields) > 2 else 0.0
        sec_int = int(sec_float)
        frac = sec_float - sec_int

        y = year - (1 if month <= 2 else 0)
        era = (y if y >= 0 else y - 399) // 400
        yoe = y - era * 400
        m_adj = month - 3 if month > 2 else month + 9
        doy = (153 * m_adj + 2) // 5 + day - 1
        doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
        days = era * 146097 + doe - 719468

        return float(days * 86400 + hour * 3600 + minute * 60 + sec_int + frac - tz_offset_s)
    except Exception:
        return None
