import hashlib
import logging
import mimetypes
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import unquote, urljoin, urlsplit

import requests
from requests_ntlm import HttpNtlmAuth
from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError

from database import SessionLocal
from models import (
    SP_eszkozleltar_nonIT,
    SharePointImageSyncHistory,
    SharePointImageVersion,
)

logger = logging.getLogger(__name__)
IMAGE_SYNC_LOCK = threading.Lock()

ALLOWED_HOST = "project.tspc.hu"
ALLOWED_PATH_PREFIX = "/it/leltar/"
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_SYNC_BYTES = 2 * 1024 * 1024 * 1024
MAX_IMAGE_URLS = 3000
REQUEST_TIMEOUT = (10, 45)
MAX_REDIRECTS = 3
SUPPORTED_IMAGES = {
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "image/gif": (b"GIF8", ".gif"),
    "image/webp": (b"RIFF", ".webp"),
}
URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


class ImageSyncError(Exception):
    pass


class ImageAuthenticationError(ImageSyncError):
    pass


def _safe_source_url(candidate):
    try:
        parsed = urlsplit(candidate)
        if (
            len(candidate) > 2048
            or parsed.scheme.casefold() != "https"
            or (parsed.hostname or "").casefold() != ALLOWED_HOST
            or parsed.port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or not parsed.path.casefold().startswith(ALLOWED_PATH_PREFIX)
        ):
            return None
    except ValueError:
        return None
    return candidate


def _extract_image_urls(value):
    if not isinstance(value, str):
        return [], 0
    urls = []
    skipped = 0
    for candidate in URL_PATTERN.findall(value):
        candidate = candidate.rstrip(".,;:!?)\\]}").replace("&amp;", "&")
        safe_url = _safe_source_url(candidate)
        if safe_url and safe_url not in urls:
            urls.append(safe_url)
        elif not safe_url:
            skipped += 1
    return urls, skipped


def _download_image(url, username, password):
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        safe_url = _safe_source_url(current_url)
        if safe_url is None:
            raise ImageSyncError("A képlink vagy az átirányítás nem engedélyezett címre mutat.")

        with requests.get(
            safe_url,
            auth=HttpNtlmAuth(username, password),
            timeout=REQUEST_TIMEOUT,
            allow_redirects=False,
            stream=True,
        ) as response:
            if response.status_code in (401, 403):
                raise ImageAuthenticationError("A SharePoint hitelesítés sikertelen.")
            if response.is_redirect:
                location = response.headers.get("Location")
                if not location:
                    raise ImageSyncError("A képforrás hiányos átirányítást adott.")
                current_url = urljoin(safe_url, location)
                continue
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            image_data = bytearray()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                image_data.extend(chunk)
                if len(image_data) > MAX_IMAGE_BYTES:
                    raise ImageSyncError("A kép túllépi a 15 MB-os méretkorlátot.")

            data = bytes(image_data)
            image_format = next(
                (
                    (mime_type, extension)
                    for mime_type, (signature, extension) in SUPPORTED_IMAGES.items()
                    if data.startswith(signature)
                ),
                None,
            )
            if (
                image_format is None
                or content_type not in (*SUPPORTED_IMAGES, "image/pjpeg", "application/octet-stream")
            ):
                raise ImageSyncError("A letöltött fájl nem támogatott képformátum.")
            actual_type, extension = image_format
            if (
                (
                    content_type != "application/octet-stream"
                    and content_type != actual_type
                    and not (content_type == "image/pjpeg" and actual_type == "image/jpeg")
                )
                or (actual_type == "image/webp" and data[8:12] != b"WEBP")
            ):
                raise ImageSyncError("A kép MIME-típusa és fájltartalma nem egyezik.")
            file_name = unquote(urlsplit(safe_url).path.rsplit("/", 1)[-1])
            file_name = re.sub(r"[^A-Za-z0-9._-]", "_", file_name)[:255].strip("._")
            if not file_name:
                file_name = "sharepoint-image" + extension
            elif not mimetypes.guess_type(file_name)[0] == actual_type:
                file_name = file_name.rsplit(".", 1)[0] + extension
            return data, actual_type, file_name

    raise ImageSyncError("A képforrás túl sok átirányítást adott.")


def _record_result(history_id, **values):
    with SessionLocal() as db:
        history = db.query(SharePointImageSyncHistory).filter_by(id=history_id).one()
        for key, value in values.items():
            setattr(history, key, value)
        db.commit()


def _run_sharepoint_image_sync(username, password):
    if not username or not password:
        raise ImageSyncError("Felhasználónév és jelszó megadása szükséges.")
    if len(username) > 256 or len(password) > 1024:
        raise ImageSyncError("A megadott hitelesítési adat túl hosszú.")

    started = time.monotonic()
    with SessionLocal() as db:
        history = SharePointImageSyncHistory(status="FOLYAMATBAN")
        db.add(history)
        db.commit()
        history_id = history.id
        records = db.query(
            SP_eszkozleltar_nonIT.sharepoint_item_id,
            SP_eszkozleltar_nonIT.fields,
        ).filter(SP_eszkozleltar_nonIT.is_deleted.is_(False)).all()

    targets = []
    skipped_count = 0
    for item_id, fields in records:
        urls, skipped = _extract_image_urls((fields or {}).get("field_2"))
        targets.extend((item_id, url) for url in urls)
        skipped_count += skipped
    if len(targets) > MAX_IMAGE_URLS:
        error = "A képlinkek száma túllépi az egy futásban engedélyezett korlátot."
        _record_result(
            history_id,
            ended_at=datetime.now(timezone.utc),
            duration_seconds=round(time.monotonic() - started, 2),
            status="HIBA",
            links_count=len(targets),
            error_message=error,
        )
        raise ImageSyncError(error)

    counts = {"new_versions_count": 0, "unchanged_count": 0, "failed_count": 0}
    first_error = None
    auth_error = None
    processing_error = None
    total_downloaded_bytes = 0
    size_limit_reached = False
    executor = ThreadPoolExecutor(max_workers=8)
    try:
        for batch_start in range(0, len(targets), 8):
            batch = targets[batch_start:batch_start + 8]
            futures = {
                executor.submit(_download_image, url, username, password): (item_id, url)
                for item_id, url in batch
            }
            for future in as_completed(futures):
                item_id, url = futures[future]
                try:
                    image_data, content_type, file_name = future.result()
                except ImageAuthenticationError as exc:
                    auth_error = exc
                    for pending in futures:
                        pending.cancel()
                    break
                except (requests.RequestException, ImageSyncError) as exc:
                    counts["failed_count"] += 1
                    message = (
                        str(exc)
                        if isinstance(exc, ImageSyncError)
                        else "Hálózati vagy HTTP-hiba történt egy kép letöltésekor."
                    )
                    first_error = first_error or message
                    continue

                if total_downloaded_bytes + len(image_data) > MAX_SYNC_BYTES:
                    counts["failed_count"] += 1
                    first_error = "A futás elérte a 2 GB-os összesített letöltési korlátot."
                    size_limit_reached = True
                    for pending in futures:
                        pending.cancel()
                    break
                total_downloaded_bytes += len(image_data)
                content_hash = hashlib.sha256(image_data).hexdigest()
                with SessionLocal() as db:
                    source_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
                    latest = (
                        db.query(SharePointImageVersion)
                        .filter_by(
                            sharepoint_item_id=item_id,
                            source_url_sha256=source_hash,
                        )
                        .order_by(desc(SharePointImageVersion.version_number))
                        .first()
                    )
                    now = datetime.now(timezone.utc)
                    if latest and latest.content_sha256 == content_hash:
                        latest.last_verified_at = now
                        result_key = "unchanged_count"
                    else:
                        db.add(
                            SharePointImageVersion(
                                sharepoint_item_id=item_id,
                                source_url=url,
                                source_url_sha256=source_hash,
                                version_number=(latest.version_number + 1) if latest else 1,
                                content_sha256=content_hash,
                                file_name=file_name,
                                content_type=content_type,
                                file_size_bytes=len(image_data),
                                image_data=image_data,
                                downloaded_at=now,
                                last_verified_at=now,
                                trigger_type="MANUAL",
                            )
                        )
                        result_key = "new_versions_count"
                    db.commit()
                    counts[result_key] += 1
            if auth_error or size_limit_reached:
                break
    except SQLAlchemyError:
        logger.exception("SharePoint-képszinkron adatbázishiba")
        first_error = first_error or "Belső hiba a képszinkron feldolgozása közben."
        counts["failed_count"] += 1
        processing_error = True
    finally:
        executor.shutdown(wait=True, cancel_futures=True)

    if auth_error or processing_error:
        error_message = (
            str(auth_error)
            if isinstance(auth_error, ImageAuthenticationError)
            else first_error or "A képszinkron feldolgozása megszakadt."
        )
        counts["failed_count"] += max(0, len(targets) - sum(counts.values()))
    else:
        error_message = first_error

    status = "HIBA" if auth_error else ("RÉSZLEGES" if counts["failed_count"] else "SIKERES")
    _record_result(
        history_id,
        ended_at=datetime.now(timezone.utc),
        duration_seconds=round(time.monotonic() - started, 2),
        status=status,
        links_count=len(targets),
        skipped_count=skipped_count,
        error_message=error_message,
        **counts,
    )
    if auth_error:
        raise ImageAuthenticationError(error_message)
    if processing_error:
        raise ImageSyncError(error_message)
    return {
        "status": status,
        "links_count": len(targets),
        **counts,
        "error_message": error_message,
    }


def sync_sharepoint_images(username, password):
    if not IMAGE_SYNC_LOCK.acquire(blocking=False):
        raise ImageSyncError("Már folyamatban van egy SharePoint-képszinkron.")
    try:
        return _run_sharepoint_image_sync(username, password)
    finally:
        IMAGE_SYNC_LOCK.release()
