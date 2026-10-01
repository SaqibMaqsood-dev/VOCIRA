"""
What Vocira answers to a question on a call - the voice agent's brain.

The decisions are the older worker's (voice_pipeline.process_voice_intent):
the call's session checked, the question saved, an answer just given reused,
the router (quick_route, else the LLM router), a guardian's own records
behind the auth service's role check, the school's knowledge, staff asked
for. Only the audio is gone - the agent (worker.py) listens and speaks.

Everything here runs on the brain loop (brain_loop.py): the database pool,
Redis and RabbitMQ are made on it, and must never be shared across the
calls' own loops.

    reply = await reply_to(call, question)    # what to say
    ... the agent speaks it ...
    await save_answer(call, question, reply, said)
"""

import asyncio
import json
import traceback
from dataclasses import dataclass
from uuid import UUID

from backend.helper_functions.database.session import SessionLocal
from backend.microservices.livekit_Rag_services.models.escalation_model import (
    Escalation,
    EscalationStatus,
)
from backend.microservices.livekit_Rag_services.models.message_model import SenderTypeEnum
from backend.microservices.livekit_Rag_services.services.erp_services import connectors
from backend.microservices.livekit_Rag_services.services.groq import (
    answer_cache,
    human_text,
    intent_prompt,
    spoken_text,
)
from backend.microservices.livekit_Rag_services.services.groq.groq import (
    GROQ_FAST_MODEL,
    dataConverter,
)
from backend.microservices.livekit_Rag_services.services.livekit.livekit_services import (
    voice_pipeline as pipeline,
)
from backend.microservices.livekit_Rag_services.services.rag_engine.query import (
    RagPrompt,
    prepare_rag,
)


@dataclass
class Call:
    """Who is calling, from where - read once when the call starts."""

    session_id: UUID
    user_id: UUID | None  # None for a guest
    user_type: str  # "user" / "guest"
    school: object  # tenants.School
    language: str


@dataclass
class Reply:
    """What to say to one question."""

    text: str | None = None  # the whole answer, spoken as it is
    prompt: RagPrompt | None = None  # an answer written from the school's knowledge, streamed
    intent: str = "rag"  # stored with the answer: "rag", "cached", "attendance:Zoya", ...
    cacheable: bool = False  # may be given again to the same question
    handoff: dict | None = None  # staff were asked for: escalation_id, message_id
    message_id: object = None  # the saved question


def as_uuid(value) -> UUID | None:
    """The token's ids as the database keeps them; anything else is no id."""
    try:
        return UUID(str(value).strip()) if value else None
    except (ValueError, TypeError):
        print(f"[Brain] not an id: {value!r}")
        return None


async def _llm(prompt: str, **kwargs):
    """
    dataConverter keeps its model fallbacks but calls Groq with a blocking
    client - so it runs in a thread, and the brain loop (every call's
    database work) never waits on it.
    """
    return await asyncio.to_thread(lambda: asyncio.run(dataConverter(prompt, **kwargs)))


async def _session_exists(db, call: Call) -> bool:
    # the token made the session a moment ago - a fresh call can race it
    for attempt in range(3):
        try:
            await pipeline.session_service.get_session_by_id(db=db, user_id=call.user_id, id_value=call.session_id)
            return True
        except Exception as error:
            if attempt == 2:
                print(f"[Session Check Failed] {error} | not answering")
                return False
            await asyncio.sleep(0.2)
    return False


async def _route(question: str, children: list[dict], last_child, previous_words) -> dict:
    """quick_route for the plain questions, the LLM router for the rest."""
    route = intent_prompt.quick_route(question)
    # with more than one child and a conversation under way, "the result"
    # may mean the child just discussed - only the LLM sees that
    if route and route.get("intent") == "ERP" and len(children) > 1 and (last_child or previous_words):
        route = None
    if route is not None:
        print(f"[Router] without the LLM: {route}")
        return route

    result = await _llm(
        intent_prompt.build_router_prompt(
            user_query=question,
            children=[c["name"] for c in children],
            last_child=last_child,
            previous=previous_words,
        ),
        model=GROQ_FAST_MODEL,
        max_tokens=intent_prompt.ROUTER_MAX_TOKENS,
    )
    raw = (result.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    try:
        route = json.loads(raw)
        if not isinstance(route, dict):
            raise ValueError("route must be an object")
        return route
    except Exception:
        print(f"[Router] JSON parse fail: {raw!r} - answering from the knowledge")
        return {"intent": "RAG"}


def _erp_items(route: dict) -> list[dict]:
    """The router's {resource, student} pairs - one per topic of a compound question."""
    items = route.get("items")
    if items is None and route.get("resource"):
        items = [{"resource": route.get("resource"), "student": route.get("student")}]
    return [
        {"resource": item.get("resource"), "student": (item.get("student") or "").strip() or None}
        for item in (items or [])
        if isinstance(item, dict) and item.get("resource")
    ]


async def _records_answer(call: Call, records, items: list[dict], question: str) -> str:
    """
    A guardian's question about their own children. The token is not
    trusted for this: the auth service says who the caller is, their role,
    and which guardian they are in the school's records.
    """
    language = call.language
    if not call.user_id:
        return human_text.system_message("erp_not_authorized", language)

    stage = "erp"  # which part failed: reaching the records, or writing the answer
    try:
        caller = await pipeline.auth_client.get_internal_user(vocira_user_id=call.user_id)
        if not caller or not isinstance(caller, dict) or str(caller.get("user_id")) != str(call.user_id):
            print(f"[ERP Auth] the auth service did not confirm {call.user_id}: {caller!r}")
            return human_text.system_message("account_not_verified", language)

        role = pipeline.normalize_role(caller.get("role"))
        if role not in pipeline.ERP_ALLOWED_ROLES:
            print(f"[ERP Auth] role {role!r} may not read records")
            return human_text.system_message("erp_not_authorized_short", language)

        guardian_id = caller.get("parent_id")
        if not guardian_id:
            print(f"[ERP Mapping] no parent_id for {call.user_id}")
            return human_text.system_message("erp_not_linked", language)

        print(f"[ERP] guardian {guardian_id} asks: {question} -> {items}")
        # a compound question's topics are separate lookups - made together
        results = await asyncio.gather(*[
            records.fetch(
                resource=item["resource"],
                guardian_id=guardian_id,
                student_name=item["student"],
                session_id=str(call.session_id),
            )
            for item in items
        ])
        data = results[0] if len(results) == 1 else list(results)
        print(f"[ERP DATA] {data}")

        stage = "llm"
        response = await _llm(
            human_text.build_response_prompt(
                user_query=question,
                response=data,
                language=language,
                school_name=call.school.name,
            ),
            # the provider reserves max_tokens from the per-minute budget;
            # more topics need more room, capped
            max_tokens=min(640 * len(items), 1600),
        )
        choice = response.choices[0]
        return spoken_text.finish_answer(
            choice.message.content.strip(),
            language,
            cut_off=choice.finish_reason == "length",
        )

    except Exception as error:
        # an LLM out of credit is not "the records are unreachable"
        print(f"[{'LLM' if stage == 'llm' else 'ERP'} Error] {type(error).__name__}: {error}")
        traceback.print_exc()
        return human_text.system_message("answer_assembly_failed" if stage == "llm" else "erp_unreachable", language)


async def _ask_for_staff(db, call: Call, question: str, message_id) -> Reply:
    """
    An escalation for the admin panel, and the caller told staff are being
    called. Guests too: a parent asking about admissions has no account yet
    - their escalation simply has no user, and the panel shows "Guest".
    """
    escalation = Escalation(user_id=call.user_id, message_id=message_id, status=EscalationStatus.pending)
    db.add(escalation)
    await db.commit()
    await db.refresh(escalation)
    print(f"[Escalation Created] {escalation.id}")

    try:
        await pipeline.rabbitmq.publish_admin_handoff({
            "event": "admin.call.handoff",
            "call_id": str(call.session_id),
            "session_id": str(call.session_id),
            "room_name": f"room-{call.session_id}",
            "caller_id": str(call.user_id) if call.user_id else None,
            "escalation_id": str(escalation.id),
            "message_id": str(message_id),
            "message": question,
        })
        print("[RabbitMQ] Admin handoff published.")
    except Exception as error:
        print(f"[RabbitMQ] Failed to publish admin handoff: {error}")
        traceback.print_exc()

    return Reply(
        text=human_text.system_message("connecting_to_staff", call.language),
        intent="admin_handoff",
        handoff={"escalation_id": escalation.id, "message_id": message_id},
        message_id=message_id,
    )


async def reply_to(call: Call, question: str) -> Reply | None:
    """What to say to `question` - None when nothing should be said."""
    school, language = call.school, call.language
    records = connectors.connector_for(school, default_service=pipeline.erp_service)
    children_task = asyncio.create_task(pipeline.caller_children(call.user_id, records))

    async with SessionLocal() as db:
        if not await _session_exists(db, call):
            children_task.cancel()
            return None
        message = await pipeline.message_service.create_message(
            db=db,
            content=question,
            user_id=call.user_id,
            usertype=SenderTypeEnum.user.value,
            session_id=call.session_id,
        )

        children = await children_task
        last_child = None
        if children:
            last_id = await pipeline.erp_service.last_student_id(str(call.session_id))
            last_child = next((c["name"] for c in children if c["id"] == last_id), None)
        previous_words = pipeline.take_previous_words(call.session_id, question)
        print(f"[Context] children={[c['name'] for c in children]} "
              f"last_child={last_child!r} previous={previous_words!r}")

        # "and her result?" means a different child at different points of
        # a call - an answer that leaned on what came before is never reused
        use_cache = not (last_child or previous_words)
        cached = answer_cache.get(call.user_id, question, language, school.id) if use_cache else None
        if cached:
            print("[Cache] this same question was just asked")
            return Reply(text=cached, intent="cached", message_id=message.id)

        route = await _route(question, children, last_child, previous_words)
        intent = str(route.get("intent", "RAG")).strip().upper()
        items = _erp_items(route)
        print(f"[Route]: intent={intent} items={items}")

        if intent == "ERP" and items and not any(item["student"] for item in items):
            await pipeline.erp_service.forget_student(str(call.session_id))

        if pipeline.ADMIN_HANDOFF_INTENT in intent:
            print("[Route]: ADMIN HANDOFF")
            return await _ask_for_staff(db, call, question, message.id)

    if intent == "ERP" and items:
        # "attendance:Zoya+fee:Zoya" - the My Calls table's Topic column
        topic = "+".join(f"{i['resource']}:{i['student']}" if i["student"] else i["resource"] for i in items)
        if not records.available:
            print(f"[Route]: records asked, but {school.name} has no records system")
            text = human_text.system_message("records_not_available", language, school=school)
        else:
            print("[Route]: ERP Pipeline")
            text = await _records_answer(call, records, items, question)
        return Reply(text=text, intent=topic, cacheable=use_cache, message_id=message.id)

    print("[Route]: RAG Pipeline")
    prepared = await prepare_rag(
        await pipeline.retriever_for(school),
        question,
        language=language,
        # the router's plain restatement, searched beside the caller's words
        search_query=route.get("search"),
        school_name=school.name,
    )
    if isinstance(prepared, str):  # nothing in the school's knowledge relates to it
        return Reply(text=prepared, intent=intent.lower(), cacheable=use_cache, message_id=message.id)
    return Reply(prompt=prepared, intent=intent.lower(), cacheable=use_cache, message_id=message.id)


async def save_answer(call: Call, question: str, reply: Reply, said: str) -> None:
    """The answer into the call's history (and the cache, if it may be reused)."""
    said = (said or "").strip()
    if not said:
        return
    if reply.cacheable:
        # put() turns error answers away on its own
        answer_cache.put(
            user_id=call.user_id,
            question=question,
            answer=said,
            language=call.language,
            school=call.school.id,
        )
    async with SessionLocal() as db:
        await pipeline.message_service.create_message(
            db=db,
            content=said,
            user_id=call.user_id,
            usertype=SenderTypeEnum.ai.value,
            session_id=call.session_id,
            intent=reply.intent,
        )
