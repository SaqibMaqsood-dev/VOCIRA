from backend.microservices.auth_services.models.user_model  import *
from backend.microservices.auth_services.models.role_model  import *
from backend.microservices.auth_services.models.permission_model  import *
from backend.microservices.livekit_Rag_services.models.message_model import *
from backend.microservices.auth_services.models.role_permision_model  import *
from backend.microservices.livekit_Rag_services.models.escalation_model import *


def   table_list():

   DB_SCHEMA = {

      "users": {
         "id": "integer (primary key)",
         "name": "text",
         "email": "text (unique)",
         "phone_number": "text (unique)",
         "password": "text",
         "role_id": "integer (FK -> role.role_id)",
         "created_at": "timestamp",
         "updated_at": "timestamp",
         "address": "text",
         "location": "text",
         "date_birth": "date"
      },

      "role": {
         "role_id": "integer (primary key)",
         "name": "text (unique)"
      },

      "permissions": {
         "id": "integer (primary key)",
         "name": "text (unique)"
      },

      "role_permissions": {
         "role_id": "integer (FK -> role.role_id)",
         "permission_id": "integer (FK -> permissions.id)",
         "PRIMARY KEY": "(role_id, permission_id)"
      },

      "sessions": {
         "id": "integer (primary key)",
         "user_id": "integer (FK -> users.id)",
         "start_at": "timestamp (default now)",
         "end_at": "timestamp (nullable)",
         "title": "text",
         "status": "enum(active, closed)"
      },

      "messages": {
         "id": "integer (primary key)",
         "user_id": "integer (FK -> users.id)",
         "session_id": "integer (FK -> sessions.id)",
         "sender_type": "enum(user, ai, admin)",
         "created_at": "timestamp",
         "content": "text",
         "intent": "text",
         "source_type": "enum(rag, database)"
      },

      "escalations": {
         "id": "integer (primary key)",
         "user_id": "integer (FK -> users.id)",
         "message_id": "integer (FK -> messages.id)",
         "status": "enum(pending, open, customer_waiting, resolved, closed)",
         "assigned_admin": "integer (FK -> users.id, nullable)",
         "created_at": "timestamp"
      }
   }

   RELATIONSHIPS = {

      # USERS CORE RELATIONS
      "users": {
         "role": "many-to-one (users.role_id -> role.role_id)",
         "sessions": "one-to-many (users.id -> sessions.user_id)",
         "messages": "one-to-many (users.id -> messages.user_id)",
         "escalations_created": "one-to-many (users.id -> escalations.user_id)",
         "escalations_assigned": "one-to-many (users.id -> escalations.assigned_admin)"
      },

      # ROLE SYSTEM
      "role": {
         "users": "one-to-many (role.role_id -> users.role_id)",
         "permissions": "many-to-many via role_permissions"
      },

      "permissions": {
         "roles": "many-to-many via role_permissions"
      },

      "role_permissions": {
         "role": "FK -> role.role_id",
         "permission": "FK -> permissions.id"
      },

      # SESSION FLOW
      "sessions": {
         "user": "many-to-one (sessions.user_id -> users.id)",
         "messages": "one-to-many (sessions.id -> messages.session_id)"
      },

      # MESSAGES FLOW
      "messages": {
         "user": "many-to-one (messages.user_id -> users.id)",
         "session": "many-to-one (messages.session_id -> sessions.id)",
         "escalation": "one-to-one (messages.id -> escalations.message_id)"
      },

      # ESCALATION SYSTEM
      "escalations": {
         "user": "many-to-one (escalations.user_id -> users.id)",
         "message": "one-to-one (escalations.message_id -> messages.id)",
         "admin": "many-to-one (escalations.assigned_admin -> users.id)"
      }
   }

   return [DB_SCHEMA , RELATIONSHIPS]