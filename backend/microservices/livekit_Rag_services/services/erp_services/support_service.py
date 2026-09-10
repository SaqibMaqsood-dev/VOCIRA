"""
Support tickets - in ERPNext's own Issue doctype.

Why ERPNext rather than VOCIRA's database:

ERPNext's Support module already is a complete ticket system - list,
filter, assign to staff, reply, resolve, close. Someone at the school
works at localhost:8081/app/issue exactly as they normally would. We
have to build neither an admin screen nor a new table.

ERPNext owns the data: ticket status, assignment and replies all live
there. VOCIRA only creates the ticket and returns its number - it
keeps no copy of its own, which would mean status in two places and
the drift that follows.
"""

import html

from backend.microservices.livekit_Rag_services.services.erp_services.ERP_client import (
    ERPClient,
)


ISSUE_ENDPOINT = "/api/resource/Issue"

# Tell apart what came from a voice call and what came from the form
TYPE_SUPPORT = "Support Request"
TYPE_ESCALATION = "Voice Escalation"

DEFAULT_PRIORITY = "Medium"

MAX_SUBJECT = 140
MAX_MESSAGE = 5000


class SupportService:

    def __init__(self):
        self.client = ERPClient()

    # ------------------------------------------------------
    # TICKET BANAYEIN
    # ------------------------------------------------------

    async def create_ticket(
        self,
        subject: str,
        message: str,
        raised_by: str | None = None,
        raised_by_name: str | None = None,
        customer: str | None = None,
        issue_type: str = TYPE_SUPPORT,
        priority: str = DEFAULT_PRIORITY,
    ) -> dict:
        """
        Create an Issue in ERPNext and return its ticket number.

        subject is required by ERPNext; everything else is optional.
        """

        subject = (subject or "").strip()[:MAX_SUBJECT]
        message = (message or "").strip()[:MAX_MESSAGE]

        if not subject:
            raise ValueError("Subject is required")

        # Who sent it - written above the description as well.
        #
        # The email already goes into the raised_by field, but that is
        # a Data field: a name cannot go in it, and some ERPNext views
        # do not show it prominently. Opening the ticket should show
        # the school the sender's name and email straight away.
        header = (
            f"<p><b>From:</b> {html.escape(raised_by_name or 'Guest')} "
            f"&lt;{html.escape(raised_by or 'no email')}&gt;</p>"
        )

        payload = {
            "subject": subject,
            # description is a "Text Editor" field - it interprets
            # HTML. What the parent wrote has to be escaped, or their
            # text is read as markup and breaks.
            "description": (
                f"{header}<div>{html.escape(message)}</div>"
                if message
                else header
            ),
            "status": "Open",
            "priority": priority,
            "issue_type": issue_type,
        }

        if raised_by:
            payload["raised_by"] = raised_by

        # The child's Customer record - this attaches the ticket to
        # their record. If none is found the ticket is still created.
        if customer:
            payload["customer"] = customer

        data = await self.client.post(
            endpoint=ISSUE_ENDPOINT,
            payload=payload,
        )

        issue = data.get("data", data) or {}

        return {
            "ticket_id": issue.get("name"),
            "subject": issue.get("subject"),
            "status": issue.get("status"),
            "priority": issue.get("priority"),
            "opening_date": issue.get("opening_date"),
        }

    # ------------------------------------------------------
    # MERE TICKETS
    # ------------------------------------------------------

    async def list_tickets(
        self,
        raised_by: str,
        limit: int = 20,
    ) -> list[dict]:
        """
        Only this parent's tickets.

        The filter is applied here; the caller is not trusted - the
        same rule that governs the rest of the ERP data.
        """

        if not raised_by:
            return []

        data = await self.client.get(
            endpoint=ISSUE_ENDPOINT,
            params={
                "filters": f'[["raised_by","=","{raised_by}"]]',
                "fields": (
                    '["name","subject","status","priority",'
                    '"opening_date","issue_type"]'
                ),
                "order_by": "creation desc",
                "limit_page_length": limit,
            },
        )

        return data.get("data", []) or []
