from datetime import datetime
from sqlalchemy import VARCHAR,  DateTime,  func , ForeignKey , Float , text , Integer , Text , Enum, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column
from backend.helper_functions.database import Base
from sqlalchemy.orm import relationship
from sqlalchemy import Text, Enum
from backend.microservices.auth_services.models.role_permision_model import role_permissions
from uuid import UUID , uuid4
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from uuid import uuid4 , UUID

class Role(Base):
    __tablename__ = "role"

    role_id = mapped_column(VARCHAR, primary_key=True)
    name = mapped_column(Text, unique=True)

    users = relationship(
        "Users",
        back_populates="role"
    )

    # Change secondary to the string name of the junction table:
    permissions = relationship(
        "Permission",
        secondary="role_permissions",  # <-- Use string table name here
        back_populates="roles"
    )