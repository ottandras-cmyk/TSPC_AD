import os
import re
import socket
import ipaddress
import subprocess
import shutil
from datetime import datetime, timezone, timedelta
from sqlalchemy import text, desc, func
import models
from config_manager import get_setting

def parse_user_agent(ua_str: str):
    if not ua_str:
        return "Ismeretlen", "Ismeretlen", "Asztali gép"

    device = "Asztali gép"
    if re.search(r"Mobile|Android.*Mobile|iPhone|iPod", ua_str, re.IGNORECASE):
        device = "Mobiltelefon"
    elif re.search(r"iPad|Tablet|Android(?!.*Mobile)", ua_str, re.IGNORECASE):
        device = "Táblagép (Tablet)"

    os_name = "Ismeretlen OS"
    if "Windows NT 10.0" in ua_str: os_name = "Windows 10/11"
    elif "Windows NT 6.3" in ua_str: os_name = "Windows 8.1"
    elif "Windows NT 6.1" in ua_str: os_name = "Windows 7"
    elif "Windows" in ua_str: os_name = "Windows"
    elif "Macintosh" in ua_str or "Mac OS X" in ua_str: os_name = "macOS"
    elif "Android" in ua_str: os_name = "Android"
    elif "iPhone" in ua_str or "iPad" in ua_str: os_name = "iOS"
    elif "Linux" in ua_str: os_name = "Linux"

    browser = "Ismeretlen Böngésző"
    if "Edg/" in ua_str: browser = "Microsoft Edge"
    elif "Chrome/" in ua_str and "Chromium/" not in ua_str: browser = "Google Chrome"
    elif "Firefox/" in ua_str: browser = "Mozilla Firefox"
    elif "Safari/" in ua_str and "Chrome/" not in ua_str: browser = "Apple Safari"
    elif "OPR/" in ua_str or "Opera/" in ua_str: browser = "Opera"
    elif "Postman" in ua_str: browser = "Postman API"
    elif "curl/" in ua_str: browser = "curl parancssor"
    elif "python" in ua_str.lower(): browser = "Python Script"

    return browser, os_name, device

def resolve_ip_network(ip: str):
    if not ip or ip in ["127.0.0.1", "::1", "localhost"]:
        return "Helyi gép (Localhost)"
    try:
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.is_private:
            if ip.startswith("10.1."):
                return "TSPC Belső Hálózat (LAN 10.1.x)"
            elif ip.startswith("10."):
                return "Belső Hálózat / VPN (10.x)"
            elif ip.startswith("192.168."):
                return "Helyi Alhálózat (LAN 192.168.x)"
            elif ip.startswith("172."):
                return "Docker Belső Hálózat"
            return "Belső Hálózat"
        else:
            try:
                hostname, _, _ = socket.gethostbyaddr(ip)
                return f"Publikus ({hostname})"
            except Exception:
                return "Publikus Internet"
    except Exception:
        return "Hálózat"

def get_client_ip(request):
    if not request:
        return "127.0.0.1"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

# --- AKTÍV MUNKAMENET KEZELŐ ---
def register_active_session(db, request, session_id: str, username: str):
    try:
        ip = get_client_ip(request)
        ua_str = request.headers.get("user-agent", "") if request else ""
        browser, os_name, device = parse_user_agent(ua_str)
        loc = resolve_ip_network(ip)
        now = datetime.now(timezone.utc)

        existing = db.query(models.ActiveSession).filter_by(session_id=session_id).first()
        if existing:
            existing.last_activity = now
            existing.client_ip = ip
            existing.browser = browser
            existing.os_name = os_name
            existing.device_type = device
            existing.location = loc
        else:
            new_s = models.ActiveSession(
                session_id=session_id,
                username=username,
                login_time=now,
                last_activity=now,
                client_ip=ip,
                browser=browser,
                os_name=os_name,
                device_type=device,
                location=loc,
                user_agent=ua_str[:500] if ua_str else ""
            )
            db.add(new_s)
        db.commit()
    except Exception:
        db.rollback()

def update_active_session(db, session_id: str):
    if not session_id: return
    try:
        s = db.query(models.ActiveSession).filter_by(session_id=session_id).first()
        if s:
            s.last_activity = datetime.now(timezone.utc)
            db.commit()
    except Exception:
        db.rollback()

def close_active_session(db, session_id: str):
    if not session_id: return
    try:
        db.query(models.ActiveSession).filter_by(session_id=session_id).delete()
        db.commit()
    except Exception:
        db.rollback()

def get_active_sessions_info(db, current_session_id: str):
    now_utc = datetime.now(timezone.utc)
    # 2 óránál régebbi inaktív session-ök takarítása
    try:
        db.query(models.ActiveSession).filter(models.ActiveSession.last_activity < now_utc - timedelta(hours=2)).delete()
        db.commit()
    except Exception:
        db.rollback()

    curr = db.query(models.ActiveSession).filter_by(session_id=current_session_id).first()
    curr_data = None
    if curr:
        active_mins = int((now_utc - curr.login_time).total_seconds() / 60)
        curr_data = {
            "username": curr.username,
            "client_ip": curr.client_ip,
            "browser": curr.browser,
            "os_name": curr.os_name,
            "device_type": curr.device_type,
            "location": curr.location,
            "login_time": curr.login_time.strftime("%Y-%m-%d %H:%M:%S") if curr.login_time else "-",
            "active_duration": f"{active_mins // 60} óra, {active_mins % 60} perc" if active_mins >= 60 else f"{active_mins} perce"
        }

    others = db.query(models.ActiveSession)\
        .filter(models.ActiveSession.session_id != current_session_id, models.ActiveSession.last_activity >= now_utc - timedelta(minutes=25))\
        .order_by(desc(models.ActiveSession.last_activity)).all()

    other_list = []
    for o in others:
        o_active_mins = int((now_utc - o.login_time).total_seconds() / 60)
        last_seen_mins = int((now_utc - o.last_activity).total_seconds() / 60)
        other_list.append({
            "username": o.username,
            "client_ip": o.client_ip,
            "browser": o.browser,
            "os_name": o.os_name,
            "device_type": o.device_type,
            "location": o.location,
            "login_time": o.login_time.strftime("%Y-%m-%d %H:%M:%S") if o.login_time else "-",
            "active_duration": f"{o_active_mins} perce",
            "last_activity": f"{last_seen_mins} perce" if last_seen_mins > 0 else "Épp most"
        })

    return {
        "current_session": curr_data,
        "other_sessions": other_list
    }

def log_web_activity(db, request, username: str, action: str, details: str = "", status: str = "SIKERES"):
    try:
        ip = get_client_ip(request)
        ua_str = request.headers.get("user-agent", "") if request else ""
        browser, os_name, device = parse_user_agent(ua_str)
        loc = resolve_ip_network(ip)

        entry = models.WebAccessLog(
            username=username or "Ismeretlen",
            client_ip=ip,
            browser=browser,
            os_name=os_name,
            device_type=device,
            location=loc,
            user_agent=ua_str[:500] if ua_str else "",
            action=action,
            details=details,
            status=status
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()

def detect_host_machine_info(db):
    hostname = socket.gethostname()
    current_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        current_ip = s.getsockname()[0]
        s.close()
    except Exception:
        try: current_ip = socket.gethostbyname(hostname)
        except Exception: pass

    uptime_str = "-"
    if os.path.exists("/proc/uptime"):
        try:
            with open("/proc/uptime", "r") as f:
                uptime_sec = float(f.read().split()[0])
                days = int(uptime_sec // 86400)
                hours = int((uptime_sec % 86400) // 3600)
                mins = int((uptime_sec % 3600) // 60)
                uptime_str = f"{days} nap, {hours} óra, {mins} perc"
        except Exception: pass

    try:
        last_log = db.query(models.HostIPLog).order_by(desc(models.HostIPLog.timestamp)).first()
        if not last_log or last_log.ip_address != current_ip:
            new_log = models.HostIPLog(
                ip_address=current_ip, hostname=hostname,
                details=f"Aktuális IP rögzítve. Futási idő: {uptime_str}"
            )
            db.add(new_log)
            db.commit()
    except Exception:
        db.rollback()

    return {"current_ip": current_ip, "hostname": hostname, "uptime": uptime_str}

def parse_cpu_metrics():
    try: load1, _, _ = os.getloadavg()
    except Exception: load1 = 0.0
    cpu_count = os.cpu_count() or 1
    cpu_pct = round(min(100.0, (load1 / cpu_count) * 100), 1)

    cpu_temp = None
    for p in ["/sys/class/thermal/thermal_zone0/temp", "/sys/class/hwmon/hwmon0/temp1_input"]:
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    val = float(f.read().strip())
                    cpu_temp = round(val / 1000.0, 1) if val > 1000 else round(val, 1)
                    break
            except Exception: pass
    return cpu_pct, cpu_temp, cpu_count

def parse_ram_metrics():
    total_mb, avail_mb, free_mb = 0.0, 0.0, 0.0
    if os.path.exists("/proc/meminfo"):
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    p = line.split()
                    if len(p) >= 2:
                        if p[0] == "MemTotal:": total_mb = round(int(p[1]) / 1024, 1)
                        elif p[0] == "MemAvailable:": avail_mb = round(int(p[1]) / 1024, 1)
                        elif p[0] == "MemFree:": free_mb = round(int(p[1]) / 1024, 1)
        except Exception: pass
    used_mb = round(total_mb - (avail_mb or free_mb), 1) if total_mb else 0.0
    pct = round((used_mb / total_mb) * 100, 1) if total_mb else 0.0
    return total_mb, used_mb, pct

def parse_disk_metrics():
    try:
        total, used, free = shutil.disk_usage("/")
        return round(total / (1024**3), 2), round(used / (1024**3), 2), round(free / (1024**3), 2)
    except Exception:
        return 0.0, 0.0, 0.0

def parse_gpu_metrics():
    data = {"detected": False, "name": None, "util_pct": 0.0, "mem_used_mb": 0.0, "mem_total_mb": 0.0, "temp_c": None, "power_w": None}
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw", "--format=csv,noheader,nounits"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3
        )
        if res.returncode == 0 and res.stdout.strip():
            first_line = res.stdout.strip().split("\n")[0]
            parts = [p.strip() for p in first_line.split(",")]
            if len(parts) >= 6:
                data["detected"] = True
                data["name"] = parts[0]
                data["util_pct"] = float(parts[1]) if parts[1] != '[N/A]' else 0.0
                data["mem_used_mb"] = float(parts[2]) if parts[2] != '[N/A]' else 0.0
                data["mem_total_mb"] = float(parts[3]) if parts[3] != '[N/A]' else 0.0
                data["temp_c"] = float(parts[4]) if parts[4] != '[N/A]' else None
                data["power_w"] = float(parts[5]) if parts[5] != '[N/A]' else None
    except Exception: pass
    return data

def get_db_size_mb(db):
    try:
        val = db.execute(text("SELECT pg_database_size(current_database()) / (1024.0 * 1024.0);")).scalar()
        return round(float(val), 2) if val is not None else 0.0
    except Exception: return 0.0

def get_llm_token_counts(db):
    try:
        p = int(get_setting(db, "LLM_TOKENS_PROMPT", "0"))
        e = int(get_setting(db, "LLM_TOKENS_EVAL", "0"))
        t = int(get_setting(db, "LLM_TOKENS_TOTAL", "0"))
        return p, e, t
    except Exception: return 0, 0, 0

def collect_and_save_telemetry(db):
    cpu_pct, cpu_temp, cpu_count = parse_cpu_metrics()
    ram_total, ram_used, ram_pct = parse_ram_metrics()
    disk_total, disk_used, disk_free = parse_disk_metrics()
    gpu = parse_gpu_metrics()
    db_size = get_db_size_mb(db)
    tok_p, tok_e, tok_t = get_llm_token_counts(db)
    detect_host_machine_info(db)

    record = models.SystemTelemetry(
        cpu_percent=cpu_pct,
        cpu_temp_c=cpu_temp,
        ram_total_mb=ram_total,
        ram_used_mb=ram_used,
        ram_percent=ram_pct,
        disk_total_gb=disk_total,
        disk_used_gb=disk_used,
        disk_free_gb=disk_free,
        db_size_mb=db_size,
        gpu_name=gpu["name"],
        gpu_util_percent=gpu["util_pct"] if gpu["detected"] else None,
        gpu_mem_used_mb=gpu["mem_used_mb"] if gpu["detected"] else None,
        gpu_mem_total_mb=gpu["mem_total_mb"] if gpu["detected"] else None,
        gpu_temp_c=gpu["temp_c"] if gpu["detected"] else None,
        gpu_power_w=gpu["power_w"] if gpu["detected"] else None,
        llm_tokens_prompt=tok_p,
        llm_tokens_eval=tok_e,
        llm_tokens_total=tok_t
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

def get_live_telemetry(db):
    cpu_pct, cpu_temp, cpu_count = parse_cpu_metrics()
    ram_total, ram_used, ram_pct = parse_ram_metrics()
    disk_total, disk_used, disk_free = parse_disk_metrics()
    gpu = parse_gpu_metrics()
    db_size = get_db_size_mb(db)
    tok_p, tok_e, tok_t = get_llm_token_counts(db)
    host_info = detect_host_machine_info(db)

    return {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "host": host_info,
        "cpu": {"percent": cpu_pct, "temp_c": cpu_temp, "cores": cpu_count},
        "ram": {"total_mb": ram_total, "used_mb": ram_used, "percent": ram_pct},
        "disk": {"total_gb": disk_total, "used_gb": disk_used, "free_gb": disk_free, "percent": round((disk_used / disk_total * 100), 1) if disk_total else 0.0},
        "db": {"size_mb": db_size},
        "gpu": gpu,
        "llm": {"prompt_tokens": tok_p, "eval_tokens": tok_e, "total_tokens": tok_t}
    }

def get_telemetry_history(db, limit=96):
    records = db.query(models.SystemTelemetry).order_by(desc(models.SystemTelemetry.timestamp)).limit(limit).all()
    records.reverse()
    result = []
    for r in records:
        result.append({
            "timestamp": r.timestamp.strftime("%m-%d %H:%M") if r.timestamp else "-",
            "cpu_percent": r.cpu_percent or 0.0,
            "cpu_temp_c": r.cpu_temp_c,
            "ram_used_mb": r.ram_used_mb or 0.0,
            "ram_percent": r.ram_percent or 0.0,
            "disk_used_gb": r.disk_used_gb or 0.0,
            "disk_free_gb": r.disk_free_gb or 0.0,
            "db_size_mb": r.db_size_mb or 0.0,
            "gpu_name": r.gpu_name or "N/A",
            "gpu_util_percent": r.gpu_util_percent or 0.0,
            "gpu_mem_used_mb": r.gpu_mem_used_mb or 0.0,
            "gpu_temp_c": r.gpu_temp_c,
            "gpu_power_w": r.gpu_power_w,
            "llm_tokens_total": r.llm_tokens_total or 0
        })
    return result

def get_web_access_logs(db, limit=100):
    logs = db.query(models.WebAccessLog).order_by(desc(models.WebAccessLog.timestamp)).limit(limit).all()
    return [{
        "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "-",
        "username": l.username,
        "client_ip": l.client_ip,
        "browser": getattr(l, "browser", "-") or "-",
        "os_name": getattr(l, "os_name", "-") or "-",
        "device_type": getattr(l, "device_type", "-") or "-",
        "location": getattr(l, "location", "-") or "-",
        "action": l.action,
        "details": l.details or "",
        "status": l.status
    } for l in logs]

def get_host_ip_history(db, limit=50):
    logs = db.query(models.HostIPLog).order_by(desc(models.HostIPLog.timestamp)).limit(limit).all()
    return [{
        "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "-",
        "ip_address": l.ip_address,
        "hostname": l.hostname,
        "details": l.details or ""
    } for l in logs]

# --- LLM MÉLYSÉGI ADATTÁR ÉS KORRELÁCIÓS DOSSZIÉ ---
def get_system_deep_dossier(db):
    sections = []
    now_utc = datetime.now(timezone.utc)

    # 1. Dokumentáció és kódstruktúra
    app_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.abspath(os.path.join(app_dir, ".."))
    rebuild_path = os.path.join(project_dir, "docs", "SYSTEM_REBUILD_PROMPT.md")
    blueprint_excerpt = ""
    if os.path.isfile(rebuild_path):
        try:
            with open(rebuild_path, "r", encoding="utf-8") as f:
                blueprint_excerpt = f.read()[:2500]
        except Exception: pass
    sections.append("### 1. RENDSZERARCHITEKTÚRA ÉS SÉMALEÍRÁS\n" + (blueprint_excerpt or "Docs generálás a háttérben."))

    # 2. Hardver és Telemetria Szélsőértékek (Min/Max és Korreláció)
    t_records = db.query(models.SystemTelemetry).order_by(desc(models.SystemTelemetry.timestamp)).limit(200).all()
    if t_records:
        max_cpu_rec = max(t_records, key=lambda x: x.cpu_percent or 0.0)
        min_cpu_rec = min(t_records, key=lambda x: x.cpu_percent or 0.0)
        max_ram_rec = max(t_records, key=lambda x: x.ram_used_mb or 0.0)
        max_gpu_rec = max(t_records, key=lambda x: x.gpu_util_percent or 0.0) if any(x.gpu_util_percent for x in t_records) else None

        # Korreláció a csúcsidőpontban futó feladatokkal
        def find_tasks_around(dt):
            if not dt: return "Nincs rögzített feladat"
            start_window = dt - timedelta(minutes=20)
            end_window = dt + timedelta(minutes=20)
            syncs = db.query(models.SyncHistory).filter(models.SyncHistory.started_at >= start_window, models.SyncHistory.started_at <= end_window).all()
            if not syncs: return "Csak normál rendszerfolyamatok / alapjárat"
            return ", ".join([f"{s.trigger_type} ({s.status}, {s.changes_detected} változás, {s.duration_seconds} mp)" for s in syncs])

        # Korreláció a csúcsidőpontban aktív belépésekkel
        def find_logins_around(dt):
            if not dt: return "Nincs belépési esemény"
            start_window = dt - timedelta(minutes=20)
            end_window = dt + timedelta(minutes=20)
            logs = db.query(models.WebAccessLog).filter(models.WebAccessLog.timestamp >= start_window, models.WebAccessLog.timestamp <= end_window).all()
            if not logs: return "Nem történt webes bejelentkezés ebben az időablakban"
            return ", ".join([f"{l.username} ({l.client_ip}, {l.action})" for l in logs[:5]])

        tel_summary = [
            f"- MAXIMÁLIS CPU terhelés: {max_cpu_rec.cpu_percent}% (Időpont: {max_cpu_rec.timestamp.strftime('%Y-%m-%d %H:%M:%S')})",
            f"  * Ekkor futó feladatok: {find_tasks_around(max_cpu_rec.timestamp)}",
            f"  * Ekkor történt webes aktivitás: {find_logins_around(max_cpu_rec.timestamp)}",
            f"- MINIMÁLIS CPU terhelés: {min_cpu_rec.cpu_percent}% (Időpont: {min_cpu_rec.timestamp.strftime('%Y-%m-%d %H:%M:%S')})",
            f"- CSÚCS Memóriahasználat (RAM): {max_ram_rec.ram_used_mb} MB ({max_ram_rec.ram_percent}%) (Időpont: {max_ram_rec.timestamp.strftime('%Y-%m-%d %H:%M:%S')})",
            f"- GPU csúcsterhelés: {max_gpu_rec.gpu_util_percent if max_gpu_rec else 0}% ({max_gpu_rec.gpu_name if max_gpu_rec else 'Nem észlelt'})"
        ]
        sections.append("### 2. HARDVER TELEMETRIAI SZÉLSŐÉRTÉKEK ÉS FELADAT-KORRELÁCIÓK\n" + "\n".join(tel_summary))
    else:
        sections.append("### 2. HARDVER TELEMETRIA\nMég nincs elegendő idősoros telemetria rögzítve.")

    # 3. Webes Belépések és Kliensek Statisztikája
    login_stats = db.execute(text("""
        SELECT username, client_ip, browser, os_name, COUNT(*) as login_count, MAX(timestamp) as last_login
        FROM web_access_log
        WHERE action = 'BEJELENTKEZÉS' AND status = 'SIKERES'
        GROUP BY username, client_ip, browser, os_name
        ORDER BY login_count DESC LIMIT 15;
    """)).fetchall()

    failed_logins = db.execute(text("""
        SELECT username, client_ip, COUNT(*) as fail_count, MAX(timestamp) as last_attempt
        FROM web_access_log
        WHERE status = 'SIKERTELEN'
        GROUP BY username, client_ip
        ORDER BY fail_count DESC LIMIT 10;
    """)).fetchall()

    web_lines = ["- Sikeres belépések felhasználónként és gépenként:"]
    for row in login_stats:
        web_lines.append(f"  * {row[0]}: {row[4]} alkalommal lépett be (IP: {row[1]}, Böngésző: {row[2]}, OS: {row[3]}, Utoljára: {row[5]})")
    if not login_stats: web_lines.append("  * Nincs még rögzített sikeres belépés.")

    web_lines.append("- Sikertelen belépési kísérletek:")
    for f_row in failed_logins:
        web_lines.append(f"  * {f_row[0]} fiókkal {f_row[2]} sikertelen kísérlet (IP: {f_row[1]}, Utoljára: {f_row[3]})")
    if not failed_logins: web_lines.append("  * Nincs regisztrált sikertelen bejelentkezési kísérlet.")
    sections.append("### 3. WEBES BELÉPÉSI ÉS BIZTONSÁGI STATISZTIKÁK\n" + "\n".join(web_lines))

    # 4. Jelenleg aktív munkamenetek
    active_now = db.query(models.ActiveSession).filter(models.ActiveSession.last_activity >= now_utc - timedelta(minutes=30)).all()
    session_lines = [f"Aktív munkamenetek száma: {len(active_now)} fő"]
    for s in active_now:
        session_lines.append(f"- {s.username} (IP: {s.client_ip}, Gép: {s.browser} on {s.os_name}, Belépve: {s.login_time.strftime('%H:%M:%S')})")
    sections.append("### 4. JELENLEG AKTÍV FELHASZNÁLÓK A RENDSZERBEN\n" + "\n".join(session_lines))

    # 5. AD Fiókok és Audit napló összegzés
    u_cnt = db.query(models.ADUser).count()
    g_cnt = db.query(models.ADGroup).count()
    aud_cnt = db.query(models.ADAuditLog).count()
    recent_audits = db.query(models.ADAuditLog).order_by(desc(models.ADAuditLog.timestamp)).limit(8).all()
    aud_lines = [f"Összes fiók: {u_cnt} db | Csoportok: {g_cnt} db | Naplózott változások: {aud_cnt} db", "Legutóbbi jogosultság-változások:"]
    for a in recent_audits:
        aud_lines.append(f"- {a.timestamp.strftime('%Y-%m-%d %H:%M')}: [{a.change_type}] {a.entity_name} -> {a.details}")
    sections.append("### 5. ACTIVE DIRECTORY ADATOK ÉS LEGUTÓBBI VÁLTOZÁSOK\n" + "\n".join(aud_lines))

    return "\n\n".join(sections)
