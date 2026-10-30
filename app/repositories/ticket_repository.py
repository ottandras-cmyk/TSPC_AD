from sqlalchemy.orm import Session
from sqlalchemy import desc
import models

class TicketRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all_helpdesk_tickets(self):
        return (
            self.db.query(models.EPHelpdeskTicket)
            .order_by(desc(models.EPHelpdeskTicket.created_on))
            .all()
        )

    def get_ticket_by_id(self, ep_id: int):
        return (
            self.db.query(models.EPHelpdeskTicket)
            .filter(models.EPHelpdeskTicket.ep_id == ep_id)
            .first()
        )

    def get_tasks(self, limit: int = 2000):
        return (
            self.db.query(models.EPTask)
            .order_by(desc(models.EPTask.created_on))
            .limit(limit)
            .all()
        )
