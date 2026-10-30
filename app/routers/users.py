from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import Boolean, String, func, literal, or_, select
from sqlalchemy.orm import Session, joinedload
from database import get_db
from auth import COOKIE_NAME, verify_session_token
from config_manager import load_local_settings, save_local_settings
import models

router = APIRouter(prefix="/api", tags=["users"])

TABLE_LAYOUT_DEFAULTS = {
    "users": [230, 160, 230, 180, 170, 170, 100],
    "groups": [240, 160, 170, 110, 420, 120],
}


@router.get("/users/table-layout")
def get_users_table_layout():
    settings = load_local_settings()
    saved_layout = settings.get("ui_table_layouts", {})
    if not isinstance(saved_layout, dict):
        saved_layout = {}
    return {
        "status": "SUCCESS",
        "layouts": {
            table_name: _validated_column_widths(table_name, saved_layout.get(table_name))
            for table_name in TABLE_LAYOUT_DEFAULTS
        },
    }


@router.put("/users/table-layout")
async def save_users_table_layout(request: Request):
    try:
        payload = await request.json()
    except Exception as error:
        raise HTTPException(status_code=400, detail="A táblázat-elrendezés JSON formátuma érvénytelen.") from error
    layouts = payload.get("layouts") if isinstance(payload, dict) else None
    if not isinstance(layouts, dict):
        raise HTTPException(status_code=400, detail="A táblázat-elrendezések megadása kötelező.")

    current_settings = load_local_settings()
    saved_layouts = current_settings.get("ui_table_layouts", {})
    if not isinstance(saved_layouts, dict):
        saved_layouts = {}
    for table_name, widths in layouts.items():
        if table_name not in TABLE_LAYOUT_DEFAULTS:
            raise HTTPException(status_code=400, detail="Ismeretlen táblázat-elrendezés.")
        saved_layouts[table_name] = _validated_column_widths(table_name, widths, strict=True)
    current_settings["ui_table_layouts"] = saved_layouts
    if not save_local_settings(current_settings):
        raise HTTPException(status_code=500, detail="A táblázat-elrendezés helyi mentése nem sikerült.")
    return {
        "status": "SUCCESS",
        "layouts": {
            name: _validated_column_widths(name, saved_layouts.get(name))
            for name in TABLE_LAYOUT_DEFAULTS
        },
    }


def _validated_column_widths(table_name: str, widths, strict: bool = False) -> list[int]:
    defaults = TABLE_LAYOUT_DEFAULTS[table_name]
    if not isinstance(widths, list) or len(widths) != len(defaults):
        if strict:
            raise HTTPException(status_code=400, detail="Az oszlopszélességek száma nem megfelelő.")
        return defaults.copy()
    if any(type(width) is not int or not 60 <= width <= 1200 for width in widths):
        if strict:
            raise HTTPException(status_code=400, detail="Az oszlopszélesség 60 és 1200 pixel közötti egész szám lehet.")
        return defaults.copy()
    return widths


def safe_get_user(request: Request):
    try:
        token = request.cookies.get(COOKIE_NAME)
        if token:
            user, _ = verify_session_token(token)
            return user
    except Exception: pass
    return "tadmin"

@router.get("/users/all")
@router.get("/users")
@router.get("/users/list")
def get_all_users(request: Request, db: Session = Depends(get_db)):
    db_users = (
        db.query(models.ADUser)
        .filter(
            ~models.ADUser.sam_account_name.contains('@'),
            ~models.ADUser.mail.startswith('S-1-5-'),
            ~models.ADUser.sam_account_name.contains(' ')
        )
        .options(joinedload(models.ADUser.groups))
        .order_by(models.ADUser.display_name.asc().nullslast())
        .all()
    )

    users_payload = []
    total_active = 0

    for u in db_users:
        is_act = bool(u.is_enabled)
        if is_act: total_active += 1

        grp_names = [g.sam_account_name for g in u.groups if g.sam_account_name]

        users_payload.append({
            "id": str(u.object_guid) if u.object_guid else "",
            "guid": str(u.object_guid) if u.object_guid else "",
            "sam_account_name": u.sam_account_name or "",
            "display_name": u.display_name or u.sam_account_name or "-",
            "mail": u.mail or "-",
            "title": u.title or "-",
            "department": u.department or "-",
            "company": u.company or "TSPC",
            "office": u.office or "-",
            "telephone_number": u.telephone_number or "-",
            "mobile": u.mobile or "-",
            "user_status": u.user_status or ("Aktív normál user" if is_act else "Letiltva"),
            "is_enabled": is_act,
            "last_logon": u.last_logon_date.strftime("%Y-%m-%d %H:%M") if u.last_logon_date else "-",
            "last_logon_date": u.last_logon_date.strftime("%Y-%m-%d %H:%M") if u.last_logon_date else "-",
            "when_created": u.when_created.strftime("%Y-%m-%d") if u.when_created else "-",
            "groups": grp_names,
            "groups_count": len(grp_names)
        })

    return {
        "status": "SUCCESS",
        "total_count": len(users_payload),
        "total_users": len(users_payload),
        "active_users": total_active,
        "disabled_users": len(users_payload) - total_active,
        "users": users_payload,
        "data": users_payload
    }

@router.get("/users/{sam}/detail")
def get_user_detail(sam: str, db: Session = Depends(get_db)):
    user = (
        db.query(models.ADUser)
        .options(joinedload(models.ADUser.groups))
        .filter(func.lower(models.ADUser.sam_account_name) == sam.lower())
        .first()
    )
    if user is None:
        raise HTTPException(status_code=404, detail="A felhasználó nem található.")

    user_data = {}
    for column in models.ADUser.__table__.columns:
        value = getattr(user, column.name)
        if value is not None and hasattr(value, "isoformat"):
            value = value.isoformat()
        elif value is not None and not isinstance(value, (str, int, float, bool)):
            value = str(value)
        user_data[column.name] = value

    groups = sorted(
        (group for group in user.groups if group.sam_account_name),
        key=lambda group: group.sam_account_name.casefold(),
    )
    serialized_groups = []
    for group in groups:
        raw_group_type = (group.group_type or "").strip()
        normalized_type = raw_group_type.casefold()
        if normalized_type in {"terjesztési lista", "distribution list"}:
            membership_type = "distribution_list"
        elif normalized_type in {"biztonsági csoport", "security group"}:
            membership_type = "security_group"
        else:
            try:
                membership_type = (
                    "security_group"
                    if int(raw_group_type) & 0x80000000
                    else "distribution_list"
                )
            except ValueError:
                membership_type = "group"

        serialized_groups.append({
            "name": group.sam_account_name,
            "sam_account_name": group.sam_account_name,
            "group_type": raw_group_type or "AD-csoport",
            "membership_type": membership_type,
            "description": group.description or "",
            "distinguished_name": group.distinguished_name or "",
        })

    return {
        "status": "SUCCESS",
        "sam_account_name": user.sam_account_name,
        "user": user_data,
        "groups_count": len(serialized_groups),
        "groups": serialized_groups,
    }

@router.get("/users/{sam}/history")
def get_user_history(sam: str, db: Session = Depends(get_db)):
    logs = db.query(models.ADAuditLog).filter(models.ADAuditLog.entity_name == sam).order_by(models.ADAuditLog.timestamp.desc()).limit(100).all()
    res = []
    for l in logs:
        res.append({
            "id": l.id,
            "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "-",
            "change_type": l.change_type or "-",
            "details": l.details or "-",
            "source_ref": l.source_ref or "AD"
        })
    return {"status": "SUCCESS", "history": res, "data": res}

@router.get("/groups/all")
@router.get("/groups")
def get_all_groups(db: Session = Depends(get_db)):
    grps = db.query(models.ADGroup).order_by(models.ADGroup.sam_account_name.asc()).all()
    user_counts = dict(db.execute(
        select(
            models.group_memberships.c.group_guid,
            func.count(),
        ).group_by(models.group_memberships.c.group_guid)
    ).all())
    nested_counts = dict(db.execute(
        select(
            models.group_group_memberships.c.parent_group_guid,
            func.count(),
        ).group_by(models.group_group_memberships.c.parent_group_guid)
    ).all())
    res = []
    for g in grps:
        user_member_count = user_counts.get(g.object_guid, 0)
        nested_group_count = nested_counts.get(g.object_guid, 0)
        res.append({
            "guid": str(g.object_guid) if g.object_guid else "",
            "sam_account_name": g.sam_account_name or "",
            "description": g.description or "-",
            "group_type": g.group_type or "Security Group",
            "when_created": g.when_created.isoformat() if g.when_created else None,
            "members_count": user_member_count + nested_group_count,
            "users_count": user_member_count,
            "nested_groups_count": nested_group_count,
        })
    return {"status": "SUCCESS", "groups": res, "data": res}

@router.get("/groups/{sam}/detail")
def get_group_detail(
    sam: str,
    q: str = Query(default="", max_length=255),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="display_name"),
    sort_order: str = Query(default="asc"),
    db: Session = Depends(get_db),
):
    group = (
        db.query(models.ADGroup)
        .filter(func.lower(models.ADGroup.sam_account_name) == sam.lower())
        .first()
    )
    if group is None:
        raise HTTPException(status_code=404, detail="A csoport nem található.")

    user_members = (
        db.query(
            literal("user").label("entity_type"),
            models.ADUser.object_guid.label("guid"),
            models.ADUser.display_name.label("display_name"),
            models.ADUser.sam_account_name.label("sam_account_name"),
            models.ADUser.object_sid.label("object_sid"),
            models.ADUser.mail.label("mail"),
            models.ADUser.user_principal_name.label("user_principal_name"),
            models.ADUser.is_enabled.label("is_enabled"),
            models.ADUser.user_status.label("user_status"),
            models.ADUser.title.label("title"),
            models.ADUser.department.label("department"),
            models.ADUser.company.label("company"),
            models.ADUser.office.label("office"),
            models.ADUser.telephone_number.label("telephone_number"),
            models.ADUser.mobile.label("mobile"),
            models.ADUser.description.label("description"),
            models.ADUser.distinguished_name.label("distinguished_name"),
            models.ADUser.ou_path.label("ou_path"),
            models.ADUser.when_created.label("when_created"),
            models.ADUser.when_changed.label("when_changed"),
            models.ADUser.last_logon_date.label("last_logon_date"),
            models.ADUser.last_synced_at.label("last_synced_at"),
            models.group_memberships.c.assigned_at.label("assigned_at"),
            literal(None, type_=String()).label("group_type"),
        )
        .join(
            models.group_memberships,
            models.group_memberships.c.user_guid == models.ADUser.object_guid,
        )
        .filter(models.group_memberships.c.group_guid == group.object_guid)
    )
    nested_groups = (
        db.query(
            literal("group").label("entity_type"),
            models.ADGroup.object_guid.label("guid"),
            models.ADGroup.sam_account_name.label("display_name"),
            models.ADGroup.sam_account_name.label("sam_account_name"),
            models.ADGroup.object_sid.label("object_sid"),
            literal(None, type_=String()).label("mail"),
            literal(None, type_=String()).label("user_principal_name"),
            literal(None, type_=Boolean()).label("is_enabled"),
            literal(None, type_=String()).label("user_status"),
            literal(None, type_=String()).label("title"),
            literal(None, type_=String()).label("department"),
            literal(None, type_=String()).label("company"),
            literal(None, type_=String()).label("office"),
            literal(None, type_=String()).label("telephone_number"),
            literal(None, type_=String()).label("mobile"),
            models.ADGroup.description.label("description"),
            models.ADGroup.distinguished_name.label("distinguished_name"),
            literal(None, type_=String()).label("ou_path"),
            models.ADGroup.when_created.label("when_created"),
            models.ADGroup.when_changed.label("when_changed"),
            literal(None).label("last_logon_date"),
            models.ADGroup.last_synced_at.label("last_synced_at"),
            models.group_group_memberships.c.assigned_at.label("assigned_at"),
            models.ADGroup.group_type.label("group_type"),
        )
        .join(
            models.group_group_memberships,
            models.group_group_memberships.c.member_group_guid == models.ADGroup.object_guid,
        )
        .filter(models.group_group_memberships.c.parent_group_guid == group.object_guid)
    )
    combined_members = user_members.union_all(nested_groups).subquery()
    member_query = select(combined_members)
    member_count = db.execute(
        select(func.count()).select_from(combined_members)
    ).scalar_one()
    if q.strip():
        search = f"%{q.strip()}%"
        member_query = member_query.where(or_(
            combined_members.c.display_name.ilike(search),
            combined_members.c.sam_account_name.ilike(search),
            combined_members.c.mail.ilike(search),
            combined_members.c.object_sid.ilike(search),
            combined_members.c.group_type.ilike(search),
            combined_members.c.distinguished_name.ilike(search),
        ))

    filtered_count = db.execute(
        select(func.count()).select_from(member_query.subquery())
    ).scalar_one()
    sortable_columns = {
        "entity_type": combined_members.c.entity_type,
        "display_name": combined_members.c.display_name,
        "sam_account_name": combined_members.c.sam_account_name,
        "mail": combined_members.c.mail,
        "is_enabled": combined_members.c.is_enabled,
        "assigned_at": combined_members.c.assigned_at,
    }
    if sort_by not in sortable_columns:
        raise HTTPException(status_code=400, detail="Érvénytelen rendezési mező.")
    if sort_order not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="Érvénytelen rendezési irány.")

    sort_column = sortable_columns[sort_by]
    sort_expression = sort_column.asc() if sort_order == "asc" else sort_column.desc()
    members = db.execute(
        member_query
        .order_by(sort_expression.nullslast(), combined_members.c.sam_account_name.asc())
        .offset(offset)
        .limit(limit)
    ).mappings().all()

    def format_datetime(value):
        return value.isoformat() if value else None

    serialized_members = [{
        "entity_type": member["entity_type"],
        "guid": str(member["guid"]) if member["guid"] else "",
        "sam_account_name": member["sam_account_name"] or "",
        "display_name": member["display_name"] or member["sam_account_name"] or "",
        "object_sid": member["object_sid"] or "",
        "mail": member["mail"] or "",
        "user_principal_name": member["user_principal_name"] or "",
        "is_enabled": bool(member["is_enabled"]) if member["is_enabled"] is not None else None,
        "user_status": member["user_status"] or "",
        "title": member["title"] or "",
        "department": member["department"] or "",
        "company": member["company"] or "",
        "office": member["office"] or "",
        "telephone_number": member["telephone_number"] or "",
        "mobile": member["mobile"] or "",
        "description": member["description"] or "",
        "distinguished_name": member["distinguished_name"] or "",
        "ou_path": member["ou_path"] or "",
        "when_created": format_datetime(member["when_created"]),
        "when_changed": format_datetime(member["when_changed"]),
        "last_logon_date": format_datetime(member["last_logon_date"]),
        "last_synced_at": format_datetime(member["last_synced_at"]),
        "assigned_at": format_datetime(member["assigned_at"]),
        "group_type": member["group_type"] or "",
    } for member in members]

    next_offset = offset + len(serialized_members)
    return {
        "status": "SUCCESS",
        "group": {
            "guid": str(group.object_guid) if group.object_guid else "",
            "sam_account_name": group.sam_account_name or "",
            "description": group.description or "",
            "group_type": group.group_type or "AD-csoport",
            "distinguished_name": group.distinguished_name or "",
            "when_created": format_datetime(group.when_created),
            "when_changed": format_datetime(group.when_changed),
            "object_sid": group.object_sid or "",
        },
        "member_count": member_count,
        "filtered_count": filtered_count,
        "offset": offset,
        "limit": limit,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "next_offset": next_offset if next_offset < filtered_count else None,
        "members": serialized_members,
    }
