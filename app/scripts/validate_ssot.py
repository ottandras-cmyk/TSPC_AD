#!/usr/bin/env python3
import os
import sys
import subprocess

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(CURRENT_DIR)

def run_validation():
    print(">>> [CI/CD] 1. Lépés: Alembic migrációs szinkron vizsgálata...")
    try:
        # Ellenőrzi, hogy van-e eltérés az ORM modellek és az Alembic revíziók között
        res = subprocess.run(
            ["alembic", "check"],
            cwd=APP_DIR,
            capture_output=True,
            text=True
        )
        if res.returncode != 0:
            print("❌ HIBA: Eltérés található az ORM modellek és az Alembic migrációk között!")
            print(res.stdout or res.stderr)
            return False
        print("✅ Alembic migrációk szinkronban vannak az ORM modellekkel.")
    except FileNotFoundError:
        print("⚠️ Figyelmeztetés: 'alembic' parancs nem található közvetlenül a PATH-ban, lépés kihagyva.")

    print(">>> [CI/CD] 2. Lépés: Generált artefaktumok ellenőrzése...")
    # Artefaktumok újragenerálása és git diff vizsgálat
    subprocess.run([sys.executable, os.path.join(CURRENT_DIR, "generate_artifacts.py")], check=True)
    
    diff_res = subprocess.run(
        ["git", "diff", "--exit-code", os.path.join(APP_DIR, "db_dump", "schema.sql"), os.path.join(APP_DIR, "docs")],
        capture_output=True,
        text=True
    )
    if diff_res.returncode != 0:
        print("❌ HIBA: A tárolt dokumentációk vagy a schema.sql elavultak az ORM modellekhez képest!")
        print("Futtasd a 'python3 app/scripts/generate_artifacts.py' parancsot és commitold a változásokat.")
        return False

    print("✅ Minden artefaktum (schema.sql, OpenAPI, Docs) naprakész és valid.")
    return True

if __name__ == "__main__":
    if not run_validation():
        sys.exit(1)
    sys.exit(0)
