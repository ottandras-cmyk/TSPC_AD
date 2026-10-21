import uuid
from datetime import datetime, timezone
from ldap3 import Server, Connection, NTLM, SIMPLE, SUBTREE
from ldap3.protocol.formatters.standard import format_sid
from sqlalchemy.orm import Session
from ldap_client import parse_ad_server
from config_manager import get_setting
import models

def get_attr(entry, attr_name, default=""):
    """Biztonságos attribútum kinyerés az ldap3 entry-ből"""
    try:
        val = entry['attributes'].get(attr_name)
        if val is None or val == []:
            return default
        if isinstance(val, list):
            return str(val[0])
        return str(val)
    except:
        return default

def get_date_attr(entry, attr_name):
    """Biztonságos dátum kinyerés az AD GeneralizedTime formátumából"""
    try:
        val = entry['attributes'].get(attr_name)
        if not val:
            return None
        # Az AD datetime objektumként vagy stringként is visszaadhatja
        if isinstance(val, list):
            val = val[0]
        if isinstance(val, datetime):
            return val
        
        # Ha string (pl. '20230101120000.0Z')
        val_str = str(val).split('.')[0] # Leveágjuk a törtmásodpercet
        val_str = val_str.replace('Z', '')
        if len(val_str) == 14:
            return datetime.strptime(val_str, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        return None
    except:
        return None

def run_ad_sync(db: Session):
    raw_server = get_setting(db, "AD_SERVER")
    user = get_setting(db, "AD_USER")
    password = get_setting(db, "AD_PASSWORD")
    search_base = get_setting(db, "AD_SEARCH_BASE")

    if not all([raw_server, user, password, search_base]):
        raise Exception("Hiányzó AD konfiguráció!")

    host, port, use_ssl = parse_ad_server(raw_server)
    
    # Kifejezetten megmondjuk az ldap3-nak, hogy az összes meglévő attribútumot küldje át!
    # Ha a get_info=ALL nincs megfelelően beállítva az AD oldalon, explicit kérjük a mezőket.
    server = Server(host=host, port=port, use_ssl=use_ssl, connect_timeout=10)
    auth_type = SIMPLE if "@" in user else NTLM
    conn = Connection(server, user=user, password=password, authentication=auth_type, auto_bind=True)

    now = datetime.now(timezone.utc)
    changes_count = 0

    # 1. CSOPORTOK (Kifejezetten kérjük a mezőket!)
    group_attrs = [
        'objectGUID', 'sAMAccountName', 'distinguishedName', 'description', 
        'groupType', 'objectSid', 'whenCreated', 'whenChanged'
    ]
    group_paged = conn.extend.standard.paged_search(
        search_base, "(objectCategory=group)", SUBTREE, 
        attributes=group_attrs, paged_size=500
    )
    
    ad_groups_map = {}
    for entry in group_paged:
        raw_guid = entry.get('raw_attributes', {}).get('objectGUID', [None])[0]
        if not raw_guid: continue
        g_uuid = uuid.UUID(bytes_le=raw_guid)
        
        dn = get_attr(entry, 'distinguishedName')
        gtype_val = int(get_attr(entry, 'groupType', '0'))
        is_security = bool(gtype_val & 2147483648)
        group_type_str = "Biztonsági (Security)" if is_security else "Terjesztési lista (Distribution)"
        
        raw_sid = entry.get('raw_attributes', {}).get('objectSid', [None])[0]
        sid_str = format_sid(raw_sid) if raw_sid else ""

        db_group = db.query(models.ADGroup).filter(models.ADGroup.object_guid == g_uuid).first()
        if not db_group:
            db_group = models.ADGroup(
                object_guid=g_uuid, 
                sam_account_name=get_attr(entry, 'sAMAccountName'),
                distinguished_name=dn, 
                description=get_attr(entry, 'description'),
                group_type=group_type_str,
                object_sid=sid_str,
                when_created=get_date_attr(entry, 'whenCreated'),
                when_changed=get_date_attr(entry, 'whenChanged'),
                last_synced_at=now
            )
            db.add(db_group)
        else:
            db_group.distinguished_name = dn
            db_group.description = get_attr(entry, 'description')
            db_group.group_type = group_type_str
            db_group.when_changed = get_date_attr(entry, 'whenChanged')
            db_group.last_synced_at = now
            
        ad_groups_map[dn.lower()] = db_group
    
    db.commit()

    # 2. FELHASZNÁLÓK (Kifejezetten felsoroljuk az összes kért attribútumot!)
    user_attrs = [
        'objectGUID', 'sAMAccountName', 'displayName', 'mail', 'userAccountControl', 
        'memberOf', 'distinguishedName', 'givenName', 'sn', 'description', 
        'physicalDeliveryOfficeName', 'title', 'department', 'company', 
        'telephoneNumber', 'mobile', 'objectSid', 'whenCreated', 'whenChanged'
    ]
    user_paged = conn.extend.standard.paged_search(
        search_base, "(&(objectCategory=person)(objectClass=user))", SUBTREE, 
        attributes=user_attrs, paged_size=500
    )
    
    for entry in user_paged:
        raw_guid = entry.get('raw_attributes', {}).get('objectGUID', [None])[0]
        if not raw_guid: continue
        u_uuid = uuid.UUID(bytes_le=raw_guid)
        sam_name = get_attr(entry, 'sAMAccountName')
        uac = int(get_attr(entry, 'userAccountControl', '512'))
        is_enabled = not bool(uac & 2)
        
        raw_sid = entry.get('raw_attributes', {}).get('objectSid', [None])[0]
        sid_str = format_sid(raw_sid) if raw_sid else ""

        db_user = db.query(models.ADUser).filter(models.ADUser.object_guid == u_uuid).first()
        if not db_user:
            db_user = models.ADUser(object_guid=u_uuid, sam_account_name=sam_name, last_synced_at=now)
            db.add(db_user)
            db.flush()

        db_user.display_name = get_attr(entry, 'displayName', sam_name)
        db_user.mail = get_attr(entry, 'mail')
        db_user.distinguished_name = get_attr(entry, 'distinguishedName')
        db_user.is_enabled = is_enabled
        
        # Új AD Property mezők mentése:
        db_user.first_name = get_attr(entry, 'givenName')
        db_user.last_name = get_attr(entry, 'sn')
        db_user.description = get_attr(entry, 'description')
        db_user.office = get_attr(entry, 'physicalDeliveryOfficeName')
        db_user.title = get_attr(entry, 'title')
        db_user.department = get_attr(entry, 'department')
        db_user.company = get_attr(entry, 'company')
        db_user.telephone_number = get_attr(entry, 'telephoneNumber')
        db_user.mobile = get_attr(entry, 'mobile')
        
        db_user.object_sid = sid_str
        db_user.when_created = get_date_attr(entry, 'whenCreated')
        db_user.when_changed = get_date_attr(entry, 'whenChanged')
        db_user.last_synced_at = now

        # Tagság diff feldolgozás
        raw_member_of = entry['attributes'].get('memberOf') or []
        if isinstance(raw_member_of, str): raw_member_of = [raw_member_of]
        current_dns = set(str(g).lower() for g in raw_member_of)
        
        existing_map = {g.distinguished_name.lower(): g for g in db_user.groups}
        existing_dns = set(existing_map.keys())

        for g_dn in (current_dns - existing_dns):
            if g_dn in ad_groups_map:
                db_user.groups.append(ad_groups_map[g_dn])
                changes_count += 1
                
        for g_dn in (existing_dns - current_dns):
            if g_dn in existing_map and existing_map[g_dn] in db_user.groups:
                db_user.groups.remove(existing_map[g_dn])
                changes_count += 1

    db.commit()
    conn.unbind()
    return {"status": "SUCCESS", "detektalt_valtozasok": changes_count}
