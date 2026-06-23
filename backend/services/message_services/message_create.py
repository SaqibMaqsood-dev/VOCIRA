from fastapi import   HTTPException , status
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy import select
from models import message_model , user_model 
from models.session_model import Session , SessionStatus
from sqlalchemy.orm import selectinload


async def create_message(db: AsyncSession, user_id, content, usertype , session_id):
    try:

        if user_id and str(user_id).strip().lower() not in ("guest", "none", "null"):
            user_id = int(user_id)
        else:
            user_id = None
        
        # ----------------------------------------
        # Finding Active Session for Guest Users
        # ----------------------------------------
        
        if session_id:
            stmt = (
                select(Session)
                .where(
                    Session.status == SessionStatus.active, 
                    Session.id == session_id
                )
            )

            result = await db.execute(stmt)
            active_session = result.scalars().first()


            if not active_session:
                print(f"⚠️ [create_message] Active session {session_id} not found for guest.")
                return None

            new_message = message_model.Message(
                session_id=active_session.id,
                user_id=None, 
                sender_type=message_model.SenderTypeEnum.guest,
                intent="guest_voice_input",
                source_type=None, 
                content=content
            )

            db.add(new_message)
            await db.commit()
            await db.refresh(new_message)
            
            return {"text": content, "session_id": active_session.id}



        # ----------------------------------------
        # Finding Active Session for  Users
        # ----------------------------------------

        stmt = (
            select(Session)
            .where(
                 Session.status == SessionStatus.active,
                 Session.user_id == user_id
            )
            .order_by(Session.start_at.desc()) 
        )
        result = await db.execute(stmt)
        active_session = result.scalars().first()   
        
        if not active_session:
            print(f"⚠️ [create_message] No active session found for user_id: {user_id}")
            return None
            
           # ----------------------------------------
           # Storing Response OF AI Agent
           # ----------------------------------------

        if usertype == "agent":
            new_message = message_model.Message(
                session_id=active_session.id,
                user_id=None,
                sender_type=message_model.SenderTypeEnum.ai,
                intent="agent_response",
                source_type=None, 
                content=content
            )

            db.add(new_message)
            await db.commit()
            await db.refresh(new_message)
            
            return {"text": content, "session_id": active_session.id}

        
           # ----------------------------------------
           # Storing Recode OF User
           # ----------------------------------------


        stmts = select(user_model.Users).options(
            selectinload(user_model.Users.role)
        ).where(user_model.Users.id == user_id)
        
        current_user_role = await db.execute(stmts)
        user_role = current_user_role.scalars().first()

        if not user_role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        if user_role.role.name == "user":
            new_message = message_model.Message(
                session_id=active_session.id,
                user_id=user_id,
                sender_type=message_model.SenderTypeEnum.ai,
                intent="User_data",
                source_type=None, 
                content=content
            )

        

    except Exception as e:
        print("ERROR:", e)
        raise
