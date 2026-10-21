import json
import re
import urllib.request
import urllib.error
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_
import models
from config_manager import get_setting

# Magyar kérdő- és töltelékszavak kizárása a találati zaj megszüntetéséhez
STOPWORDS = {
    "mit", "kik", "hol", "hogy", "van", "vannak", "nem", "sem", "meg", "egy", 
    "tudsz", "mondani", "keress", "keresd", "felhasznalo", "felhasznalot", 
    "felhasználó", "felhasználót", "fiok", "fiók", "fiokot", "fiókot", 
    "csoport", "csoportot", "csoportok", "adatait", "adatai", "lehet", 
    "user", "users", "group", "groups", "info", "informacio", "információ", 
    "rol", "ről", "szerepel", "letezik", "létezik", "milyen", "melyik", "nevu", "neve"
}

def fetch_ollama_models(db: Session):
    ollama_url = get_setting(db, "OLLAMA_URL", "http://ollama:11434").rstrip("/")
    url = f"{ollama_url}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []

def extract_search_terms(query: str):
    """Kinyeri a neveket, pontozott felhasználóneveket és emaileket a promptból"""
    raw_tokens = re.findall(r'[a-zA-Z0-9_\.\-]+', query.lower())
    terms = set()
    for tok in raw_tokens:
        clean = tok.strip(".-_")
        if len(clean) >= 3 and clean not in STOPWORDS:
            terms.add(clean)
            # Ha van benne pont (pl. ott.andras), külön-külön is hozzáadjuk: 'ott', 'andras'
            if "." in clean:
                for sub in clean.split("."):
                    if len(sub) >= 3 and sub not in STOPWORDS:
                        terms.add(sub)
    return list(terms)

def build_database_context(db: Session, user_query: str) -> str:
    terms = extract_search_terms(user_query)

    total_users = db.query(models.ADUser).count()
    disabled_users = db.query(models.ADUser).filter(models.ADUser.is_enabled == False).count()
    enabled_users = total_users - disabled_users
    total_groups = db.query(models.ADGroup).count()

    sections = [
        "### RENDSZER STATISZTIKA:",
        f"- Összes AD fiók a DB-ben: {total_users} (Aktív: {enabled_users}, Letiltva: {disabled_users})",
        f"- Összes AD csoport: {total_groups}",
        ""
    ]

    # Célzott felhasználó keresés
    matched_users = []
    if terms:
        user_filters = []
        for t in terms:
            user_filters.append(models.ADUser.sam_account_name.ilike(f"%{t}%"))
            user_filters.append(models.ADUser.display_name.ilike(f"%{t}%"))
            user_filters.append(models.ADUser.mail.ilike(f"%{t}%"))
        matched_users = db.query(models.ADUser).filter(or_(*user_filters)).limit(15).all()

    if matched_users:
        sections.append("### MEGTALÁLT AD FELHASZNÁLÓK ÉS JOGOSULTSÁGOK:")
        for u in matched_users:
            st = "Aktív" if u.is_enabled else "LETILTVA"
            grp_names = [g.sam_account_name for g in u.groups]
            grp_str = ", ".join(grp_names[:20]) if grp_names else "Nincs csoporttagsága"
            sections.append(
                f"- Felhasználói azonosító (sAMAccountName): {u.sam_account_name}\n"
                f"  Név: {u.display_name or 'Nincs megadva'}\n"
                f"  Email: {u.mail or 'Nincs megadva'}\n"
                f"  Fiók státusz: {st}\n"
                f"  Csoporttagságok ({len(grp_names)} db): {grp_str}"
            )
        sections.append("")

    # Célzott csoport keresés
    matched_groups = []
    if terms:
        group_filters = []
        for t in terms:
            group_filters.append(models.ADGroup.sam_account_name.ilike(f"%{t}%"))
            group_filters.append(models.ADGroup.description.ilike(f"%{t}%"))
        matched_groups = db.query(models.ADGroup).filter(or_(*group_filters)).limit(10).all()

    if matched_groups:
        sections.append("### MEGTALÁLT AD CSOPORTOK ÉS TAGOK:")
        for g in matched_groups:
            members = [u.sam_account_name for u in g.members]
            m_sample = ", ".join(members[:25]) if members else "Üres csoport"
            sections.append(
                f"- Csoport neve: {g.sam_account_name}\n"
                f"  Leírás: {g.description or '-'}\n"
                f"  Tagok száma: {len(members)} fő | Tagok mintája: [{m_sample}]"
            )
        sections.append("")

    # Eseménynapló (Audit Log)
    sections.append("### AUDIT NAPLÓ (Legutóbbi releváns események):")
    log_query = db.query(models.ADAuditLog)
    matched_logs = []
    if terms:
        log_filters = []
        for t in terms:
            log_filters.append(models.ADAuditLog.entity_name.ilike(f"%{t}%"))
            log_filters.append(models.ADAuditLog.details.ilike(f"%{t}%"))
        matched_logs = log_query.filter(or_(*log_filters)).order_by(desc(models.ADAuditLog.timestamp)).limit(20).all()

    latest_logs = log_query.order_by(desc(models.ADAuditLog.timestamp)).limit(20).all()
    all_logs = list({l.id: l for l in (matched_logs + latest_logs)}.values())
    all_logs.sort(key=lambda x: x.timestamp or datetime.min, reverse=True)

    for l in all_logs[:25]:
        t_str = l.timestamp.strftime("%Y-%m-%d %H:%M") if l.timestamp else "-"
        sections.append(f"[{t_str}] [{l.entity_type}] {l.entity_name} -> {l.change_type}: {l.details}")

    return "\n".join(sections)

def ask_ollama(db: Session, model_name: str, user_prompt: str) -> dict:
    ollama_url = get_setting(db, "OLLAMA_URL", "http://ollama:11434").rstrip("/")
    url = f"{ollama_url}/api/chat"

    context_data = build_database_context(db, user_prompt)

    system_prompt = (
        "Te egy tapasztalt, segítőkész Active Directory és IT-biztonsági szakértő vagy a TSPC csoportnál.\n"
        "SZIGORÚ SZABÁLY: MINDIG ÉS KIZÁRÓLAG MAGYAR NYELVEN VÁLASZOLJ!\n\n"
        "Az alábbiakban megkapod a belső PostgreSQL adatbázisból kinyert Active Directory adatokat.\n"
        "A válaszodat a biztosított tényadatokra alapozd. Ha egy felhasználó vagy csoport szerepel a "
        "'MEGTALÁLT AD FELHASZNÁLÓK' vagy 'MEGTALÁLT AD CSOPORTOK' szekcióban, pontosan sorold fel az adatait "
        "(név, azonosító, státusz, csoporttagságok).\n\n"
        f"--- BIZTOSÍTOTT ADATBÁZIS ADATOK ---\n{context_data}\n--- ADATOK VÉGE ---"
    )

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=90) as response:
            resp_data = json.loads(response.read().decode())
            reply = resp_data.get("message", {}).get("content", "Nem érkezett válasz.")
            return {"status": "SUCCESS", "response": reply}
    except Exception as e:
        return {"status": "ERROR", "message": f"Hiba az Ollama elérése során: {e}"}
