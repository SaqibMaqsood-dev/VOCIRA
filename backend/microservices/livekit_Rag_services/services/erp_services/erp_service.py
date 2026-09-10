import json

from .ERP_client import ERPClient
from .prompt import build_erp_prompt
from .endpoint import ERP_RESOURCES
from .compact import compact_records

# More records than this are of no use to a voice assistant.
DEFAULT_LIMIT = 20

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
        """
        Work out the resource from the question and fetch the data
        (through the LLM).

        The voice pipeline no longer uses this - it gets the resource
        from the same router call and invokes fetch() directly. This
        path is kept for tests, and for any caller that has only the
        question.
        """

        print("=" * 70)
        print("[ERP SERVICE]  (LLM planner path)")
        print(f"User Query   : {user_query}")
        print(f"ERP Parent ID: {erp_parent_id}")
        print("=" * 70)

        result = await dataConverter(
            build_erp_prompt(user_query=user_query)
        )

        if not result or not result.choices:
            raise ValueError("ERP LLM returned empty response")

        llm_response = (result.choices[0].message.content or "").strip()

        if not llm_response:
            raise ValueError("ERP LLM returned empty content")

        # markdown fences hata dein
        if llm_response.startswith("```"):
            lines = llm_response.splitlines()[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            llm_response = "\n".join(lines).strip()

        try:
            decision = json.loads(llm_response)
        except json.JSONDecodeError as exc:
            print("[ERP JSON ERROR]", repr(llm_response))
            raise ValueError(
                "LLM returned invalid ERP query JSON"
            ) from exc

        if not isinstance(decision, dict):
            raise ValueError("ERP query plan must be a JSON object")

        print("[ERP QUERY PLAN]", decision)

        return await self.fetch(
            resource=decision.get("resource"),
            erp_parent_id=erp_parent_id,
            student_name=self.extract_student_name(
                filters=decision.get("filters", []) or []
            ),
        )

    # ==========================================================
    # DATA FETCH  (resource pehle se maloom ho)
    # ==========================================================

    async def fetch(
        self,
        resource: str,
        erp_parent_id: str,
        student_name: str | None = None,
    ):
        """
        Fetch the data for the given resource.

        Authorization happens entirely here - the caller (whether the
        LLM or the router) only says WHAT is wanted. WHOSE data comes
        back is always decided by erp_parent_id.
        """

        print("=" * 70)
        print("[ERP FETCH]")
        print(f"Resource     : {resource}")
        print(f"Student      : {student_name or '(sab)'}")
        print(f"ERP Parent ID: {erp_parent_id}")
        print("=" * 70)

        # ======================================================
        # RESOURCE VALIDATION (whitelist)
        # ======================================================

        if not resource:
            raise ValueError("No ERP resource given")

        if resource not in ERP_RESOURCES:
            raise ValueError(f"Unauthorized ERP resource: {resource}")

        resource_config = ERP_RESOURCES[resource]
        endpoint = resource_config["endpoint"]
        authorization = resource_config["authorization"]

        # Filters are built by the application alone. Filters sent by
        # the caller are never trusted.
        filters: list = []

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
            print("[AUTHORIZED STUDENT IDS]")
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

            # NOTE: student_name now arrives as a fetch() parameter.
            # It used to be read out of the filters here - filters are
            # always empty now, so that would set the parameter to None.

            resolved_student_ids = student_ids

            if student_name:

                print("=" * 70)
                print("[STUDENT NAME RESOLUTION]")
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

                    # No child by this name in this parent's record.
                    # There are two possible reasons: the name really
                    # is not theirs, or STT misheard the spoken name.
                    #
                    # A ValueError used to be raised here and the
                    # parent heard "could not reach the school
                    # records" - even though the records were
                    # perfectly healthy, and "please try again" was
                    # useless because the result never changed.
                    #
                    # Both cases give the same answer on purpose, so
                    # it also does not reveal that the child exists
                    # but belongs to someone else.
                    print(
                        f"[ERP] '{student_name}' is parent ke "
                        "not found among the children"
                    )

                    return {
                        "data": [],
                        "_about": resource_config.get("description") or "",
                        "_note": (
                            f"No child named '{student_name}' was found "
                            "for this parent. The name may have been "
                            "misheard - ask them to say it again."
                        ),
                    }

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

            # In some doctypes (Student Group, for example) the link
            # to the student lives in a child table. Those need
            # Frappe's 4-element filter: [child_doctype, field,
            # operator, value]
            student_filter_doctype = (
                resource_config.get(
                    "student_filter_doctype"
                )
            )

            # --------------------------------------------------
            # STEP 5
            #
            # APPLICATION-CONTROLLED AUTHORIZATION FILTER
            # --------------------------------------------------

            if student_filter_doctype:

                filters.append(
                    [
                        student_filter_doctype,
                        student_filter_field,
                        "in",
                        resolved_student_ids,
                    ]
                )

            else:

                filters.append(
                    [
                        student_filter_field,
                        "in",
                        resolved_student_ids,
                    ]
                )

        elif authorization == "student_group":

            # =================================================
            # CLASS-BASED RESOURCES
            #
            # Timetables and upcoming exams are attached to the
            # student's CLASS, not to the student. Hence:
            #
            #   guardian -> their students -> their classes -> filter
            #
            # Authorization still rests with the application: only
            # the classes the guardian's own children are in.
            # =================================================

            parent_students = (
                await self.get_parent_students(
                    erp_parent_id=erp_parent_id,
                )
            )

            if not parent_students:

                raise ValueError(
                    "No students found for this guardian"
                )

            student_ids = [
                student["name"]
                for student in parent_students
                if isinstance(student, dict)
                and student.get("name")
            ]

            # If the user named a particular child, narrow this
            # down to that child's class only.
            # NOTE: student_name now arrives as a fetch() parameter.
            # It used to be read out of the filters here - filters are
            # always empty now, so that would set the parameter to None.

            resolved_student_ids = student_ids

            if student_name:

                resolved_student_ids = (
                    await self.resolve_student_name(
                        student_name=student_name,
                        authorized_student_ids=student_ids,
                    )
                )

                if not resolved_student_ids:

                    # No child by this name in this parent's record.
                    # There are two possible reasons: the name really
                    # is not theirs, or STT misheard the spoken name.
                    #
                    # A ValueError used to be raised here and the
                    # parent heard "could not reach the school
                    # records" - even though the records were
                    # perfectly healthy, and "please try again" was
                    # useless because the result never changed.
                    #
                    # Both cases give the same answer on purpose, so
                    # it also does not reveal that the child exists
                    # but belongs to someone else.
                    print(
                        f"[ERP] '{student_name}' is parent ke "
                        "not found among the children"
                    )

                    return {
                        "data": [],
                        "_about": resource_config.get("description") or "",
                        "_note": (
                            f"No child named '{student_name}' was found "
                            "for this parent. The name may have been "
                            "misheard - ask them to say it again."
                        ),
                    }

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

            student_groups = (
                await self.get_student_groups(
                    student_ids=resolved_student_ids,
                )
            )

            if not student_groups:

                # The child has not been placed in any class
                # (Student Group) - that is an incomplete school
                # record, not an error.
                #
                # A ValueError used to be raised here, which broke
                # the call: the parent got "something went wrong",
                # when the right answer is "no class is set yet".
                #
                # Empty data is returned in the same shape as any
                # other empty result, so the rest of the flow can
                # treat it like an ordinary empty answer.
                print(
                    f"[ERP] {student_name or 'student'} kisi class "
                    "is in no class - returning an empty schedule"
                )

                return {
                    "data": [],
                    "_about": (
                        resource_config.get("description")
                        or "Class schedule"
                    ),
                    "_note": (
                        "This student has not been assigned to a class "
                        "yet, so there is no timetable to show."
                    ),
                }

            group_filter_field = (
                resource_config.get(
                    "group_filter_field",
                    "student_group",
                )
            )

            filters.append(
                [
                    group_filter_field,
                    "in",
                    student_groups,
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

        # ------------------------------------------------------
        # Fields always come from endpoint.py, never from a caller.
        # The LLM used to invent field names ("attendance_date",
        # "subject", "score") that make Frappe return HTTP 417.
        # ------------------------------------------------------

        fields = resource_config.get(
            "fields",
            [],
        )

        if fields:

            params["fields"] = json.dumps(
                fields
            )

        # ======================================================
        # 11. LIMIT
        # ======================================================

        # For a spoken answer, 20 records is more than enough.
        limit = DEFAULT_LIMIT

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
        print("[ERP REQUEST]")
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
        print("[ERP LIST RESPONSE]")
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

        # ------------------------------------------------------
        # Context for the LLM that writes the answer.
        #
        # Given only the raw records, it often fails to work out
        # that a "Class 5" record is in fact that child's class.
        # ------------------------------------------------------

        if isinstance(data, dict):

            data = compact_records(resource, data)

            data["_about"] = resource_config.get(
                "description",
                resource,
            )

        print("=" * 70)
        print("[FINAL ERP DATA]")
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
        print("[RESOLVE STUDENT NAME]")
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
        print("[STUDENT NAME RESULT]")
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
                "[PROGRAM ENROLLMENT]"
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
                    "Program Enrollment "
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
                "[PROGRAM ENROLLMENT DETAIL]"
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
                    "[PROGRAM ENROLLMENT DETAIL ERROR]"
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
                    "Program Enrollment "
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
                "[COURSES FOUND]"
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
        print("[ERP STUDENT LOOKUP]")
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
            "[PARENT STUDENTS]"
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

    # ==========================================================
    # STUDENT -> CLASS (STUDENT GROUP) RESOLUTION
    # ==========================================================

    async def get_student_groups(
        self,
        student_ids: list[str],
    ) -> list[str]:
        """
        Which classes (Student Groups) the given students are in.

        Timetables and upcoming exams are attached to the class,
        not to the student. This returns classes only for students
        that have already been authorized.
        """

        if not student_ids:
            return []

        endpoint = (
            ERP_RESOURCES[
                "class"
            ]["endpoint"]
        )

        params = {
            "filters": json.dumps(
                [
                    [
                        "Student Group Student",
                        "student",
                        "in",
                        student_ids,
                    ]
                ]
            ),
            "fields": json.dumps(
                [
                    "name",
                ]
            ),
            "limit_page_length": 100,
        }

        print("=" * 70)
        print("[STUDENT GROUP LOOKUP]")
        print(
            f"Students: {student_ids}"
        )
        print("=" * 70)

        data = await self.client.get(
            endpoint=endpoint,
            params=params,
        )

        groups = data.get(
            "data",
            [],
        )

        if not isinstance(
            groups,
            list,
        ):
            raise ValueError(
                "ERP Student Group response is invalid"
            )

        # Several children can share a class - drop the duplicates
        group_names = sorted(
            {
                group["name"]
                for group in groups
                if isinstance(group, dict)
                and group.get("name")
            }
        )

        print("=" * 70)
        print("[AUTHORIZED CLASSES]")
        print(
            f"Classes: {group_names}"
        )
        print("=" * 70)

        return group_names