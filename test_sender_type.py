"""Agent ka jawab DB mein 'ai' banta hai ya ghalti se 'user'?"""
import asyncio, io, contextlib, uuid

from sqlalchemy import select

from backend.helper_functions.database.session import SessionLocal
from backend.microservices.livekit_Rag_services.models.message_model import (
    Message, SenderTypeEnum,
)
from backend.microservices.livekit_Rag_services.models.session_model import (
    Session, SessionStatus,
)
from backend.microservices.livekit_Rag_services.services.router_services.message_service import (
    MessageService, _SENDER_ALIASES,
)

svc = MessageService()
noise = io.StringIO()
p = f = 0


def chk(label, got, want):
    global p, f
    if got == want:
        print(f"  PASS  {label:<46} -> {got}")
        p += 1
    else:
        print(f"  FAIL  {label:<46} -> {got}  (chahiye {want})")
        f += 1


async def main():
    print("=" * 74)
    print("SENDER TYPE")
    print("=" * 74)

    print("\n--- 1. mapping (jo call sites asal mein bhejte hain) ---")
    for sent, want in [
        (SenderTypeEnum.ai.value,    SenderTypeEnum.ai),     # voice_pipeline:1488
        (SenderTypeEnum.user.value,  SenderTypeEnum.user),   # voice_pipeline:836
        ("agent",                    SenderTypeEnum.ai),     # purana naam
        ("admin",                    SenderTypeEnum.admin),
        ("guest",                    SenderTypeEnum.guest),
        ("kuch_bhi",                 SenderTypeEnum.guest),  # anjaan -> guest
    ]:
        chk(f"usertype={sent!r}",
            _SENDER_ALIASES.get(sent, SenderTypeEnum.guest), want)

    print("\n--- 2. asli DB mein likh kar parhein ---")
    async with SessionLocal() as db:
        sess = Session(id=uuid.uuid4(), user_id=None, title="sender-type test",
                       status=SessionStatus.active)
        db.add(sess)
        await db.commit()

        uid = uuid.uuid4()
        cases = [
            ("agent ka jawab",  SenderTypeEnum.ai.value,   uid,  SenderTypeEnum.ai),
            ("logged-in sawal", SenderTypeEnum.user.value, uid,  SenderTypeEnum.user),
            ("guest ka sawal",  SenderTypeEnum.user.value, None, SenderTypeEnum.guest),
        ]
        made = []
        for label, ut, u, want in cases:
            with contextlib.redirect_stdout(noise):
                m = await svc.create_message(
                    db=db, content=f"test {label}", user_id=u,
                    usertype=ut, session_id=sess.id,
                )
            made.append(m.id)
            row = (await db.execute(
                select(Message).where(Message.id == m.id)
            )).scalar_one()
            chk(label, row.sender_type, want)
            if want is SenderTypeEnum.ai and row.user_id is not None:
                print("  FAIL  agent ke jawab par user_id laga hua hai")
                globals()['f'] = f + 1

        # safai
        for mid in made:
            await db.execute(Message.__table__.delete().where(Message.id == mid))
        await db.execute(Session.__table__.delete().where(Session.id == sess.id))
        await db.commit()
        print("  (test data hata diya)")

    print("\n" + "=" * 74)
    print(f"  PASS: {p}   FAIL: {f}")
    print("=" * 74)


asyncio.run(main())
