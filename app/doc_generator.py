import os
import ast
import json
import urllib.request
from datetime import datetime, timezone
from sqlalchemy import inspect
from sqlalchemy.schema import CreateTable
from sqlalchemy.inspection import inspect as sa_inspect
from database import engine
import models
from config_manager import get_setting

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))
DOCS_DIR = os.path.join(PROJECT_DIR, "docs")
B3 = chr(96) * 3

def ensure_docs_dir():
    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(os.path.join(APP_DIR, "docs"), exist_ok=True)

def inspect_database_schema():
    inspector = inspect(engine)
    schema_info = {}
    for table_name in inspector.get_table_names():
        columns = []
        for col in inspector.get_columns(table_name):
            columns.append({
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col.get("nullable", True)
            })
        pks = inspector.get_pk_constraint(table_name).get("constrained_columns", [])
        fks = [
            f"{fk.get('constrained_columns')} -> {fk.get('referred_table')}.{fk.get('referred_columns')}"
            for fk in inspector.get_foreign_keys(table_name)
        ]
        schema_info[table_name] = {
            "columns": columns,
            "primary_keys": pks,
            "foreign_keys": fks
        }
    return schema_info

def inspect_sqlalchemy_relationships():
    rel_info = {}
    model_classes = [models.ADUser, models.ADGroup, models.ADAuditLog, models.SyncHistory, models.SystemSetting]
    for cls in model_classes:
        try:
            mapper = sa_inspect(cls)
            rels = {}
            for rel in mapper.relationships:
                secondary_table = rel.secondary.name if rel.secondary is not None else None
                rels[rel.key] = {
                    "target_entity": rel.target.name,
                    "direction": rel.direction.name,
                    "secondary_table": secondary_table,
                    "cascade": str(rel.cascade)
                }
            if rels:
                rel_info[cls.__name__] = rels
        except Exception as e:
            rel_info[cls.__name__] = f"Hiba: {str(e)}"
    return rel_info

def inspect_codebase():
    code_map = {}
    for root, _, files in os.walk(APP_DIR):
        if any(ignored in root for ignored in ["__pycache__", "backups", "docs", "csv_imports"]):
            continue
        for f in files:
            if f.endswith(".py"):
                fpath = os.path.join(root, f)
                rel_path = os.path.relpath(fpath, PROJECT_DIR)
                try:
                    with open(fpath, "r", encoding="utf-8") as fp:
                        tree = ast.parse(fp.read(), filename=f)
                    classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
                    functions = []
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            decors = []
                            for d in node.decorator_list:
                                if isinstance(d, ast.Name):
                                    decors.append(f"@{d.id}")
                                elif isinstance(d, ast.Call):
                                    if hasattr(d.func, "id"):
                                        decors.append(f"@{d.func.id}")
                                    elif hasattr(d.func, "attr"):
                                        prefix = d.func.value.id if hasattr(d.func, "value") and hasattr(d.func.value, "id") else ""
                                        decors.append(f"@{prefix}.{d.func.attr}" if prefix else f"@{d.func.attr}")
                                elif isinstance(d, ast.Attribute):
                                    prefix = d.value.id if hasattr(d, "value") and hasattr(d.value, "id") else ""
                                    decors.append(f"@{prefix}.{d.attr}" if prefix else f"@{d.attr}")
                            functions.append({
                                "name": node.name,
                                "decorators": decors
                            })
                    code_map[rel_path] = {
                        "classes": classes,
                        "functions": functions
                    }
                except Exception as err:
                    code_map[rel_path] = {"error": str(err)}
    return code_map

def inspect_ldap_attributes():
    user_attrs = []
    group_attrs = []
    sync_engine_path = os.path.join(APP_DIR, "sync_engine.py")
    if os.path.isfile(sync_engine_path):
        try:
            with open(sync_engine_path, "r", encoding="utf-8") as fp:
                tree = ast.parse(fp.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if target.id == "user_attrs" and isinstance(node.value, ast.List):
                                user_attrs = [elt.value for elt in node.value.elts if hasattr(elt, "value")]
                            elif target.id == "group_attrs" and isinstance(node.value, ast.List):
                                group_attrs = [elt.value for elt in node.value.elts if hasattr(elt, "value")]
        except Exception:
            pass
    return {
        "user_attributes": user_attrs,
        "group_attributes": group_attrs
    }

def inspect_fastapi_and_scheduler():
    routes_info = []
    openapi_spec = {}
    scheduler_jobs = []
    try:
        import sys
        main_mod = sys.modules.get("main") or sys.modules.get("app.main")
        if not main_mod:
            try:
                import main as main_mod
            except Exception:
                pass
        if main_mod:
            if hasattr(main_mod, "app"):
                try:
                    openapi_spec = main_mod.app.openapi()
                except Exception:
                    pass
                for route in main_mod.app.routes:
                    methods = list(getattr(route, "methods", []))
                    if methods:
                        routes_info.append({
                            "path": getattr(route, "path", ""),
                            "name": getattr(route, "name", ""),
                            "methods": methods
                        })
            if hasattr(main_mod, "scheduler"):
                for job in main_mod.scheduler.get_jobs():
                    scheduler_jobs.append({
                        "id": job.id,
                        "name": job.name,
                        "trigger": str(job.trigger),
                        "next_run_time": str(job.next_run_time) if hasattr(job, "next_run_time") else "-"
                    })
    except Exception as e:
        routes_info.append({"error": str(e)})
    return routes_info, openapi_spec, scheduler_jobs

def inspect_environment_and_settings(db):
    settings_records = db.query(models.SystemSetting).all()
    app_settings = {
        s.setting_key: {
            "value": s.setting_value if not any(k in s.setting_key.upper() for k in ["PASS", "TOKEN", "SECRET"]) else "***",
            "desc": s.description
        } for s in settings_records
    }
    env_keys = sorted(list(os.environ.keys()))
    return {
        "database_app_settings": app_settings,
        "active_env_variables": env_keys
    }

def generate_live_requirements():
    modules = set()
    standard_libs = {
        "os", "sys", "json", "time", "datetime", "re", "ast", "uuid", "shutil",
        "urllib", "threading", "zipfile", "csv", "contextlib", "typing", "base64"
    }
    for root, _, files in os.walk(APP_DIR):
        for f in files:
            if f.endswith(".py"):
                try:
                    with open(os.path.join(root, f), "r", encoding="utf-8") as fp:
                        tree = ast.parse(fp.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for n in node.names:
                                base_mod = n.name.split(".")[0]
                                if base_mod not in standard_libs:
                                    modules.add(base_mod)
                        elif isinstance(node, ast.ImportFrom) and node.module:
                            base_mod = node.module.split(".")[0]
                            if base_mod not in standard_libs:
                                modules.add(base_mod)
                except Exception:
                    pass

    package_map = {
        "fastapi": "fastapi>=0.110.0",
        "uvicorn": "uvicorn>=0.28.0",
        "sqlalchemy": "sqlalchemy>=2.0.28",
        "psycopg2": "psycopg2-binary>=2.9.9",
        "ldap3": "ldap3>=2.9.1",
        "apscheduler": "apscheduler>=3.10.4",
        "multipart": "python-multipart>=0.0.9",
        "requests": "requests>=2.31.0"
    }

    internal_mods = {
        "database", "models", "config_manager", "ldap_client", "auth",
        "sync_engine", "history_importer", "github_sync", "backup_manager",
        "ai_assistant", "doc_generator"
    }

    req_lines = []
    for mod in sorted(modules):
        if mod in package_map:
            req_lines.append(package_map[mod])
        elif mod not in internal_mods:
            req_lines.append(mod)

    for p in ["fastapi>=0.110.0", "uvicorn>=0.28.0", "sqlalchemy>=2.0.28", "psycopg2-binary>=2.9.9", "ldap3>=2.9.1", "apscheduler>=3.10.4", "python-multipart>=0.0.9"]:
        if p not in req_lines:
            req_lines.append(p)

    req_content = "\n".join(sorted(list(set(req_lines)))) + "\n"
    with open(os.path.join(PROJECT_DIR, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write(req_content)
    with open(os.path.join(APP_DIR, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write(req_content)
    return req_content

def build_all_docs(db):
    ensure_docs_dir()
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    app_ver = str(get_setting(db, "APP_VERSION", "1.00")).replace("v", "").strip()

    live_reqs = generate_live_requirements()

    ddl_statements = [
        f"-- AD TRACKER - ÉLŐ POSTGRESQL DDL ADATBÁZIS SÉMA",
        f"-- Generálva: {now_utc} | Verzió: v{app_ver}\n"
    ]
    for table in models.Base.metadata.sorted_tables:
        ddl_statements.append(str(CreateTable(table).compile(engine)).strip() + ";\n")
    live_sql_ddl = "\n".join(ddl_statements)

    db_schema = inspect_database_schema()
    relationships = inspect_sqlalchemy_relationships()
    code_map = inspect_codebase()
    ldap_attrs = inspect_ldap_attributes()
    routes_info, openapi_spec, scheduler_jobs = inspect_fastapi_and_scheduler()
    env_info = inspect_environment_and_settings(db)

    # MASTER REBUILDER PROMPT összeállítása
    rebuilder_lines = [
        f"# MASTER SYSTEM REBUILDER BLUEPRINT & PROMPT",
        f"# Generálva az élő rendszerből: {now_utc} | Verzió: v{app_ver}",
        "",
        "---",
        "[DIRECTIVE FOR AI SYSTEM ARCHITECT]",
        "Reconstruct the complete, production-grade AD Tracker application using the live technical specifications below.",
        "Generate every component (endpoints, database models, background scheduler, LDAP sync logic, and environment configurations) matching these exact contracts.",
        "---",
        "",
        "## 1. REQUIREMENTS ÉS CSOMAGVERZIÓK",
        f"{B3}text",
        live_reqs.strip(),
        f"{B3}",
        "",
        "## 2. FASTAPI VÉGPONTOK (ROUTES) ÉS DECORATOROK",
        f"{B3}json",
        json.dumps(routes_info, indent=2, ensure_ascii=False),
        f"{B3}",
        "",
        "## 3. FORRÁSKÓD FÜGGVÉNYEK ÉS DEKORÁTOROK (AST INTROSPEKCIÓ)",
        f"{B3}json",
        json.dumps(code_map, indent=2, ensure_ascii=False),
        f"{B3}",
        "",
        "## 4. SQLALCHEMY RELATIONSHIP-EK ÉS MODELL RELÁCIÓK",
        f"{B3}json",
        json.dumps(relationships, indent=2, ensure_ascii=False),
        f"{B3}",
        "",
        "## 5. ACTIVE DIRECTORY / LDAP LEKÉRT ATTRIBUTELISTÁK",
        f"{B3}json",
        json.dumps(ldap_attrs, indent=2, ensure_ascii=False),
        f"{B3}",
        "",
        "## 6. APSCHEDULER ÜTEMEZETT HÁTTÉRFOLYAMATOK",
        f"{B3}json",
        json.dumps(scheduler_jobs, indent=2, ensure_ascii=False),
        f"{B3}",
        "",
        "## 7. RENDSZER- ÉS KÖRNYEZETI BEÁLLÍTÁSOK (ENV & CONFIG)",
        f"{B3}json",
        json.dumps(env_info, indent=2, ensure_ascii=False),
        f"{B3}",
        "",
        "## 8. POSTGRESQL DDL ADATBÁZIS SÉMA",
        f"{B3}sql",
        live_sql_ddl.strip(),
        f"{B3}"
    ]
    rebuild_prompt = "\n".join(rebuilder_lines)

    inspection_dump = json.dumps({
        "schema": db_schema,
        "relationships": relationships,
        "codebase": code_map,
        "ldap_attributes": ldap_attrs,
        "routes": routes_info,
        "scheduler": scheduler_jobs,
        "environment": env_info
    }, indent=2, ensure_ascii=False)

    files = {
        "database_schema.sql": live_sql_ddl,
        "SYSTEM_REBUILD_PROMPT.md": rebuild_prompt,
        "openapi.json": json.dumps(openapi_spec, indent=2, ensure_ascii=False) if openapi_spec else "{}",
        "SYSTEM_INTROSPECTION.json": inspection_dump
    }

    for folder in [DOCS_DIR, os.path.join(APP_DIR, "docs")]:
        for fname, content in files.items():
            with open(os.path.join(folder, fname), "w", encoding="utf-8") as f:
                f.write(content)

    return list(files.keys())
