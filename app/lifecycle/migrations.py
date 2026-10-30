import logging

logger = logging.getLogger("migrations")

def run_schema_migrations():
    """
    KONSZOLIDÁLVA: A runtime ALTER TABLE logikákat felváltotta az Alembic migrációs lánc.
    Ez a függvény kompatibilitási okokból meghagyva, de aktív DDL parancsot már nem futtat.
    """
    logger.info("Ad-hoc migrációk inaktiválva. A séma kezelését az Alembic végzi.")

def start_migrations_in_background():
    pass
