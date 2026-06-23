import asyncio
from database.database import get_db
from seed.role_seed import seed_roles
from seed.permision_seed import permission_seed   
from seed.role_permision_seed import role_permission_seed


# IMPORTANT: load models
from models import (
    escalation_model, message_model, permision_model,
    refresh_tokken_model, role_model, role_permission_model,
    session_model, user_model, user_role_model
)


async def run_seed():
    async for db in get_db():

        # ORDER MATTERS 
        await seed_roles(db)
        await permission_seed(db)        
        await role_permission_seed(db)   

asyncio.run(run_seed())

print("successfully seed run")