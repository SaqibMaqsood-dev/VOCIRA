from backend.helper_functions.database.engine import create_database_engine
from backend.microservices.auth_services.core.config import settings

engine = create_database_engine(
   database_url= settings.DATABASE_URL
)
