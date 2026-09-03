# firstly run 9000 port command then auth_service lievkit service docker command and frontend command npm run dev 
#  uv run python -m uvicorn backend.microservices.gateway_api.main:app --port 9000 
# activate  env
# source backend/microservices/livekit_Rag_services/.venv/bin/activate

# auth services
# uv run --project backend/microservices/auth_services uvicorn backend.microservices.auth_services.main.main:app --port 8000
# livekit service

# uv run --project backend/microservices/livekit_Rag_services  python -m uvicorn backend.microservices.livekit_Rag_services.main.main:app --port 8001


# docker

# docker run --rm -p 7880:7880 -p 7881:7881 -p 7882:7882/udp \
#   livekit/livekit-server \
#   --dev \
#   --bind 0.0.0.0 \
#   --keys devkey: secret







#⁡⁣⁢⁢ docker livekit ⁡

# docker run --rm -p 7880:7880 -p 7881:7881 -p 7882:7882/udp \
#   livekit/livekit-server \
#   --dev


#⁡⁣⁢⁢ livekit meet
# cd backend/meet
# npm run dev