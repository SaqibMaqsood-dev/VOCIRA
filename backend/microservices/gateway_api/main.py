import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
import httpx

from fastapi.middleware.cors import CORSMiddleware


# The gateway has no .env of its own - it reads whatever is already
# in the process environment (which is how docker-compose's shared
# x-backend-env block reaches it). Running it directly with uvicorn
# outside Docker left CORS_ORIGINS unset every time, silently falling
# back to "*" - fine on localhost, wrong the moment the frontend is a
# real deployed origin. This loads the same .env the livekit_Rag
# service uses, so a value set once survives every local restart.
load_dotenv(
    Path(__file__).resolve().parent.parent
    / "livekit_Rag_services"
    / ".env"
)


app = FastAPI(
    title="VOCIRA API Gateway",
    description="API Gateway for Auth and LiveKit services",
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================
#
# Locally everything is localhost, so "*" was good enough. On the
# internet it is not: "*" together with allow_credentials means ANY
# website can call this API on behalf of a logged-in user.
#
# Put your frontend's address into CORS_ORIGINS (the Vercel one);
# several can be given, separated by commas. Leave it unset and the
# old "*" behaviour remains - for local development.

_origins = os.getenv("CORS_ORIGINS", "").strip()

ALLOWED_ORIGINS = (
    [o.strip() for o in _origins.split(",") if o.strip()]
    if _origins
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# SERVICES
# ============================================================
#
# Under Docker each service lives in its own container, so 127.0.0.1
# there is the gateway's own container and the call reaches nothing.
# The default is left as it was so a local setup keeps working
# exactly as before.

AUTH_SERVICE = os.getenv(
    "AUTH_SERVICE_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

LIVEKIT_SERVICE = os.getenv(
    "LIVEKIT_SERVICE_URL",
    "http://127.0.0.1:8001",
).rstrip("/")


# ============================================================
# GENERIC FORWARDER
# ============================================================

async def forward_request(
    service_url: str,
    path: str,
    request: Request,
):
    # Remove leading slash
    path = path.lstrip("/")

    target_url = f"{service_url}/{path}"

    print("=" * 60)
    print("GATEWAY REQUEST")
    print(f"Method : {request.method}")
    print(f"Path   : {path}")
    print(f"Target : {target_url}")
    print("=" * 60)

    body = await request.body()

    # Forward headers except Host
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() != "host"
    }

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=60.0,
    ) as client:

        response = await client.request(
            method=request.method,
            url=target_url,
            params=request.query_params,
            headers=headers,
            content=body,
        )

    print(
        f"SERVICE RESPONSE: "
        f"{response.status_code}"
    )

    print(
        f"SERVICE BODY: "
        f"{response.text}"
    )

    # Don't forward hop-by-hop headers
    excluded_headers = {
        "content-length",
        "transfer-encoding",
        "connection",
    }

    response_headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in excluded_headers
    }

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=response_headers,
        media_type=response.headers.get(
            "content-type"
        ),
    )


# ============================================================
# LIVEKIT FORWARDER
# ============================================================

async def forward_livekit_request(
    path: str,
    request: Request,
):
    # Remove leading slash
    path = path.lstrip("/")

    # IMPORTANT:
    #
    # Gateway receives:
    #
    # /livekit/live_kit/token
    #
    # FastAPI extracts:
    #
    # path = "live_kit/token"
    #
    # LiveKit service actually expects:
    #
    # /livekit/live_kit/token
    #
    # Therefore we add /livekit here.

    target_url = (
        f"{LIVEKIT_SERVICE}/livekit/{path}"
    )

    print("=" * 60)
    print("LIVEKIT GATEWAY REQUEST")
    print(f"Method : {request.method}")
    print(f"Path   : {path}")
    print(f"Target : {target_url}")
    print("=" * 60)

    body = await request.body()

    # Forward headers except Host
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() != "host"
    }

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=60.0,
    ) as client:

        response = await client.request(
            method=request.method,
            url=target_url,
            params=request.query_params,
            headers=headers,
            content=body,
        )

    print(
        f"LIVEKIT SERVICE RESPONSE: "
        f"{response.status_code}"
    )

    print(
        f"LIVEKIT SERVICE BODY: "
        f"{response.text}"
    )

    # Don't forward hop-by-hop headers
    excluded_headers = {
        "content-length",
        "transfer-encoding",
        "connection",
    }

    response_headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in excluded_headers
    }

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=response_headers,
        media_type=response.headers.get(
            "content-type"
        ),
    )


# ============================================================
# AUTH - GET
# ============================================================

@app.get(
    "/auth/{path:path}",
    operation_id="gateway_auth_get",
)
async def gateway_auth_get(
    path: str,
    request: Request,
):
    return await forward_request(
        AUTH_SERVICE,
        path,
        request,
    )


# ============================================================
# AUTH - POST
# ============================================================

@app.post(
    "/auth/{path:path}",
    operation_id="gateway_auth_post",
)
async def gateway_auth_post(
    path: str,
    request: Request,
):
    return await forward_request(
        AUTH_SERVICE,
        path,
        request,
    )


# ============================================================
# AUTH - PUT
# ============================================================

@app.put(
    "/auth/{path:path}",
    operation_id="gateway_auth_put",
)
async def gateway_auth_put(
    path: str,
    request: Request,
):
    return await forward_request(
        AUTH_SERVICE,
        path,
        request,
    )


# ============================================================
# AUTH - PATCH
# ============================================================

@app.patch(
    "/auth/{path:path}",
    operation_id="gateway_auth_patch",
)
async def gateway_auth_patch(
    path: str,
    request: Request,
):
    return await forward_request(
        AUTH_SERVICE,
        path,
        request,
    )


# ============================================================
# AUTH - DELETE
# ============================================================

@app.delete(
    "/auth/{path:path}",
    operation_id="gateway_auth_delete",
)
async def gateway_auth_delete(
    path: str,
    request: Request,
):
    return await forward_request(
        AUTH_SERVICE,
        path,
        request,
    )


# ============================================================
# LIVEKIT - GET
# ============================================================

@app.get(
    "/livekit/{path:path}",
    operation_id="gateway_livekit_get",
)
async def gateway_livekit_get(
    path: str,
    request: Request,
):
    return await forward_livekit_request(
        path,
        request,
    )


# ============================================================
# LIVEKIT - POST
# ============================================================

@app.post(
    "/livekit/{path:path}",
    operation_id="gateway_livekit_post",
)
async def gateway_livekit_post(
    path: str,
    request: Request,
):
    return await forward_livekit_request(
        path,
        request,
    )


# ============================================================
# LIVEKIT - PUT
# ============================================================

@app.put(
    "/livekit/{path:path}",
    operation_id="gateway_livekit_put",
)
async def gateway_livekit_put(
    path: str,
    request: Request,
):
    return await forward_livekit_request(
        path,
        request,
    )


# ============================================================
# LIVEKIT - PATCH
# ============================================================

@app.patch(
    "/livekit/{path:path}",
    operation_id="gateway_livekit_patch",
)
async def gateway_livekit_patch(
    path: str,
    request: Request,
):
    return await forward_livekit_request(
        path,
        request,
    )


# ============================================================
# LIVEKIT - DELETE
# ============================================================

@app.delete(
    "/livekit/{path:path}",
    operation_id="gateway_livekit_delete",
)
async def gateway_livekit_delete(
    path: str,
    request: Request,
):
    return await forward_livekit_request(
        path,
        request,
    )