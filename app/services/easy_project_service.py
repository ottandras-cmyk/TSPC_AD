import html, re, json
from sqlalchemy.orm import Session
try:
    from repositories.ticket_repository import TicketRepository
except ImportError:
    from app.repositories.ticket_repository import TicketRepository

class EasyProjectService:
    def __init__(self, db: Session = None):
        self.db = db

    def _repo(self, db: Session = None):
        target = db or self.db
        if target:
            return TicketRepository(target)
        return None

    @staticmethod
    def clean_html_snippet(text_c: str, max_len: int = 140) -> str:
        if not text_c: return ""
        clean = html.unescape(text_c)
        clean = re.sub(r'<(br|p|/p)[^>]*>', ' ', clean, flags=re.IGNORECASE)
        clean = re.sub(r'<[^>]+>', '', clean)
        return (clean[:max_len] + "...") if len(clean) > max_len else re.sub(r'\s+', ' ', clean).strip()

    @staticmethod
    def is_ticket_closed(t) -> bool:
        if getattr(t, "raw_json", None):
            try:
                raw = json.loads(t.raw_json)
                if raw.get("closed_on") or (isinstance(raw.get("status"), dict) and raw.get("status", {}).get("is_closed")):
                    return True
            except Exception: pass
        s = (getattr(t, "status_name", "") or "").lower().strip()
        closed_keywords = ["lezárt", "lezárva", "megoldva", "elutasítva", "érvénytelen", "törölve", "kész", "closed", "resolved", "done"]
        return any(k in s for k in closed_keywords)

    def get_tickets_payload(self, db: Session = None):
        r = self._repo(db)
        tickets = r.get_all_helpdesk_tickets() if r else []
        payload = []
        statuses, categories, priorities, locations = set(), set(), set(), set()
        open_count, closed_count = 0, 0

        for t in tickets:
            st_name = t.status_name or "Nyitott"
            statuses.add(st_name)
            if t.category: categories.add(t.category)
            if t.priority_name: priorities.add(t.priority_name)
            if t.location: locations.add(t.location)

            if self.is_ticket_closed(t): closed_count += 1
            else: open_count += 1

            payload.append({
                "id": t.ep_id,
                "hd_serial": t.hd_serial or f"#{t.ep_id}",
                "created_on": t.created_on.strftime("%Y-%m-%d %H:%M") if t.created_on else "-",
                "created_raw": t.created_on.isoformat() if t.created_on else "",
                "updated_on": t.updated_on.strftime("%Y-%m-%d %H:%M") if t.updated_on else "-",
                "subject": t.subject or "Névtelen hibajegy",
                "author_name": t.author_name or "Ismeretlen bejelentő",
                "assigned_to_name": t.assigned_to_name or "Nincs kiosztva",
                "assigned_to_mail": t.assigned_to_mail or "-",
                "phone": t.phone or "-",
                "location": t.location or "-",
                "inventory_number": t.inventory_number or "-",
                "category": t.category or "-",
                "status_name": st_name,
                "priority_name": t.priority_name or "Normál",
                "tracker_name": t.tracker_name or "Hibajegy",
                "contact_method": t.contact_method or "-",
                "desc_snippet": self.clean_html_snippet(t.ticket_desc_html),
                "solution_snippet": self.clean_html_snippet(t.solution_html),
                "desc_html": t.ticket_desc_html or "",
                "solution_html": t.solution_html or "",
                "raw_json": t.raw_json or "{}"
            })

        return {
            "tickets": payload, "open_count": open_count, "closed_count": closed_count,
            "statuses": sorted(list(statuses)), "categories": sorted(list(categories)),
            "priorities": sorted(list(priorities)), "locations": sorted(list(locations))
        }

    def __call__(self, db: Session = None):
        return EasyProjectService(db)

easy_project_service = EasyProjectService()
