"""
Support tickets - ERPNext ke apne Issue doctype mein.

Kyun ERPNext mein aur VOCIRA ke DB mein nahi:

ERPNext ka Support module pehle se poora ticket system rakhta hai -
list, filter, staff ko assign karna, reply, resolve, close. School
ka banda localhost:8081/app/issue par wahi kaam karta hai jo wo aam
tor par karta hai. Hamein na koi admin screen banani parti, na koi
nayi table.

Maalik ERPNext hai: ticket ka status, assignment aur reply sab wahin
rehte hain. VOCIRA sirf ticket banata hai aur us ka number lauta
deta hai - apni koi copy nahi rakhta, warna do jagah status rakh kar
drift shuru ho jati.
"""

import html

from backend.microservices.livekit_Rag_services.services.erp_services.ERP_client import (
    ERPClient,
)


ISSUE_ENDPOINT = "/api/resource/Issue"

# Voice call se aayi baat aur form se aayi baat alag pehchani jaayein
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
        ERPNext mein Issue banayein aur us ka ticket number lautayein.

        subject ERPNext mein lazmi hai; baqi sab optional.
        """

        subject = (subject or "").strip()[:MAX_SUBJECT]
        message = (message or "").strip()[:MAX_MESSAGE]

        if not subject:
            raise ValueError("Subject is required")

        # Kis ne bheja - description ke upar bhi likh dete hain.
        #
        # raised_by field mein email pehle se jata hai, magar wo Data
        # field hai: naam us mein nahi aa sakta, aur ERPNext ke kuch
        # views us ko numayan nahi karte. Ticket kholte hi school ko
        # bhejne wale ka naam aur email saaf nazar aana chahiye.
        header = (
            f"<p><b>From:</b> {html.escape(raised_by_name or 'Guest')} "
            f"&lt;{html.escape(raised_by or 'no email')}&gt;</p>"
        )

        payload = {
            "subject": subject,
            # description "Text Editor" field hai - HTML samajhti hai.
            # Parent ka likha hua escape karna zaroori hai, warna
            # us ka text markup ban kar tootta hai.
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

        # Bachche ka Customer record - is se ticket us ke record se
        # juR jata hai. Na mile to ticket phir bhi banta hai.
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
        Sirf isi parent ke tickets.

        Filter yahan lagti hai, caller par bharosa nahi kiya jata -
        wahi usool jo ERP ke baqi data par hai.
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
