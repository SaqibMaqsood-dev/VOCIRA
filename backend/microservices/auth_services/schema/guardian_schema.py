from uuid import UUID

from pydantic import BaseModel, Field


class ERPGuardianMappingCreate(BaseModel):
    vocira_user_id: UUID
    erp_guardian_id: str = Field(min_length=1, max_length=140)


class ERPGuardianMappingResponse(BaseModel):
    id: UUID
    vocira_user_id: UUID
    erp_guardian_id: str

    model_config = {
        "from_attributes": True
    }


from uuid import UUID

from pydantic import BaseModel


class AddERPGuardianRequest(BaseModel):
    vocira_user_id: UUID
    erp_guardian_id: str