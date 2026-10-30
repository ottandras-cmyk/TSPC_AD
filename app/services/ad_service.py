import re
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
try:
    from repositories.audit_repository import AuditRepository
except ImportError:
    from app.repositories.audit_repository import AuditRepository

KNOWN_STATUS_WORDS = {
    "alapadat", "aktív normál user", "aktiv normal user",
    "hosszútávúszabadság", "hosszutavuszabadsag",
    "külsös", "kulsos", "távozottak", "tavozottak",
    "engedélyezve", "letiltva", "enabled", "disabled"
}

class AdService:
    def __init__(self, db: Session = None):
        self.db = db

    def _repo(self, db: Session = None):
        target = db or self.db
        if target:
            return AuditRepository(target)
        return None

    @staticmethod
    def is_valid_group_name(grp: str) -> bool:
        if not grp: return False
        if re.search(r"^\d{2,4}[-/\.]\d{2}[-/\.]\d{2,4}", grp): return False
        if re.search(r"\d{1,2}:\d{2}:\d{2}", grp): return False
        if grp.lower() in KNOWN_STATUS_WORDS: return False
        return True

    @staticmethod
    def extract_group_name(details: str) -> str:
        if not details: return ""
        m = re.search(r"['\"]([^'\"]+)['\"]", details)
        if m:
            grp = m.group(1).strip()
            if AdService.is_valid_group_name(grp):
                return grp
        return ""

    def get_clean_changes(self, start_time: datetime = None, limit: int = 10000, db: Session = None):
        r = self._repo(db)
        logs = r.get_clean_logs(start_time=start_time, limit=limit) if r else []
        clean_list = []
        seen = set()

        for l in logs:
            grp = self.extract_group_name(l.details or "")
            if "GROUP" in l.change_type and ("ADDED" in l.change_type or "REMOVED" in l.change_type):
                if not grp:
                    continue

            ts_minute = l.timestamp.strftime("%Y-%m-%d %H:%M") if l.timestamp else ""
            dedup_key = (ts_minute, l.entity_name.lower(), l.change_type, grp.lower() if grp else "")
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

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

    def get_analytics_summary(self, db: Session = None):
        now_utc = datetime.now(timezone.utc)
        all_changes = self.get_clean_changes(start_time=now_utc - timedelta(days=180), limit=10000, db=db)
        t_24h = now_utc - timedelta(hours=24)
        t_72h = now_utc - timedelta(hours=72)
        t_168h = now_utc - timedelta(hours=168)
        t_30d = now_utc - timedelta(days=30)

        w_24h, w_72h, w_168h, w_30d = [], [], [], []
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
                    "date": d_str, "total": 0, "added_to_group": 0, "removed_from_group": 0,
                    "user_lifecycle": 0, "affected_users": set(), "affected_groups": set()
                }
            d = daily_map[d_str]
            d["total"] += 1
            if c["change_type"] == "ADDED_TO_GROUP": d["added_to_group"] += 1
            elif c["change_type"] == "REMOVED_FROM_GROUP": d["removed_from_group"] += 1
            else: d["user_lifecycle"] += 1

            if c["entity_name"]: d["affected_users"].add(c["entity_name"])
            if c["group_name"]: d["affected_groups"].add(c["group_name"])

        sorted_dates = sorted(daily_map.keys())
        daily_table, chart_labels, chart_total, chart_added, chart_removed, chart_lifecycle = [], [], [], [], [], []

        for d_str in sorted_dates:
            item = daily_map[d_str]
            chart_labels.append(d_str)
            chart_total.append(item["total"])
            chart_added.append(item["added_to_group"])
            chart_removed.append(item["removed_from_group"])
            chart_lifecycle.append(item["user_lifecycle"])

            daily_table.append({
                "date": d_str, "total": item["total"], "added_to_group": item["added_to_group"],
                "removed_from_group": item["removed_from_group"], "user_lifecycle": item["user_lifecycle"],
                "affected_users": sorted(list(item["affected_users"])),
                "affected_groups": sorted(list(item["affected_groups"])),
                "affected_users_count": len(item["affected_users"]),
                "affected_groups_count": len(item["affected_groups"])
            })

        daily_table.reverse()
        return {
            "summary_counts": {"c_24h": len(w_24h), "c_72h": len(w_72h), "c_168h": len(w_168h), "c_30d": len(w_30d)},
            "windows": {"w_24h": w_24h[:100], "w_72h": w_72h[:150], "w_168h": w_168h[:250], "w_30d": w_30d[:400]},
            "chart_data": {"labels": chart_labels, "total": chart_total, "added": chart_added, "removed": chart_removed, "lifecycle": chart_lifecycle},
            "daily_breakdown": daily_table
        }

    def __call__(self, db: Session = None):
        return AdService(db)

ad_service = AdService()
