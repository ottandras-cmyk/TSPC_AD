import re
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from ldap3 import Server, Connection, ALL, SUBTREE
import models
from config_manager import get_setting

def parse_ad_datetime(val):
    if not val: return None
    if isinstance(val, datetime): return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    s = str(val).strip()
    if not s or s in ["Nincs adat", "None", "NULL"]: return None
    m = re.match(r'^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})', s)
    if m:
        try:
            p = [int(x) for x in m.groups()]
            return datetime(p[0], p[1], p[2], p[3], p[4], p[5], tzinfo=timezone.utc)
        except Exception: pass
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y%m%d_%H%M%S", "%Y%m%d-%H%M%S"):
        try: return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except Exception: continue
    return None

def parse_ad_filetime(val):
    if not val: return None
    try:
        if isinstance(val, (list, tuple)): val = val[0] if len(val) > 0 else None
        if isinstance(val, datetime): return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        val_int = int(str(val).strip())
        if val_int <= 0 or val_int > 0x7FFFFFFFFFFFFFFF: return None
        epoch_sec = (val_int / 10000000) - 11644473600
        if epoch_sec < 0: return None
        return datetime.fromtimestamp(epoch_sec, tz=timezone.utc)
    except Exception: return None

def extract_ou_path(dn: str) -> str:
    if not dn: return ""
    ou_matches = re.findall(r'OU=([^,]+)', dn, re.IGNORECASE)
    return ";".join(ou_matches)

def determine_user_status(member_of_list, is_enabled: bool) -> str:
    for g_dn in (member_of_list or []):
        g_str = str(g_dn)
        if re.search(r'CN=Hosszútávúszabadság', g_str, re.IGNORECASE): return "Hosszútávúszabadság"
        elif re.search(r'CN=Külsös', g_str, re.IGNORECASE): return "Külsös"
        elif re.search(r'CN=Távozottak', g_str, re.IGNORECASE): return "Távozottak"
    return "Aktív normál user" if is_enabled else "Letiltva"

def get_attr(entry, name, default=None):
    try:
        if hasattr(entry, name):
            val = getattr(entry, name).value
            if val is not None: return val
        if name in entry:
            val = entry[name].value
            if val is not None: return val
        if hasattr(entry, name) and hasattr(getattr(entry, name), 'raw_values'):
            raw = getattr(entry, name).raw_values
            if raw and raw[0]:
                if isinstance(raw[0], bytes): return raw[0].decode('utf-8', errors='ignore')
                return str(raw[0])
    except Exception: pass
    return default

def get_guid(entry):
    try:
        val = entry['objectGUID'].raw_values[0]
        if isinstance(val, bytes): return uuid.UUID(bytes_le=val)
    except Exception: pass
    try:
        val = entry['objectGUID'].value
        if isinstance(val, uuid.UUID): return val
        if isinstance(val, str): return uuid.UUID(val)
    except Exception: pass
    return uuid.uuid4()

def run_ad_sync(db: Session) -> dict:
    server_addr = get_setting(db, "AD_SERVER")
    bind_user = get_setting(db, "AD_USER")
    bind_pass = get_setting(db, "AD_PASSWORD")
    search_base = get_setting(db, "AD_SEARCH_BASE")

    if not all([server_addr, bind_user, bind_pass, search_base]):
        raise ValueError("Hiányzó Active Directory kapcsolati beállítások!")

    server = Server(server_addr, get_info=ALL)
    conn = Connection(server, user=bind_user, password=bind_pass, auto_bind=True)

    now_utc = datetime.now(timezone.utc)
    changes_count = 0

    # 1. CSOPORTOK
    group_attrs = ['objectGUID', 'sAMAccountName', 'distinguishedName', 'description', 'groupType', 'objectSid', 'whenCreated', 'whenChanged']
    conn.search(search_base=search_base, search_filter='(&(objectCategory=group)(objectClass=group))', search_scope=SUBTREE, attributes=group_attrs)
    
    db_groups = {g.sam_account_name.lower(): g for g in db.query(models.ADGroup).all()}
    for entry in conn.entries:
        sam = str(get_attr(entry, 'sAMAccountName', '')).strip()
        if not sam: continue
        sam_key = sam.lower()

        raw_type = get_attr(entry, 'groupType')
        is_security = bool(int(raw_type) & 0x80000000) if raw_type is not None else True
        grp_type_str = "Biztonsági Csoport" if is_security else "Terjesztési Lista"

        dn = str(get_attr(entry, 'distinguishedName', ''))
        desc = str(get_attr(entry, 'description') or '').strip()
        sid = str(get_attr(entry, 'objectSid') or '')
        w_created = parse_ad_datetime(get_attr(entry, 'whenCreated'))
        w_changed = parse_ad_datetime(get_attr(entry, 'whenChanged'))

        if sam_key not in db_groups:
            # Csak akkor tekintjük új csoportnak, ha valóban az elmúlt 3 napban jött létre az AD-ban
            is_truly_new_group = False
            if w_created and (now_utc - w_created).total_seconds() < 86400 * 3:
                is_truly_new_group = True

            new_grp = models.ADGroup(
                object_guid=get_guid(entry),
                sam_account_name=sam,
                distinguished_name=dn,
                description=desc,
                group_type=grp_type_str,
                object_sid=sid,
                source_type="AD_SYNC",
                source_ref="LIVE_AD",
                when_created=w_created or now_utc,
                when_changed=w_changed or now_utc,
                last_synced_at=now_utc
            )
            db.add(new_grp)
            db.flush()
            db_groups[sam_key] = new_grp

            if is_truly_new_group:
                db.add(models.ADAuditLog(
                    timestamp=w_created or now_utc,
                    entity_type="GROUP",
                    entity_name=sam,
                    change_type="GROUP_CREATED",
                    details=f"Új AD csoport létrehozva ({grp_type_str})",
                    raw_diff=None,
                    source_type="AD_SYNC",
                    source_ref="LIVE_AD"
                ))
                changes_count += 1
        else:
            g = db_groups[sam_key]
            g.distinguished_name = dn
            if desc: g.description = desc
            g.group_type = grp_type_str
            if w_created: g.when_created = w_created
            if w_changed: g.when_changed = w_changed
            g.source_type = "AD_SYNC"
            g.source_ref = "LIVE_AD"
            g.last_synced_at = now_utc

    # 2. FELHASZNÁLÓK
    user_attrs = [
        'objectGUID', 'sAMAccountName', 'displayName', 'mail', 'telephoneNumber',
        'mobile', 'physicalDeliveryOfficeName', 'title', 'department', 'company',
        'description', 'objectSid', 'distinguishedName', 'userAccountControl',
        'whenCreated', 'whenChanged', 'memberOf', 'lastLogonTimestamp', 'lastLogon'
    ]
    conn.search(search_base=search_base, search_filter='(&(objectCategory=person)(objectClass=user))', search_scope=SUBTREE, attributes=user_attrs)

    db_users = {u.sam_account_name.lower(): u for u in db.query(models.ADUser).all()}

    for entry in conn.entries:
        sam = str(get_attr(entry, 'sAMAccountName', '')).strip()
        if not sam: continue
        sam_key = sam.lower()

        dn = str(get_attr(entry, 'distinguishedName', ''))
        disp_name = str(get_attr(entry, 'displayName') or '')
        mail = str(get_attr(entry, 'mail') or '')
        phone = str(get_attr(entry, 'telephoneNumber') or '')
        mobile = str(get_attr(entry, 'mobile') or '')
        office = str(get_attr(entry, 'physicalDeliveryOfficeName') or '')
        title = str(get_attr(entry, 'title') or '')
        dept = str(get_attr(entry, 'department') or '')
        comp = str(get_attr(entry, 'company') or '')
        desc = str(get_attr(entry, 'description') or '').strip()
        sid = str(get_attr(entry, 'objectSid') or '')
        w_created = parse_ad_datetime(get_attr(entry, 'whenCreated'))
        w_changed = parse_ad_datetime(get_attr(entry, 'whenChanged'))

        uac = get_attr(entry, 'userAccountControl') or 512
        is_enabled = not bool(int(uac) & 2)

        dt_llts = parse_ad_filetime(get_attr(entry, 'lastLogonTimestamp'))
        dt_ll = parse_ad_filetime(get_attr(entry, 'lastLogon'))
        valid_logon_dts = [d for d in [dt_llts, dt_ll] if d is not None]
        last_logon_dt = max(valid_logon_dts) if valid_logon_dts else None

        ou_path = extract_ou_path(dn)

        member_of_raw = []
        try:
            if 'memberOf' in entry:
                member_of_raw = entry['memberOf'].values or []
        except Exception: pass
        user_status = determine_user_status(member_of_raw, is_enabled)

        # Aktuális csoportnevek kinyerése
        current_user_group_names = set()
        for g_dn in member_of_raw:
            match = re.search(r'CN=([^,]+)', str(g_dn), re.IGNORECASE)
            if match: current_user_group_names.add(match.group(1).lower())

        if sam_key not in db_users:
            # Csak akkor tekintjük új fióknak, ha valóban az elmúlt 3 napban jött létre az AD-ban
            is_truly_new_user = False
            if w_created and (now_utc - w_created).total_seconds() < 86400 * 3:
                is_truly_new_user = True

            new_u = models.ADUser(
                object_guid=get_guid(entry),
                sam_account_name=sam,
                display_name=disp_name,
                mail=mail,
                telephone_number=phone,
                mobile=mobile,
                office=office,
                title=title,
                department=dept,
                company=comp,
                description=desc,
                object_sid=sid,
                distinguished_name=dn,
                is_enabled=is_enabled,
                last_logon_date=last_logon_dt,
                user_status=user_status,
                ou_path=ou_path,
                source_type="AD_SYNC",
                source_ref="LIVE_AD",
                when_created=w_created or now_utc,
                when_changed=w_changed or now_utc,
                last_synced_at=now_utc
            )
            db.add(new_u)
            db.flush()
            db_users[sam_key] = new_u
            u_obj = new_u

            # Kezdeti csoporttagságok csendes beállítása (nem generál false-positive záport)
            for ag in current_user_group_names:
                g_obj = db_groups.get(ag)
                if g_obj and g_obj not in u_obj.groups:
                    u_obj.groups.append(g_obj)

            if is_truly_new_user:
                db.add(models.ADAuditLog(
                    timestamp=w_created or now_utc,
                    entity_type="USER",
                    entity_name=sam,
                    change_type="USER_CREATED",
                    details=f"Új AD felhasználó létrehozva ({disp_name})",
                    raw_diff=None,
                    source_type="AD_SYNC",
                    source_ref="LIVE_AD"
                ))
                changes_count += 1
        else:
            u_obj = db_users[sam_key]

            # FONTOS: Megvizsgáljuk, hogy ez a fiók most vált-e át CSV_IMPORT-ból élő AD_SYNC-re!
            is_first_live_sync_for_user = (getattr(u_obj, "source_type", None) == "CSV_IMPORT")

            if w_created: u_obj.when_created = w_created
            if w_changed: u_obj.when_changed = w_changed
            if desc: u_obj.description = desc
            if last_logon_dt:
                if not u_obj.last_logon_date or last_logon_dt > u_obj.last_logon_date:
                    u_obj.last_logon_date = last_logon_dt

            # Ha ez már korábban is élő AD szinkron volt, figyeljük a fiók állapotváltozásait
            if not is_first_live_sync_for_user:
                if u_obj.is_enabled != is_enabled:
                    ch_type = "USER_ENABLED" if is_enabled else "USER_DISABLED"
                    db.add(models.ADAuditLog(
                        timestamp=now_utc,
                        entity_type="USER",
                        entity_name=sam,
                        change_type=ch_type,
                        details="Fiók státusz változott az AD-ban",
                        raw_diff=None,
                        source_type="AD_SYNC",
                        source_ref="LIVE_AD"
                    ))
                    changes_count += 1

                if u_obj.user_status and u_obj.user_status != user_status:
                    db.add(models.ADAuditLog(
                        timestamp=now_utc,
                        entity_type="USER",
                        entity_name=sam,
                        change_type="STATUS_CHANGED",
                        details=f"Besorolás változott: '{u_obj.user_status}' -> '{user_status}'",
                        raw_diff=None,
                        source_type="AD_SYNC",
                        source_ref="LIVE_AD"
                    ))
                    changes_count += 1

            u_obj.is_enabled = is_enabled
            u_obj.display_name = disp_name or u_obj.display_name
            if mail: u_obj.mail = mail
            if phone: u_obj.telephone_number = phone
            if mobile: u_obj.mobile = mobile
            if office: u_obj.office = office
            if title: u_obj.title = title
            if dept: u_obj.department = dept
            if comp: u_obj.company = comp
            if sid: u_obj.object_sid = sid
            u_obj.distinguished_name = dn
            u_obj.user_status = user_status
            u_obj.ou_path = ou_path
            u_obj.source_type = "AD_SYNC"
            u_obj.source_ref = "LIVE_AD"
            u_obj.last_synced_at = now_utc

            # --- CSOPORTTAGSÁGOK KEZELÉSE ---
            if is_first_live_sync_for_user:
                # HATÓKÖR-ILLESZTÉS (Baseline Reconciliation):
                # A CSV-ben szűkebb/más volt a csoportlista mint az élő AD-ben.
                # Felvesszük a valós élő AD állapotot alapként, DE NEM generálunk több száz false ADDED/REMOVED eseményt!
                u_obj.groups.clear()
                for ag in current_user_group_names:
                    g_obj = db_groups.get(ag)
                    if g_obj:
                        u_obj.groups.append(g_obj)
            else:
                # TÉNYLEGES ÉLŐ VÁLTOZÁSOK KÖVETÉSE
                existing_db_group_names = {g.sam_account_name.lower() for g in u_obj.groups}

                for ag in (current_user_group_names - existing_db_group_names):
                    g_obj = db_groups.get(ag)
                    if g_obj:
                        u_obj.groups.append(g_obj)
                        db.add(models.ADAuditLog(
                            timestamp=now_utc,
                            entity_type="MEMBERSHIP",
                            entity_name=sam,
                            change_type="ADDED_TO_GROUP",
                            details=f"Hozzáadva a(z) '{g_obj.sam_account_name}' csoporthoz",
                            raw_diff=None,
                            source_type="AD_SYNC",
                            source_ref="LIVE_AD"
                        ))
                        changes_count += 1

                for rg in (existing_db_group_names - current_user_group_names):
                    g_obj = db_groups.get(rg)
                    if g_obj and g_obj in u_obj.groups:
                        u_obj.groups.remove(g_obj)
                        db.add(models.ADAuditLog(
                            timestamp=now_utc,
                            entity_type="MEMBERSHIP",
                            entity_name=sam,
                            change_type="REMOVED_FROM_GROUP",
                            details=f"Eltávolítva a(z) '{g_obj.sam_account_name}' csoportból",
                            raw_diff=None,
                            source_type="AD_SYNC",
                            source_ref="LIVE_AD"
                        ))
                        changes_count += 1

    db.commit()
    conn.unbind()
    return {"detektalt_valtozasok": changes_count}
