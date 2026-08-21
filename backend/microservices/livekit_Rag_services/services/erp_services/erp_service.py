import json

from .ERP_client import ERPClient
from .prompt import build_erp_prompt
from .endpoint import ERP_RESOURCES

from backend.microservices.livekit_Rag_services.services.groq.groq import (
    dataConverter,
)


class ERPService:

    def __init__(self):
        self.client = ERPClient()

    async def handle_query(
        self,
        user_query: str,
        erp_parent_id: str,
    ):

        # =============================t_user(user_id)=====================
        # 1. Generate query plan using LLM
        # ==================================================

        prompt = build_erp_prompt(
            user_query=user_query,
        )

        result = await dataConverter(prompt)

        llm_response = result.choices[0].message.content.strip()

        print(f"🤖 [ERP LLM]: {llm_response}")

        # ==================================================
        # 2. Parse LLM response
        # ==================================================

        try:
            decision = json.loads(llm_response)

        except json.JSONDecodeError as exc:
            raise ValueError(
                "LLM returned invalid ERP query JSON"
            ) from exc

        # ==================================================
        # 3. Validate resource
        # ==================================================

        resource = decision.get("resource")

        if resource not in ERP_RESOURCES:
            raise ValueError(
                f"Unauthorized ERP resource: {resource}"
            )

        resource_config = ERP_RESOURCES[resource]

        endpoint = resource_config["endpoint"]
        authorization = resource_config["authorization"]

        # ==================================================
        # 4. Validate LLM filters
        # ==================================================

        llm_filters = decision.get("filters", [])

        if not isinstance(llm_filters, list):
            raise ValueError(
                "ERP filters must be a list"
            )

        filters = list(llm_filters)

        # ==================================================
        # 5. Authorization
        # ==================================================

        if authorization == "guardian":

            # IMPORTANT:
            # erp_parent_id is NOT the VOCIRA UUID.
            #
            # Example:
            # VOCIRA user_id  = "ea415132-32a4-49ac..."
            # ERP parent_id   = "parent-001"
            #
            # Only the ERP parent ID is sent to ERPNext.

            filters.append([
                "name",
                "=",
                erp_parent_id,
            ])

        elif authorization == "student":

            # Get students belonging to this ERP parent.

            student_ids = await self.get_parent_students(
                erp_parent_id=erp_parent_id,
            )

            if not student_ids:
                raise ValueError(
                    "No students found for this guardian"
                )

            filters.append([
                "name",
                "in",
                student_ids,
            ])

        else:

            raise ValueError(
                f"Invalid authorization strategy: "
                f"{authorization}"
            )

        # ==================================================
        # 6. Build ERPNext parameters
        # ==================================================

        params = {
            "filters": json.dumps(filters)
        }

        # ==================================================
        # 7. Fields
        # ==================================================

        fields = decision.get("fields", [])

        if fields:

            if not isinstance(fields, list):
                raise ValueError(
                    "ERP fields must be a list"
                )

            params["fields"] = json.dumps(fields)

        # ==================================================
        # 8. Limit
        # ==================================================

        limit = decision.get("limit", 20)

        if not isinstance(limit, int):
            raise ValueError(
                "ERP limit must be an integer"
            )

        # Prevent excessive data retrieval
        limit = min(max(limit, 1), 100)

        params["limit_page_length"] = limit

        # ==================================================
        # 9. Debug
        # ==================================================

        print(f"🏫 [ERP Resource]: {resource}")
        print(f"📍 [ERP Endpoint]: {endpoint}")
        print(f"🔐 [ERP Parent ID]: {erp_parent_id}")
        print(f"🔎 [ERP Filters]: {filters}")
        print(f"📦 [ERP Params]: {params}")

        # ==================================================
        # 10. Call ERPNext
        # ==================================================

        data = await self.client.get(
            endpoint=endpoint,
            params=params,
        )

        print(f"🏫 [ERP Response]: {data}")

        return data

    # ==================================================
    # Get students belonging to ERP parent
    # ==================================================

    async def get_parent_students(
        self,
        erp_parent_id: str,
    ) -> list[str]:

        endpoint = ERP_RESOURCES["student"]["endpoint"]

        params = {
            "filters": json.dumps([
                [
                    "guardian",
                    "=",
                    erp_parent_id,
                ]
            ]),
            "fields": json.dumps([
                "name",
                "student_name",
            ]),
            "limit_page_length": 100,
        }

        print(
            "🔍 Fetching students for ERP parent:",
            erp_parent_id,
        )

        data = await self.client.get(
            endpoint=endpoint,
            params=params,
        )

        students = data.get("data", [])

        student_ids = [
            student["name"]
            for student in students
            if student.get("name")
        ]

        print(
            f"👨‍👩‍👧 [Parent Students]: {student_ids}"
        )

        return student_ids