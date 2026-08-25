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

    # ==========================================================
    # MAIN ERP QUERY
    # ==========================================================

    async def handle_query(
        self,
        user_query: str,
        erp_parent_id: str,
    ):

        print("=" * 70)
        print("🏫 [ERP SERVICE]")
        print(f"User Query   : {user_query}")
        print(f"ERP Parent ID: {erp_parent_id}")
        print("=" * 70)

        # ======================================================
        # 1. BUILD ERP PROMPT
        # ======================================================

        prompt = build_erp_prompt(
            user_query=user_query,
        )

        print("=" * 70)
        print("📝 [ERP PROMPT]")
        print(prompt)
        print("=" * 70)

        # ======================================================
        # 2. CALL LLM FOR QUERY PLAN
        # ======================================================

        result = await dataConverter(prompt)

        if not result:
            raise ValueError(
                "ERP LLM returned empty response"
            )

        if not result.choices:
            raise ValueError(
                "ERP LLM returned no choices"
            )

        llm_response = (
            result
            .choices[0]
            .message
            .content
        )

        print("=" * 70)
        print("🤖 [ERP LLM RAW RESPONSE]")
        print(repr(llm_response))
        print("=" * 70)

        if not llm_response:
            raise ValueError(
                "ERP LLM returned empty content"
            )

        llm_response = llm_response.strip()

        # ======================================================
        # 3. CLEAN MARKDOWN
        # ======================================================

        if llm_response.startswith("```"):

            lines = llm_response.splitlines()

            if lines:
                lines = lines[1:]

            if (
                lines
                and lines[-1].strip() == "```"
            ):
                lines = lines[:-1]

            llm_response = "\n".join(
                lines
            ).strip()

        # ======================================================
        # 4. PARSE JSON
        # ======================================================

        try:

            decision = json.loads(
                llm_response
            )

        except json.JSONDecodeError as exc:

            print("=" * 70)
            print("❌ [ERP JSON ERROR]")
            print(
                f"Raw LLM response: "
                f"{repr(llm_response)}"
            )
            print("=" * 70)

            raise ValueError(
                "LLM returned invalid ERP query JSON"
            ) from exc

        # ======================================================
        # 5. VALIDATE QUERY PLAN
        # ======================================================

        if not isinstance(
            decision,
            dict,
        ):
            raise ValueError(
                "ERP query plan must be a JSON object"
            )

        print("=" * 70)
        print("🧠 [ERP QUERY PLAN]")
        print(decision)
        print("=" * 70)

        # ======================================================
        # 6. GET RESOURCE
        # ======================================================

        resource = decision.get(
            "resource"
        )

        if not resource:
            raise ValueError(
                "ERP query plan does not contain a resource"
            )

        if resource not in ERP_RESOURCES:
            raise ValueError(
                f"Unauthorized ERP resource: {resource}"
            )

        resource_config = ERP_RESOURCES[
            resource
        ]

        endpoint = resource_config[
            "endpoint"
        ]

        authorization = resource_config[
            "authorization"
        ]

        # ======================================================
        # 7. GET LLM FILTERS
        # ======================================================

        llm_filters = decision.get(
            "filters",
            [],
        )

        if not isinstance(
            llm_filters,
            list,
        ):
            raise ValueError(
                "ERP filters must be a list"
            )

        filters = list(
            llm_filters
        )

        # ======================================================
        # 8. APPLICATION LEVEL AUTHORIZATION
        # ======================================================

        if authorization == "guardian":

            # --------------------------------------------------
            # Guardian resources
            # --------------------------------------------------

            filters.append(
                [
                    "name",
                    "=",
                    erp_parent_id,
                ]
            )

        elif authorization == "student":

            # --------------------------------------------------
            # STEP 1
            #
            # Get students belonging to authenticated guardian
            # --------------------------------------------------

            parent_students = (
                await self.get_parent_students(
                    erp_parent_id=erp_parent_id,
                )
            )

            if not parent_students:

                raise ValueError(
                    "No students found for this guardian"
                )

            # --------------------------------------------------
            # STEP 2
            #
            # Extract authorized ERP student IDs
            # --------------------------------------------------

            student_ids = [
                student["name"]
                for student in parent_students
                if isinstance(student, dict)
                and student.get("name")
            ]

            print("=" * 70)
            print("🔐 [AUTHORIZED STUDENT IDS]")
            print(
                f"Guardian   : {erp_parent_id}"
            )
            print(
                f"Student IDs: {student_ids}"
            )
            print("=" * 70)

            # --------------------------------------------------
            # STEP 3
            #
            # Check whether LLM provided student_name
            # --------------------------------------------------

            student_name = (
                self.extract_student_name(
                    filters=filters
                )
            )

            resolved_student_ids = student_ids

            if student_name:

                print("=" * 70)
                print("🔎 [STUDENT NAME RESOLUTION]")
                print(
                    f"Requested Name: {student_name}"
                )
                print("=" * 70)

                # --------------------------------------------------
                # IMPORTANT SECURITY STEP
                #
                # Resolve ONLY inside already-authorized students.
                # --------------------------------------------------

                resolved_student_ids = (
                    await self.resolve_student_name(
                        student_name=student_name,
                        authorized_student_ids=student_ids,
                    )
                )

                if not resolved_student_ids:

                    raise ValueError(
                        f"Student '{student_name}' "
                        "was not found among the "
                        "authenticated guardian's students"
                    )

                # --------------------------------------------------
                # Remove ALL student_name filters from LLM.
                #
                # From this point onward, application-controlled
                # ERP student IDs are used.
                # --------------------------------------------------

                filters = [
                    filter_item
                    for filter_item in filters
                    if not (
                        isinstance(
                            filter_item,
                            list,
                        )
                        and len(filter_item) >= 1
                        and filter_item[0]
                        == "student_name"
                    )
                ]

            # --------------------------------------------------
            # STEP 4
            #
            # Determine ERP field that references Student
            # --------------------------------------------------

            student_filter_field = (
                resource_config.get(
                    "student_filter_field",
                    "student",
                )
            )

            # --------------------------------------------------
            # STEP 5
            #
            # APPLICATION-CONTROLLED AUTHORIZATION FILTER
            # --------------------------------------------------

            filters.append(
                [
                    student_filter_field,
                    "in",
                    resolved_student_ids,
                ]
            )

        else:

            raise ValueError(
                f"Invalid authorization strategy: "
                f"{authorization}"
            )

        # ======================================================
        # 9. BUILD ERP PARAMETERS
        # ======================================================

        params = {
            "filters": json.dumps(
                filters
            )
        }

        # ======================================================
        # 10. FIELDS
        # ======================================================

        fields = decision.get(
            "fields",
            [],
        )

        if not isinstance(
            fields,
            list,
        ):
            raise ValueError(
                "ERP fields must be a list"
            )

        # ------------------------------------------------------
        # IMPORTANT
        #
        # Program Enrollment list endpoint does not reliably
        # return child-table fields such as "courses".
        #
        # We therefore always make sure "name" and "student"
        # are available for Program Enrollment.
        # ------------------------------------------------------

        if resource == "program_enrollment":

            required_fields = [
                "name",
                "student",
                "student_name",
            ]

            fields = list(
                dict.fromkeys(
                    required_fields + fields
                )
            )

        if fields:

            params["fields"] = json.dumps(
                fields
            )

        # ======================================================
        # 11. LIMIT
        # ======================================================

        limit = decision.get(
            "limit",
            20,
        )

        if not isinstance(
            limit,
            int,
        ):
            raise ValueError(
                "ERP limit must be an integer"
            )

        limit = min(
            max(limit, 1),
            100,
        )

        params[
            "limit_page_length"
        ] = limit

        # ======================================================
        # 12. DEBUG ERP REQUEST
        # ======================================================

        print("=" * 70)
        print("🏫 [ERP REQUEST]")
        print(
            f"Resource            : {resource}"
        )
        print(
            f"Endpoint            : {endpoint}"
        )
        print(
            f"Authorization       : {authorization}"
        )
        print(
            f"ERP Parent ID       : {erp_parent_id}"
        )
        print(
            f"Student Filter Field: "
            f"{resource_config.get('student_filter_field')}"
        )
        print(
            f"Filters             : {filters}"
        )
        print(
            f"Fields              : {fields}"
        )
        print(
            f"Limit               : {limit}"
        )
        print(
            f"Params              : {params}"
        )
        print("=" * 70)

        # ======================================================
        # 13. CALL ERPNEXT LIST ENDPOINT
        # ======================================================

        data = await self.client.get(
            endpoint=endpoint,
            params=params,
        )

        # ======================================================
        # 14. ERP RESPONSE
        # ======================================================

        print("=" * 70)
        print("🏫 [ERP LIST RESPONSE]")
        print(data)
        print("=" * 70)

        # ======================================================
        # 15. SPECIAL HANDLING:
        #     PROGRAM ENROLLMENT CHILD TABLE
        # ======================================================

        if resource == "program_enrollment":

            data = await self.enrich_program_enrollments(
                data=data,
                endpoint=endpoint,
            )

        # ======================================================
        # 16. FINAL ERP DATA
        # ======================================================

        print("=" * 70)
        print("🏫 [FINAL ERP DATA]")
        print(data)
        print("=" * 70)

        return data

    # ==========================================================
    # EXTRACT STUDENT NAME
    # ==========================================================

    @staticmethod
    def extract_student_name(
        filters: list,
    ) -> str | None:

        for filter_item in filters:

            if not isinstance(
                filter_item,
                list,
            ):
                continue

            if len(filter_item) < 3:
                continue

            field = filter_item[0]
            operator = filter_item[1]
            value = filter_item[2]

            if (
                field == "student_name"
                and operator == "="
                and isinstance(value, str)
            ):
                return value.strip()

        return None

    # ==========================================================
    # RESOLVE STUDENT NAME
    # ==========================================================

    async def resolve_student_name(
        self,
        student_name: str,
        authorized_student_ids: list[str],
    ) -> list[str]:

        endpoint = (
            ERP_RESOURCES[
                "student"
            ]["endpoint"]
        )

        params = {
            "filters": json.dumps(
                [
                    [
                        "name",
                        "in",
                        authorized_student_ids,
                    ]
                ]
            ),
            "fields": json.dumps(
                [
                    "name",
                    "student_name",
                ]
            ),
            "limit_page_length": 100,
        }

        print("=" * 70)
        print("🔎 [RESOLVE STUDENT NAME]")
        print(
            f"Requested Name: {student_name}"
        )
        print(
            f"Authorized IDs: {authorized_student_ids}"
        )
        print("=" * 70)

        data = await self.client.get(
            endpoint=endpoint,
            params=params,
        )

        students = data.get(
            "data",
            [],
        )

        if not isinstance(
            students,
            list,
        ):
            raise ValueError(
                "ERP Student response is invalid"
            )

        requested_name = (
            student_name.strip().lower()
        )

        matched_ids = []

        for student in students:

            if not isinstance(
                student,
                dict,
            ):
                continue

            student_id = student.get(
                "name"
            )

            actual_name = student.get(
                "student_name"
            )

            if not student_id or not actual_name:
                continue

            actual_name_normalized = (
                actual_name.strip().lower()
            )

            # --------------------------------------------------
            # Exact full name
            # --------------------------------------------------

            if (
                actual_name_normalized
                == requested_name
            ):

                matched_ids.append(
                    student_id
                )

                continue

            # --------------------------------------------------
            # First name
            #
            # Alisha -> Alisha Ahmed
            # --------------------------------------------------

            first_name = (
                actual_name_normalized
                .split()[0]
            )

            if first_name == requested_name:

                matched_ids.append(
                    student_id
                )

        print("=" * 70)
        print("🔎 [STUDENT NAME RESULT]")
        print(
            f"Requested Name : {student_name}"
        )
        print(
            f"Matched IDs    : {matched_ids}"
        )
        print("=" * 70)

        return matched_ids

    # ==========================================================
    # ENRICH PROGRAM ENROLLMENT
    #
    # IMPORTANT:
    #
    # Program Enrollment contains:
    #
    # courses -> child table
    #
    # ERPNext list endpoint may only return:
    #
    # {
    #     "name": "...",
    #     "student": "...",
    #     "student_name": "..."
    # }
    #
    # Therefore we fetch each document individually.
    # ==========================================================

    async def enrich_program_enrollments(
        self,
        data: dict,
        endpoint: str,
    ) -> dict:

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "Program Enrollment response is invalid"
            )

        enrollments = data.get(
            "data",
            [],
        )

        if not isinstance(
            enrollments,
            list,
        ):
            raise ValueError(
                "Program Enrollment data is invalid"
            )

        if not enrollments:

            print("=" * 70)
            print(
                "📚 [PROGRAM ENROLLMENT]"
            )
            print(
                "No program enrollments found."
            )
            print("=" * 70)

            return data

        enriched_enrollments = []

        # ------------------------------------------------------
        # Fetch each Program Enrollment document
        # ------------------------------------------------------

        for enrollment in enrollments:

            if not isinstance(
                enrollment,
                dict,
            ):
                continue

            enrollment_id = enrollment.get(
                "name"
            )

            if not enrollment_id:

                print(
                    "⚠️ Program Enrollment "
                    "record has no name."
                )

                continue

            # --------------------------------------------------
            # Individual document endpoint
            #
            # Example:
            #
            # /api/resource/Program Enrollment/EDU-ENR-...
            # --------------------------------------------------

            detail_endpoint = (
                f"{endpoint}/{enrollment_id}"
            )

            print("=" * 70)
            print(
                "📚 [PROGRAM ENROLLMENT DETAIL]"
            )
            print(
                f"Enrollment ID: {enrollment_id}"
            )
            print(
                f"Endpoint     : {detail_endpoint}"
            )
            print("=" * 70)

            try:

                detail_data = (
                    await self.client.get(
                        endpoint=detail_endpoint,
                        params={},
                    )
                )

            except Exception as exc:

                print("=" * 70)
                print(
                    "❌ [PROGRAM ENROLLMENT DETAIL ERROR]"
                )
                print(
                    f"Enrollment ID: {enrollment_id}"
                )
                print(
                    f"Error        : {exc}"
                )
                print("=" * 70)

                # Keep original record if detail request fails.
                enriched_enrollments.append(
                    enrollment
                )

                continue

            detail = detail_data.get(
                "data"
            )

            if not isinstance(
                detail,
                dict,
            ):
                print(
                    "⚠️ Program Enrollment "
                    "detail response invalid."
                )

                enriched_enrollments.append(
                    enrollment
                )

                continue

            # --------------------------------------------------
            # Merge list record + full document
            # --------------------------------------------------

            merged = {
                **enrollment,
                **detail,
            }

            # --------------------------------------------------
            # DEBUG COURSES
            # --------------------------------------------------

            courses = merged.get(
                "courses",
                [],
            )

            print("=" * 70)
            print(
                "📚 [COURSES FOUND]"
            )
            print(
                f"Enrollment : {enrollment_id}"
            )
            print(
                f"Courses    : {courses}"
            )
            print(
                f"Course Count: "
                f"{len(courses) if isinstance(courses, list) else 'N/A'}"
            )
            print("=" * 70)

            enriched_enrollments.append(
                merged
            )

        # ------------------------------------------------------
        # Replace original list with enriched records
        # ------------------------------------------------------

        return {
            **data,
            "data": enriched_enrollments,
        }

    # ==========================================================
    # GET STUDENTS BELONGING TO GUARDIAN
    # ==========================================================

    async def get_parent_students(
        self,
        erp_parent_id: str,
    ) -> list[dict]:

        endpoint = (
            ERP_RESOURCES[
                "student"
            ]["endpoint"]
        )

        params = {
            "filters": json.dumps(
                [
                    [
                        "Student Guardian",
                        "guardian",
                        "=",
                        erp_parent_id,
                    ]
                ]
            ),
            "fields": json.dumps(
                [
                    "name",
                    "student_name",
                ]
            ),
            "limit_page_length": 100,
        }

        print("=" * 70)
        print("🔍 [ERP STUDENT LOOKUP]")
        print(
            f"Guardian: {erp_parent_id}"
        )
        print(
            f"Filters : {params['filters']}"
        )
        print("=" * 70)

        data = await self.client.get(
            endpoint=endpoint,
            params=params,
        )

        students = data.get(
            "data",
            [],
        )

        if not isinstance(
            students,
            list,
        ):
            raise ValueError(
                "ERP Student response is invalid"
            )

        print("=" * 70)
        print(
            "👨‍👩‍👧 [PARENT STUDENTS]"
        )
        print(
            f"Guardian     : {erp_parent_id}"
        )
        print(
            f"Students     : {students}"
        )
        print(
            f"Student Count: {len(students)}"
        )
        print("=" * 70)

        return students