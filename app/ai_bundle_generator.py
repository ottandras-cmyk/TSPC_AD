#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Codebase Bundle Generator for AD Tracker & Rendszerközpont
2 fájlt generál a docs/ mappába:
  1. AI_SYSTEM_CODEBASE_BUNDLE.md        -> Teljes eredeti forráskód
  2. AI_SYSTEM_CODEBASE_BUNDLE_masked.md -> API kulcsok és jelszavak csillaggal (*) maszkolva
"""

import os
import re
from pathlib import Path
from datetime import datetime, timezone

TARGET_EXTENSIONS = {'.py', '.html', '.css', '.js', '.json', '.md', '.txt', '.sql'}

EXCLUDE_DIRS = {
    '.git', '.git_backup', '.git_corrupted', '__pycache__', '.venv', 'venv', 'env',
    'backups', 'backup', 'dist', 'build', 'node_modules', '.idea', '.vscode'
}

EXCLUDE_FILES = {
    'telegram_history.json', 'git_log.json', 'package-lock.json',
    'AI_SYSTEM_CODEBASE_BUNDLE.md', 'AI_SYSTEM_CODEBASE_BUNDLE_masked.md'
}

COMPONENT_ROLES = {
    'main.py': ('Alkalmazás belépési pont', 'FastAPI app inicializálása, middleware-ek, routerek csatolása, lifecycle események.'),
    'database.py': ('Adatbázis kapcsolat & Session', 'SQLAlchemy adatbázis motor, kapcsolatkezelés, SessionLocal provider.'),
    'models.py': ('ORM Adatmodellek', 'PostgreSQL táblák leképezése (ADUser, ADGroup, EPHelpdeskTicket, EPTask stb.) relációkkal.'),
    'auth.py': ('Hitelesítés & Biztonság', 'Munkamenet-kezelés, LDAP hitelesítés, session token ellenőrzés (HMAC).'),
    'sync_engine.py': ('AD Szinkronizációs Motor', 'Élő Active Directory LDAP szinkronizáció, felhasználók és csoportok letöltése.'),
    'ldap_client.py': ('LDAP Kliens réteg', 'Alacsony szintű LDAP lekérdezések, Active Directory kapcsolódás és attribútum-olvasás.'),
    'easy_project_sync.py': ('Easy Project Szinkronizáció', 'Easy Project REST API szinkronizáció feladatokhoz és hibajegyekhez.'),
    'ad_analytics.py': ('AD Változáskövető Analitika', 'Jogosultságváltozások, csoporttagságok és biztonsági anomáliák elemzése.'),
    'telemetry.py': ('Rendszer Telemetria', 'Szervererőforrások (CPU, RAM, Diszk, GPU) és AI token statisztikák gyűjtése.'),
    'backup_manager.py': ('Mentéskezelő alrendszer', 'Helyi és távoli biztonsági mentések generálása, tömörítése és helyreállítása.'),
    'config_manager.py': ('Konfigurációkezelő', 'app_settings tábla és settings.json beállításainak lekérése és mentése.'),
    'ai_assistant.py': ('Helyi AI / Ollama Integráció', 'Ollama API hívások, helyi modellek kezelése és adatelemzés.'),
    'index.html': ('Fő felhasználói felület', 'Single-page webes alkalmazás váz, navigációs fülek, modális ablakok.'),
    'ui-core.js': ('Kliensoldali vezérlő logika', 'Frontend állapotkezelés, táblázatok szűrése, rendezése, lapozása, modálok.')
}

def get_file_role(rel_path: str) -> tuple[str, str]:
    fname = os.path.basename(rel_path)
    if fname in COMPONENT_ROLES:
        return COMPONENT_ROLES[fname]
    
    parts = rel_path.split(os.sep)
    if 'routers' in parts:
        return ('Backend API Router', f'API végpontok definíciója a(z) {fname.replace(".py", "")} modulhoz.')
    if 'templates' in parts:
        return ('Frontend UI Sablon', f'Felületi komponens vagy résznézet sablonja ({fname}).')
    if 'static' in parts:
        if fname.endswith('.js'): return ('Frontend JavaScript', f'Kliensoldali interakciók és segédfüggvények ({fname}).')
        if fname.endswith('.css'): return ('Felületi Stíluslap', f'CSS stílusdefiníciók ({fname}).')
    if 'docs' in parts or rel_path.endswith('.md'):
        return ('Rendszerdokumentáció', f'Architektúra, séma vagy fejlesztői útmutató ({fname}).')
    if fname.endswith('.json'):
        return ('Konfiguráció / Adatállomány', f'Strukturált JSON beállítás vagy adatminta ({fname}).')
    if fname.endswith('.sql'):
        return ('Adatbázis Séma / DDL', f'PostgreSQL adatbázis tábladefiníciók és indexek ({fname}).')

    return ('Forrásfájl', f'Általános forráskód vagy kiegészítő modul ({fname}).')

def mask_authentication_secrets(content: str) -> str:
    """Minden autentikációs jelszót, tokent és API kulcsot csillagokkal (*) maszkol."""
    
    # 1. Kulcs-érték jellegű titkok (password = "...", "api_key": "..." stb.)
    def replace_kw(m):
        prefix = m.group(1)
        val = m.group(2)
        quote = m.group(3)
        return f"{prefix}{'*' * max(8, len(val))}{quote}"

    pat_kw = re.compile(
        r'([\"\']?(?:password|passwd|api_key|secret|token|bind_pw|auth_token|tg_bot_token|app_secret|secret_key)[\"\']?\s*[:=]\s*[\"\'])([^\"\'\r\n]+)([\"\'])',
        re.IGNORECASE
    )
    content = pat_kw.sub(replace_kw, content)

    # 2. URL-ben lévő jelszavak (pl. postgresql://user:password@host)
    def replace_url(m):
        return m.group(1) + ("*" * max(8, len(m.group(2)))) + m.group(3)
    
    pat_url = re.compile(r'(://[^:\s/]+:)([^@\s/]+)(@)')
    content = pat_url.sub(replace_url, content)

    # 3. Telegram bot tokenek (bot123456:ABC-DEF...)
    def replace_tg(m):
        return m.group(1) + ("*" * len(m.group(2)))
    pat_tg = re.compile(r'(bot\d+:)([\w-]{15,})', re.IGNORECASE)
    content = pat_tg.sub(replace_tg, content)

    # 4. Bearer / Token fejlécek
    def replace_bearer(m):
        return m.group(1) + ("*" * len(m.group(2)))
    pat_bearer = re.compile(r'((?:Bearer|Token)\s+)([a-zA-Z0-9_\-\.]{15,})', re.IGNORECASE)
    content = pat_bearer.sub(replace_bearer, content)

    return content

def build_tree(root_dir: str) -> str:
    tree_lines = []
    root_path = Path(root_dir)
    
    def walk(directory: Path, prefix: str = ''):
        entries = sorted([e for e in directory.iterdir() if e.name not in EXCLUDE_DIRS], key=lambda x: (not x.is_dir(), x.name.lower()))
        entries = [e for e in entries if not (e.is_file() and (e.suffix.lower() not in TARGET_EXTENSIONS or e.name in EXCLUDE_FILES))]
        count = len(entries)
        for i, entry in enumerate(entries):
            connector = '└── ' if i == count - 1 else '├── '
            tree_lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
            if entry.is_dir():
                extension = '    ' if i == count - 1 else '│   '
                walk(entry, prefix + extension)

    tree_lines.append(f"{root_path.name}/")
    walk(root_path)
    return '\n'.join(tree_lines)

def generate_both_ai_bundles(project_root: str):
    root = Path(project_root).resolve()
    docs_dir = root / 'app' / 'docs' if (root / 'app' / 'docs').exists() else root / 'docs'
    docs_dir.mkdir(parents=True, exist_ok=True)

    raw_path = docs_dir / 'AI_SYSTEM_CODEBASE_BUNDLE.md'
    masked_path = docs_dir / 'AI_SYSTEM_CODEBASE_BUNDLE_masked.md'

    tree_str = build_tree(str(root))
    
    files_to_bundle = []
    ext_counts = {}

    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for f in sorted(filenames):
            if f in EXCLUDE_FILES: continue
            ext = os.path.splitext(f)[1].lower()
            if ext in TARGET_EXTENSIONS:
                fpath = Path(dirpath) / f
                try:
                    rel = fpath.relative_to(root)
                    size = fpath.stat().st_size
                    if size > 1_500_000: continue
                    files_to_bundle.append((str(rel), fpath))
                    ext_counts[ext] = ext_counts.get(ext, 0) + 1
                except Exception:
                    pass

    files_to_bundle.sort(key=lambda x: x[0].lower())
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    for is_masked, out_file in [(False, raw_path), (True, masked_path)]:
        doc = []
        variant_desc = "MASZKOLT VÁLTOZAT (Autentikációs jelszavak és API kulcsok csillaggal kitakarva)" if is_masked else "TELJES EREDETI VÁLTOZAT"
        
        doc.append(f"# AD Tracker & Rendszerközpont - Kódbázis Dosszié ({variant_desc})")
        doc.append(f"> **Generálva:** {now_utc} | **Projekt gyökér:** `{root.name}`")
        if is_masked:
            doc.append(f"> 🔒 **BIZTONSÁGI MEGJEGYZÉS:** Ebben a fájlban minden API kulcs, jelszó és token felül lett maszkolva `*` karakterekkel. Biztonságosan megosztható bármely külső AI szolgáltatóval.")
        else:
            doc.append(f"> ⚠️ **BIZALMAS:** Ez a fájl az eredeti forráskódot tartalmazza maszkolás nélkül (belső és helyi AI használatra).")
        doc.append("")
        doc.append("## 1. Rendszer- és Kódbázis Statisztika")
        doc.append(f"- **Összes feldolgozott fájl:** {len(files_to_bundle)} db")
        ext_summary = ", ".join([f"`{k}`: {v} db" for k, v in sorted(ext_counts.items(), key=lambda x: -x[1])])
        doc.append(f"- **Fájltípusok megoszlása:** {ext_summary}")
        doc.append("")
        doc.append("## 2. Vizuális Könyvtárstruktúra")
        doc.append("```text")
        doc.append(tree_str)
        doc.append("```")
        doc.append("")
        doc.append("## 3. Részletes Forráskód és Komponensek")
        doc.append("Minden fájl előtt és után pontos AI-metainformáció szerepel a fájl feladatáról és architektúrális helyéről.")
        doc.append("")

        for idx, (rel_path, abs_path) in enumerate(files_to_bundle, 1):
            role_title, role_desc = get_file_role(rel_path)
            ext = os.path.splitext(rel_path)[1].lower()
            fence_lang = {
                '.py': 'python', '.html': 'html', '.css': 'css', '.js': 'javascript',
                '.json': 'json', '.sql': 'sql', '.md': 'markdown', '.txt': 'text'
            }.get(ext, 'text')

            try:
                with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
            except Exception as e:
                content = f"// HIBA A FÁJL OLVASÁSAKOR: {e}"

            lines_cnt = len(content.splitlines())
            final_content = mask_authentication_secrets(content) if is_masked else content

            doc.append("---")
            doc.append(f"### [{idx}/{len(files_to_bundle)}] 📄 `{rel_path}`")
            doc.append(f"- **Komponens megnevezése:** {role_title}")
            doc.append(f"- **AI Funkcionális leírás:** {role_desc}")
            doc.append(f"- **Méret:** {lines_cnt} sor | **Elérési út:** `{rel_path}`")
            doc.append("")
            doc.append(f"```{fence_lang}")
            doc.append(final_content)
            doc.append("```")
            doc.append(f"> **[FÁJL VÉGE: `{rel_path}`]**")
            doc.append("")

        out_file.write_text("\n".join(doc), encoding='utf-8')
        print(f"✅ Generálva: {out_file.name} ({len(files_to_bundle)} fájl)")

    return str(raw_path), str(masked_path)

if __name__ == '__main__':
    import sys
    root_p = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    generate_both_ai_bundles(root_p)
