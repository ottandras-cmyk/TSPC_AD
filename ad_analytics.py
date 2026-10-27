import os
import re
import json
import urllib.request
from datetime import datetime, timezone, timedelta
from sqlalchemy import desc, text
import models
from config_manager import get_setting

KNOWN_STATUS_WORDS = {
    "alapadat", "aktív normál user", "aktiv normal user",
    "hosszútávúszabadság", "hosszutavuszabadsag",
    "külsös", "kulsos", "távozottak", "tavozottak",
    "engedélyezve", "letiltva", "enabled", "disabled"
}

def is_valid_group_name(grp: str) -> bool:
    if not grp: return False
    # Kiszűrjük a dátumokat, időbélyegeket, amik tévesen csoportnévnek látszódtak
    if re.search(r"^\d{2,4}[-/\.]\d{2}[-/\.]\d{2,4}", grp):
        return False
    if re.search(r"\d{1,2}:\d{2}:\d{2}", grp):
        return False
    if grp.lower() in KNOWN_STATUS_WORDS:
        return False
    return True

def extract_group_name(details: str) -> str:
    if not details: return ""
    m = re.search(r"['\"]([^'\"]+)['\"]", details)
    if m:
        grp = m.group(1).strip()
        if is_valid_group_name(grp):
            return grp
    return ""

def get_clean_ad_changes(db, start_time=None, limit=10000):
    query = db.query(models.ADAuditLog).filter(models.ADAuditLog.change_type != 'BASELINE_ESTABLISHED')
    if start_time:
        query = query.filter(models.ADAuditLog.timestamp >= start_time)
    logs = query.order_by(desc(models.ADAuditLog.timestamp)).limit(limit).all()

    clean_list = []
    seen_dedup = set()

    for l in logs:
        grp = extract_group_name(l.details or "")
        if "GROUP" in l.change_type and ("ADDED" in l.change_type or "REMOVED" in l.change_type):
            if not grp:
                continue

        ts_minute = l.timestamp.strftime("%Y-%m-%d %H:%M") if l.timestamp else ""
        dedup_key = (ts_minute, l.entity_name.lower(), l.change_type, grp.lower() if grp else "")
        if dedup_key in seen_dedup:
            continue
        seen_dedup.add(dedup_key)

        clean_list.append({
            "id": l.id,
            "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "-",
            "date_str": l.timestamp.strftime("%Y-%m-%d") if l.timestamp else "-",
            "entity_name": l.entity_name,
            "entity_type": l.entity_type,
            "change_type": l.change_type,
            "group_name": grp,
            "details": l.details or "",
            "source_type": getattr(l, "source_type", "AD_SYNC") or "AD_SYNC",
            "source_ref": getattr(l, "source_ref", "LIVE_AD") or "LIVE_AD"
        })
    return clean_list

def get_ad_analytics_summary(db):
    now_utc = datetime.now(timezone.utc)
    t_24h = now_utc - timedelta(hours=24)
    t_72h = now_utc - timedelta(hours=72)
    t_168h = now_utc - timedelta(hours=168)
    t_30d = now_utc - timedelta(days=30)

    all_changes = get_clean_ad_changes(db, start_time=now_utc - timedelta(days=180), limit=10000)

    w_24h = []
    w_72h = []
    w_168h = []
    w_30d = []

    daily_map = {}

    for c in all_changes:
        dt = datetime.strptime(c["timestamp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) if c["timestamp"] != "-" else now_utc
        if dt >= t_24h: w_24h.append(c)
        if dt >= t_72h: w_72h.append(c)
        if dt >= t_168h: w_168h.append(c)
        if dt >= t_30d: w_30d.append(c)

        d_str = c["date_str"]
        if d_str not in daily_map:
            daily_map[d_str] = {
                "date": d_str,
                "total": 0,
                "added_to_group": 0,
                "removed_from_group": 0,
                "user_lifecycle": 0,
                "affected_users": set(),
                "affected_groups": set()
            }
        d = daily_map[d_str]
        d["total"] += 1
        if c["change_type"] == "ADDED_TO_GROUP":
            d["added_to_group"] += 1
        elif c["change_type"] == "REMOVED_FROM_GROUP":
            d["removed_from_group"] += 1
        else:
            d["user_lifecycle"] += 1

        if c["entity_name"]:
            d["affected_users"].add(c["entity_name"])
        if c["group_name"]:
            d["affected_groups"].add(c["group_name"])

    sorted_dates = sorted(daily_map.keys())
    chart_labels = []
    chart_total = []
    chart_added = []
    chart_removed = []
    chart_lifecycle = []

    daily_table = []
    for d_str in sorted_dates:
        item = daily_map[d_str]
        chart_labels.append(d_str)
        chart_total.append(item["total"])
        chart_added.append(item["added_to_group"])
        chart_removed.append(item["removed_from_group"])
        chart_lifecycle.append(item["user_lifecycle"])

        daily_table.append({
            "date": d_str,
            "total": item["total"],
            "added_to_group": item["added_to_group"],
            "removed_from_group": item["removed_from_group"],
            "user_lifecycle": item["user_lifecycle"],
            "affected_users": sorted(list(item["affected_users"])),
            "affected_groups": sorted(list(item["affected_groups"])),
            "affected_users_count": len(item["affected_users"]),
            "affected_groups_count": len(item["affected_groups"])
        })

    daily_table.reverse()

    return {
        "summary_counts": {
            "c_24h": len(w_24h),
            "c_72h": len(w_72h),
            "c_168h": len(w_168h),
            "c_30d": len(w_30d)
        },
        "windows": {
            "w_24h": w_24h[:100],
            "w_72h": w_72h[:150],
            "w_168h": w_168h[:250],
            "w_30d": w_30d[:400]
        },
        "chart_data": {
            "labels": chart_labels,
            "total": chart_total,
            "added": chart_added,
            "removed": chart_removed,
            "lifecycle": chart_lifecycle
        },
        "daily_breakdown": daily_table
    }

def get_day_detailed_events(db, date_str: str, event_type: str = "ALL"):
    all_events = get_clean_ad_changes(db, limit=10000)
    day_filtered = [e for e in all_events if e["date_str"] == date_str]

    if event_type == "ADDED":
        day_filtered = [e for e in day_filtered if e["change_type"] == "ADDED_TO_GROUP"]
    elif event_type == "REMOVED":
        day_filtered = [e for e in day_filtered if e["change_type"] == "REMOVED_FROM_GROUP"]
    elif event_type == "LIFECYCLE":
        day_filtered = [e for e in day_filtered if e["change_type"] not in ["ADDED_TO_GROUP", "REMOVED_FROM_GROUP"]]

    return {
        "date": date_str,
        "type": event_type,
        "total_count": len(day_filtered),
        "events": day_filtered
    }

def ask_ad_changes_ai(db, model: str, prompt: str) -> dict:
    url = get_setting(db, "OLLAMA_URL", "http://ollama:11434")
    summary = get_ad_analytics_summary(db)

    context_lines = [
        "=== AD JOGOSULTSÁG ÉS VÁLTOZÁSI ELEMZŐ JELENTÉS ===",
        "Időablak statisztikák:",
        f"- Elmúlt 24 óra változásai: {summary['summary_counts']['c_24h']} db",
        f"- Elmúlt 72 óra változásai: {summary['summary_counts']['c_72h']} db",
        f"- Elmúlt 168 óra (7 nap) változásai: {summary['summary_counts']['c_168h']} db",
        f"- Elmúlt 30 nap változásai: {summary['summary_counts']['c_30d']} db",
        "",
        "Napi változások és érintett felhasználók/csoportok (legfrissebb napok):"
    ]

    for d in summary["daily_breakdown"][:14]:
        u_sample = ", ".join(d["affected_users"][:5]) + (f" (+{len(d['affected_users'])-5} fő)" if len(d['affected_users']) > 5 else "")
        g_sample = ", ".join(d["affected_groups"][:5]) + (f" (+{len(d['affected_groups'])-5} csoport)" if len(d['affected_groups']) > 5 else "")
        context_lines.append(
            f"* {d['date']}: Összesen {d['total']} változás (Hozzáadás: {d['added_to_group']}, Elvétel: {d['removed_from_group']}, Státusz/Fiók: {d['user_lifecycle']}) | Érintett userek: {u_sample or 'Nincs'} | Érintett csoportok: {g_sample or 'Nincs'}"
        )

    context_lines.append("\nLegutóbbi konkrét jogosultság- és csoportváltozások (minta):")
    for event in summary["windows"]["w_72h"][:25]:
        grp_str = f" [Csoport: {event['group_name']}]" if event['group_name'] else ""
        context_lines.append(f"- {event['timestamp']}: {event['entity_name']} -> {event['change_type']}{grp_str} ({event['details']}) [Forrás: {event['source_ref']}]")

    full_context = "\n".join(context_lines)

    system_instruction = f"""Te vagy az Active Directory változáskövető és jogosultsági biztonsági szakértője.
Rendelkezésedre áll a letisztázott AD változástörténet (a CSV import és élő AD lekérdezések anomáliáitól megtisztítva).
Ismered a napi lebontásokat, a hozzáadások és elvételek számait, az érintett felhasználókat és csoportokat, valamint a 24h, 72h, 168h és 30 napos ablakokat.

[AD VÁLTOZÁSI DOSSZIÉ]:
{full_context}

[KÉRDÉS]:
{prompt}

Válaszolj tényszerűen, strukturáltan, kiemelve a biztonsági kockázatokat vagy mintázatokat magyar nyelven!"""

    payload = json.dumps({
        "model": model,
        "prompt": system_instruction,
        "stream": False,
        "options": {"temperature": 0.2}
    }).encode("utf-8")

    req = urllib.request.Request(f"{url}/api/generate", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"status": "SUCCESS", "response": data.get("response", "")}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}
