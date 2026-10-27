#!/bin/bash
set -e

echo "========================================================"
echo "⏪ AZONNALI VISSZAÁLLÍTÁS (ROLLBACK)"
echo "========================================================"

# Megnézzük, kér-e konkrét taget vagy az utolsó előtti commitra ugrik vissza
TARGET_COMMIT="${1:-HEAD~1}"

echo "Visszaállás ide: ${TARGET_COMMIT}..."
git checkout "${TARGET_COMMIT}" -- app/ static/ templates/

# Szinkronizálás a futó konténerrel
docker cp app/static ad_sync_app:/app/ 2>/dev/null || docker cp static ad_sync_app:/app/ 2>/dev/null || true
docker cp app/templates ad_sync_app:/app/ 2>/dev/null || docker cp templates ad_sync_app:/app/ 2>/dev/null || true
docker cp app/routers ad_sync_app:/app/ 2>/dev/null || docker cp routers ad_sync_app:/app/ 2>/dev/null || true

docker compose restart

echo "========================================================"
echo "✅ SIKERES VISSZAÁLLÁS! A rendszer az előző működő verzióra állt."
echo "========================================================"
