from sqlalchemy.orm import Session, joinedload
from sqlalchemy import case, desc
import models

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all_clean_users(self):
        """
        Kiszűri a technikai fantomfiókokat és eager loadinggal kapcsolja a csoportokat
        az N+1 lekérdezési anomáliák megelőzésére.
        """
        return (
            self.db.query(models.ADUser)
            .filter(
                ~models.ADUser.sam_account_name.contains('@'),
                ~models.ADUser.mail.startswith('S-1-5-'),
                ~models.ADUser.sam_account_name.contains(' ')
            )
            .options(joinedload(models.ADUser.groups))
            .order_by(
                case((models.ADUser.display_name.isnot(None), 0), else_=1),
                models.ADUser.display_name.asc(),
                models.ADUser.sam_account_name.asc()
            )
            .all()
        )

    def get_by_sam(self, sam: str):
        return (
            self.db.query(models.ADUser)
            .filter(models.ADUser.sam_account_name == sam)
            .first()
        )

    def get_all_groups(self):
        return (
            self.db.query(models.ADGroup)
            .order_by(models.ADGroup.sam_account_name.asc())
            .all()
        )
