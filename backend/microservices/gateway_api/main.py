from fastapi import FastAPI, Request, Response
import httpx

from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="VOCIRA API Gateway",
    description="API Gateway for Auth and LiveKit services",
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# SERVICES
# ============================================================

AUTH_SERVICE = "http://127.0.0.1:8000"
LIVEKIT_SERVICE = "http://127.0.0.1:8001"


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