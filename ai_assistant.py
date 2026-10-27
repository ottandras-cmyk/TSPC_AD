import re, logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from config_manager import get_setting

logger = logging.getLogger("ai_assistant")

HUNGARIAN_SUFFIXES = [
    "képpen", "szerte", "számra",
    "ban", "ben", "nak", "nek", "val", "vel", "ból", "ből", "ról", "ről", 
    "tól", "től", "hoz", "hez", "höz", "nál", "nél", "kor", "ért",
    "jaik", "jeik", "jaim", "jeim", "jaink", "jeink", "jaitok", "jeitek",
    "aik", "eik", "aim", "eim", "aink", "eink",
    "unk", "ünk", "tok", "tek", "tök", "juk", "jük",
    "uk", "ük", "om", "em", "öm", "od", "ed", "öd", "ja", "je",
    "ok", "ek", "ök", "ak", "ik",
    "at", "et", "öt", "ot", "ra", "re", "ba", "be", "vá", "vé", "ul", "ül", "t"
]

def stem_hungarian_word(word: str) -> str:
    if not word or len(word) <= 3:
        return (word or "").lower()

    w = word.lower().strip()
    w = re.sub(r'^[^\wáéíóöőúüű]+|[^\wáéíóöőúüű]+$', '', w)

    for suffix in sorted(HUNGARIAN_SUFFIXES, key=len, reverse=True):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            w = w[:-len(suffix)]
            if w.endswith('á'): w = w[:-1] + 'a'
            elif w.endswith('é'): w = w[:-1] + 'e'
            break
            
    return w

def get_system_deep_dossier(db=None) -> dict:
    """Élő rendszer-dosszié robusztus hibakezeléssel (nem dob hibát ha a db None)."""
    u_total, u_act, u_dis, g_total, t_total = 3907, 2925, 982, 858, 1029
    db_connected = False

    if db is not None:
        try:
            u_total = db.execute(text("SELECT count(*) FROM ad_users;")).scalar() or 3907
            u_act = db.execute(text("SELECT count(*) FROM ad_users WHERE is_enabled = true;")).scalar() or 2925
            u_dis = db.execute(text("SELECT count(*) FROM ad_users WHERE is_enabled = false;")).scalar() or 982
            g_total = db.execute(text("SELECT count(*) FROM ad_groups;")).scalar() or 858
            t_total = db.execute(text("SELECT count(*) FROM ep_tasks WHERE project_id = 2403;")).scalar() or 1029
            db_connected = True
        except Exception as e:
            logger.warning("Adatbázis lekérdezési hiba a dosszié készítésekor: %s", str(e))
    else:
        logger.warning("get_system_deep_dossier meghívva érvényes db munkamenet nélkül! Alapértelmezett értékek használata.")

    return {
        "db_connected": db_connected,
        "live_metrics": {
            "total_users": u_total,
            "active_users": u_act,
            "disabled_users": u_dis,
            "total_groups": g_total,
            "helpdesk_tickets": t_total,
            "helpdesk_project_id": 2403
        },
        "integrations": {
            "telegram_chat_id": get_setting("TG_CHAT_ID", "229087988"),
            "github_repo": get_setting("GH_REPO", "ottandras-cmyk/TSPC_AD"),
            "easy_project_url": get_setting("EP_URL", "https://ep.tspc.hu/"),
            "ad_server": get_setting("AD_SERVER", "dc1.tspc.hu:389")
        },
        "summary_prompt_context": (
            f"ÉLŐ RENDSZER ÁLLAPOT ({'Online DB' if db_connected else 'Cached'}):\n"
            f"- Active Directory: {u_total} felhasználó ({u_act} aktív, {u_dis} letiltott), {g_total} csoport.\n"
            f"- Helpdesk: #2403 projekt ({t_total} hibajegy).\n"
            f"- Csatlakozás: Telegram (@tspc_IT_bot, Chat: {get_setting('TG_CHAT_ID', '229087988')}), "
            f"GitHub ({get_setting('GH_REPO', 'ottandras-cmyk/TSPC_AD')})."
        )
    }
