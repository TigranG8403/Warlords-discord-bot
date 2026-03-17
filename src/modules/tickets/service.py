from __future__ import annotations

from .config import TicketsSettings
from .notifications import TicketNotifications
from .renderers import TicketRenderers
from .repository import TicketRepository
from .service_admin import TicketServiceAdminMixin
from .service_creation import TicketServiceCreationMixin
from .service_interactions import TicketServiceInteractionMixin
from .service_ticket_ops import TicketServiceTicketOpsMixin


class TicketService(
    TicketServiceAdminMixin,
    TicketServiceCreationMixin,
    TicketServiceTicketOpsMixin,
    TicketServiceInteractionMixin,
):
    def __init__(self, settings: TicketsSettings):
        self.settings = settings
        self.repository = TicketRepository(settings.database_path)
        self.repository.initialize()
        self.renderers = TicketRenderers(settings)
        self.notifications = TicketNotifications(settings)
        self._active_interaction_ids: set[int] = set()
