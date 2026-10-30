import json
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert

from database import Base, SessionLocal, engine
from models import (
    SP_Atadas_atvetel,
    SP_IT_Inventory,
    SP_O365LicenceInfo,
    SP_eszkozleltar_nonIT,
    SharePointItemChange,
    SharePointSyncHistory,
)

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
INVENTORY_LIST_URL_NAME = "IT_Inventory"
SHAREPOINT_LIST_MODELS = {
    "eszkozleltar_nonIT": SP_eszkozleltar_nonIT,
    "O365LicenceInfo": SP_O365LicenceInfo,
    "Atadas_atvetel": SP_Atadas_atvetel,
    "IT_Inventory": SP_IT_Inventory,
}


class SharePointIntegrationError(Exception):
    pass


def _validate_config(config):
    tenant_id = (config.get("tenant_id") or "").strip()
    client_id = (config.get("client_id") or "").strip()
    client_secret = (config.get("client_secret") or "").strip()
    site_url = (config.get("site_url") or "").strip()

    try:
        UUID(tenant_id)
        UUID(client_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise SharePointIntegrationError("Érvényes Tenant ID és Client ID szükséges.") from exc

    parsed = urlsplit(site_url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not hostname.endswith(".sharepoint.com") or not parsed.path.strip("/"):
        raise SharePointIntegrationError("HTTPS SharePoint site URL szükséges, például https://ceg.sharepoint.com/sites/IT.")
    if parsed.query or parsed.fragment or parsed.port:
        raise SharePointIntegrationError("A site URL ne tartalmazzon portot, query paramétert vagy fragmentet.")
    if not client_secret:
        raise SharePointIntegrationError("A Client Secret nincs beállítva.")

    site_path = parsed.path.rstrip("/")
    list_path_start = site_path.lower().find("/lists/")
    if list_path_start >= 0:
        site_path = site_path[:list_path_start]
    if not site_path.strip("/"):
        raise SharePointIntegrationError("A SharePoint webhely útvonala hiányzik a megadott URL-ből.")

    return tenant_id, client_id, client_secret, hostname, site_path


def _request_json(url, *, method="GET", headers=None, data=None):
    request = Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            error_data = json.loads(exc.read().decode("utf-8"))
            error_value = error_data.get("error", "")
            if isinstance(error_value, dict):
                message = error_value.get("message", "")
            else:
                message = error_data.get("error_description") or str(error_value)
        except (ValueError, UnicodeDecodeError):
            message = ""
        detail = f": {message[:300]}" if message else ""
        raise SharePointIntegrationError(f"Microsoft Graph HTTP {exc.code}{detail}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise SharePointIntegrationError(f"Nem sikerült elérni a Microsoft Graph szolgáltatást: {exc}") from exc


def _get_access_token(tenant_id, client_id, client_secret):
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    payload = urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }).encode("utf-8")
    result = _request_json(
        token_url,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=payload,
    )
    token = result.get("access_token")
    if not token:
        raise SharePointIntegrationError("A Microsoft identity platform nem adott hozzáférési tokent.")
    return token


def _graph_get(url, token):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "graph.microsoft.com":
        raise SharePointIntegrationError("Érvénytelen Microsoft Graph lapozó URL.")
    return _request_json(url, headers={"Authorization": f"Bearer {token}"})


def _get_site_context(config):
    tenant_id, client_id, client_secret, hostname, site_path = _validate_config(config)
    token = _get_access_token(tenant_id, client_id, client_secret)
    site_url = f"{GRAPH_ROOT}/sites/{hostname}:{quote(site_path, safe='/')}"
    site = _graph_get(site_url, token)
    return token, site


def _iter_site_lists(token, site_id):
    next_url = f"{GRAPH_ROOT}/sites/{site_id}/lists?{urlencode({'$top': 200})}"
    while next_url:
        page = _graph_get(next_url, token)
        yield from page.get("value", [])
        next_url = page.get("@odata.nextLink")


def _matches_sharepoint_list(item, list_name):
    item_name = (item.get("name") or "").casefold()
    display_name = (item.get("displayName") or "").casefold()
    normalized_name = list_name.casefold()
    return (
        item_name == normalized_name
        or display_name == normalized_name
        or (
            list_name == INVENTORY_LIST_URL_NAME
            and display_name == "tspc it inventory"
        )
    )


def list_sharepoint_lists(config):
    token, site = _get_site_context(config)
    lists = list(_iter_site_lists(token, site["id"]))
    return {
        "status": "SUCCESS",
        "site_name": site.get("displayName", ""),
        "lists": [
            {
                "name": item.get("name", ""),
                "display_name": item.get("displayName") or item.get("name") or "",
                "item_count": (item.get("list") or {}).get("itemCount"),
                "template": (item.get("list") or {}).get("template", ""),
                "import_supported": any(_matches_sharepoint_list(item, name) for name in SHAREPOINT_LIST_MODELS),
            }
            for item in lists
        ],
    }


def _resolve_inventory_list(config):
    token, site = _get_site_context(config)

    inventory_list = next(
        (
            item for item in _iter_site_lists(token, site["id"])
            if _matches_sharepoint_list(item, INVENTORY_LIST_URL_NAME)
        ),
        None,
    )

    if not inventory_list:
        raise SharePointIntegrationError("A(z) 'IT_Inventory' SharePoint-lista nem található a megadott site-on.")
    return token, site, inventory_list


def test_sharepoint_connection(config):
    _, site, inventory_list = _resolve_inventory_list(config)
    item_count = inventory_list.get("list", {}).get("itemCount", inventory_list.get("itemCount", "ismeretlen"))
    return {
        "status": "SUCCESS",
        "message": f"Kapcsolat sikeres. Lista: {inventory_list.get('displayName', INVENTORY_LIST_URL_NAME)}; elemek: {item_count}.",
        "site_name": site.get("displayName", ""),
        "list_name": inventory_list.get("displayName", INVENTORY_LIST_URL_NAME),
    }


def _get_sharepoint_items(token, site_id, list_id):
    query = urlencode({"$expand": "fields", "$top": 200})
    next_url = f"{GRAPH_ROOT}/sites/{site_id}/lists/{list_id}/items?{query}"
    items = []
    while next_url:
        page = _graph_get(next_url, token)
        items.extend(page.get("value", []))
        next_url = page.get("@odata.nextLink")
    return items


def _resolve_sharepoint_list(token, site, list_name):
    sharepoint_list = next(
        (
            item for item in _iter_site_lists(token, site["id"])
            if _matches_sharepoint_list(item, list_name)
        ),
        None,
    )
    if not sharepoint_list:
        raise SharePointIntegrationError(f"A(z) '{list_name}' SharePoint-lista nem található a megadott site-on.")
    return sharepoint_list


def _record_sharepoint_sync_failures(started_at, trigger_type, error_message, duration):
    with SessionLocal() as db:
        for list_name in SHAREPOINT_LIST_MODELS:
            db.add(SharePointSyncHistory(
                list_name=list_name,
                started_at=started_at,
                ended_at=datetime.now(timezone.utc),
                duration_seconds=duration,
                trigger_type=trigger_type,
                status="ERROR",
                items_count=0,
                error_message=error_message[:1000],
            ))
        db.commit()


def _changed_fields(previous, current):
    return sorted(
        key for key in set(previous or {}) | set(current or {})
        if (previous or {}).get(key) != (current or {}).get(key)
    )


def _change_record(list_name, item_id, change_type, changed_fields, previous_fields, current_fields, trigger_type):
    return SharePointItemChange(
        list_name=list_name,
        sharepoint_item_id=item_id,
        change_type=change_type,
        changed_fields=changed_fields,
        previous_fields=previous_fields,
        current_fields=current_fields,
        changed_at=datetime.now(timezone.utc),
        trigger_type=trigger_type,
    )


def sync_sharepoint_lists_to_database(config, trigger_type="MANUAL"):
    started_at = datetime.now(timezone.utc)
    started_clock = time.monotonic()
    try:
        token, site = _get_site_context(config)
        available_lists = list(_iter_site_lists(token, site["id"]))
        sharepoint_lists = {}
        for list_name in SHAREPOINT_LIST_MODELS:
            sharepoint_list = next(
                (item for item in available_lists if _matches_sharepoint_list(item, list_name)),
                None,
            )
            if sharepoint_list is None:
                raise SharePointIntegrationError(
                    f"A(z) '{list_name}' SharePoint-lista nem található a megadott site-on."
                )
            sharepoint_lists[list_name] = sharepoint_list

        downloaded = {
            list_name: [
                {
                    "sharepoint_item_id": str(item["id"]),
                    "fields": item.get("fields") or {},
                    "source_modified_at": (item.get("fields") or {}).get("Modified"),
                }
                for item in _get_sharepoint_items(token, site["id"], sharepoint_list["id"])
                if item.get("id") is not None
            ]
            for list_name, sharepoint_list in sharepoint_lists.items()
        }

        Base.metadata.create_all(
            bind=engine,
            tables=[
                *(model.__table__ for model in SHAREPOINT_LIST_MODELS.values()),
                SharePointSyncHistory.__table__,
                SharePointItemChange.__table__,
            ],
        )
        results = []
        with SessionLocal() as db:
            for list_name, model in SHAREPOINT_LIST_MODELS.items():
                rows = downloaded[list_name]
                existing = {
                    record.sharepoint_item_id: record
                    for record in db.query(model).all()
                }
                current_ids = set()
                added_count = updated_count = deleted_count = 0
                upsert_rows = []
                synced_at = datetime.now(timezone.utc)

                for row in rows:
                    item_id = row["sharepoint_item_id"]
                    current_ids.add(item_id)
                    fields = row["fields"]
                    previous_record = existing.get(item_id)
                    change_type = None
                    previous_fields = None
                    changed_fields = []
                    if previous_record is None:
                        change_type = "ADDED"
                        changed_fields = sorted(fields)
                        added_count += 1
                    elif previous_record.is_deleted:
                        change_type = "RESTORED"
                        previous_fields = previous_record.fields
                        changed_fields = _changed_fields(previous_fields, fields)
                        updated_count += 1
                    else:
                        previous_fields = previous_record.fields
                        changed_fields = _changed_fields(previous_fields, fields)
                        if changed_fields:
                            change_type = "UPDATED"
                            updated_count += 1

                    if change_type:
                        db.add(_change_record(
                            list_name, item_id, change_type, changed_fields,
                            previous_fields, fields, trigger_type,
                        ))
                    upsert_rows.append({
                        **row,
                        "synced_at": synced_at,
                        "is_deleted": False,
                    })

                for item_id, record in existing.items():
                    if item_id not in current_ids and not record.is_deleted:
                        record.is_deleted = True
                        deleted_count += 1
                        db.add(_change_record(
                            list_name,
                            item_id,
                            "DELETED",
                            [],
                            record.fields,
                            None,
                            trigger_type,
                        ))

                for offset in range(0, len(upsert_rows), 250):
                    batch = upsert_rows[offset:offset + 250]
                    statement = pg_insert(model).values(batch)
                    statement = statement.on_conflict_do_update(
                        index_elements=[model.sharepoint_item_id],
                        set_={
                            "fields": statement.excluded.fields,
                            "source_modified_at": statement.excluded.source_modified_at,
                            "synced_at": statement.excluded.synced_at,
                            "is_deleted": statement.excluded.is_deleted,
                        },
                    )
                    db.execute(statement)

                results.append({
                    "status": "SUCCESS",
                    "list_name": list_name,
                    "table_name": model.__tablename__,
                    "imported_count": len(rows),
                    "added_count": added_count,
                    "updated_count": updated_count,
                    "deleted_count": deleted_count,
                    "message": f"{len(rows)} elem szinkronizálva; új: {added_count}, módosult: {updated_count}, törölt: {deleted_count}.",
                })

            duration = round(time.monotonic() - started_clock, 2)
            for result in results:
                db.add(SharePointSyncHistory(
                    list_name=result["list_name"],
                    started_at=started_at,
                    ended_at=datetime.now(timezone.utc),
                    duration_seconds=duration,
                    trigger_type=trigger_type,
                    status="SUCCESS",
                    items_count=result["imported_count"],
                    added_count=result["added_count"],
                    updated_count=result["updated_count"],
                    deleted_count=result["deleted_count"],
                ))
            db.commit()

        total_items = sum(result["imported_count"] for result in results)
        total_changes = sum(
            result["added_count"] + result["updated_count"] + result["deleted_count"]
            for result in results
        )
        return {
            "status": "SUCCESS",
            "message": (
                f"{len(results)} SharePoint-lista, {total_items} elem szinkronizálva; "
                f"{total_changes} változás rögzítve."
            ),
            "imported_count": total_items,
            "site_name": site.get("displayName", ""),
            "duration_seconds": duration,
            "results": results,
        }
    except Exception as exc:
        duration = round(time.monotonic() - started_clock, 2)
        _record_sharepoint_sync_failures(started_at, trigger_type, str(exc), duration)
        raise


def sync_inventory_to_database(config):
    return sync_sharepoint_lists_to_database(config)


def sync_sharepoint_list_to_database(config, list_name, trigger_type="MANUAL"):
    if list_name not in SHAREPOINT_LIST_MODELS:
        raise SharePointIntegrationError(f"A(z) '{list_name}' lista letöltése nincs engedélyezve.")
    return sync_sharepoint_lists_to_database(config, trigger_type)