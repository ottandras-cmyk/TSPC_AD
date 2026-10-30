#!/usr/bin/env python3
import os
import sys
import json
from datetime import datetime, timezone

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(CURRENT_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from database import engine, Base, SessionLocal
import models
from factory import create_app
from doc_generator import build_all_docs

def generate_ddl_schema():
    """Tiszta DDL séma exportálása közvetlenül a deklaratív modellekből."""
    schema_path = os.path.join(APP_DIR, "db_dump", "schema.sql")
    os.makedirs(os.path.dirname(schema_path), exist_ok=True)
    
    lines = [
        "-- ========================================================",
        "-- AD TRACKER AUTO-GENERATED DATABASE SCHEMA (SSOT)",
        f"-- Generálva SQLAlchemy ORM alapján: {datetime.now(timezone.utc).isoformat()}",
        "-- ========================================================\n"
    ]
    
    from sqlalchemy.schema import CreateTable
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(engine)).strip()
        lines.append(f"{ddl};\n")
        
    with open(schema_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"✅ DDL séma sikeresen generálva: {schema_path}")

def generate_openapi():
    """OpenAPI 3.1 JSON exportálása a FastAPI alkalmazásból."""
    app_instance = create_app()
    openapi_schema = app_instance.openapi()
    openapi_path = os.path.join(APP_DIR, "docs", "openapi.json")
    os.makedirs(os.path.dirname(openapi_path), exist_ok=True)
    
    with open(openapi_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)
    print(f"✅ OpenAPI JSON specifikáció sikeresen generálva: {openapi_path}")

def generate_docs():
    """Dokumentációk automatikus újraépítése."""
    db = SessionLocal()
    try:
        res = build_all_docs(db)
        print(f"✅ Markdown dokumentációk újraépítve: {len(res.get('generated_files', []))} db fájl.")
    finally:
        db.close()

if __name__ == "__main__":
    print(">>> Artefaktumok generálása az ORM Single Source of Truth alapján...")
    generate_ddl_schema()
    generate_openapi()
    generate_docs()
    print(">>> Minden artefaktum szinkronba hozva.")
