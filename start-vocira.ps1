# =====================================================================
# VOCIRA - sab kuch chalane ka script
#
#   .\start-vocira.ps1                  backend + infra
#   .\start-vocira.ps1 -All             + ERPNext + frontend  (aam istemal)
#   .\start-vocira.ps1 -WithErp         + sirf ERPNext
#   .\start-vocira.ps1 -WithFrontend    + sirf frontend
#   .\start-vocira.ps1 -Stop            sab band
#   .\start-vocira.ps1 -Status          kya chal raha hai
#
# Har service apni window mein khulti hai taake logs nazar aayen.
# =====================================================================

param(
    [switch]$All,
    [switch]$WithErp,
    [switch]$WithFrontend,
    [switch]$Stop,
    [switch]$Status
)

# NOTE: "Stop" jaan bujh kar nahi rakha. docker apna progress stderr par
# likhta hai ("Container vocira-redis Stopping"), aur PowerShell 5.1 use
# asli error samajh kar script rok deta hai - halanke sab theek chal raha
# hota hai.
$ErrorActionPreference = "Continue"
$ROOT = "D:\college_vocira_project\VOCIRA-feature-backend"
$ERP  = Join-Path $ROOT "frappe_test"
$LK   = "backend\microservices\livekit_Rag_services"
$AUTH = "backend\microservices\auth_services"

if ($All) { $WithErp = $true; $WithFrontend = $true }

Set-Location $ROOT

function Get-VociraPython {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*VOCIRA-feature-backend*" }
}

# uv har service ke liye ek child python bhi banata hai. Ek hi baar
# maarne se kabhi kabhi child bach jata tha - phir DO agent worker
# chalte rehte the aur dono queue se messages uthate the.
function Stop-VociraPython {
    for ($pass = 0; $pass -lt 4; $pass++) {
        $procs = @(Get-VociraPython)
        if ($procs.Count -eq 0) { return $true }
        $procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 2
    }
    $left = @(Get-VociraPython)
    if ($left.Count -gt 0) {
        Write-Host ("      {0} process abhi bhi zinda hain" -f $left.Count) -ForegroundColor Red
        return $false
    }
    return $true
}

# ---------------------------------------------------------------------
# STATUS
# ---------------------------------------------------------------------
if ($Status) {
    Write-Host "`n--- Services ---" -ForegroundColor Cyan
    $checks = @(
        @{ n = "auth    "; u = "http://127.0.0.1:8000/docs" },
        @{ n = "livekit "; u = "http://127.0.0.1:8001/docs" },
        @{ n = "gateway "; u = "http://127.0.0.1:9000/docs" },
        @{ n = "frontend"; u = "http://localhost:3000" },
        @{ n = "erpnext "; u = "http://localhost:8081/api/method/ping" }
    )
    foreach ($c in $checks) {
        try {
            $r = Invoke-WebRequest $c.u -UseBasicParsing -TimeoutSec 5
            Write-Host ("  {0}  HTTP {1}" -f $c.n, $r.StatusCode) -ForegroundColor Green
        } catch {
            Write-Host ("  {0}  band" -f $c.n) -ForegroundColor DarkGray
        }
    }

    Write-Host "`n--- Agent worker ---" -ForegroundColor Cyan
    try {
        $q = Invoke-RestMethod "http://localhost:15672/api/queues/%2F/vocira_queue" -TimeoutSec 5 `
             -Headers @{ Authorization = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("guest:guest")) }
        $col = if ($q.consumers -ge 1) { "Green" } else { "Red" }
        Write-Host ("  consumers={0}  qatar mein={1}  chal rahi={2}" -f $q.consumers, $q.messages_ready, $q.messages_unacknowledged) -ForegroundColor $col
        if ($q.consumers -lt 1) { Write-Host "  worker nahi chal raha - koi call connect nahi hogi" -ForegroundColor Red }
    } catch { Write-Host "  RabbitMQ tak nahi pohancha" -ForegroundColor DarkGray }

    Write-Host ""
    return
}

# ---------------------------------------------------------------------
# STOP
# ---------------------------------------------------------------------
if ($Stop) {
    Write-Host "Python services band kar rahe hain..." -ForegroundColor Yellow
    Stop-VociraPython | Out-Null

    Write-Host "Frontend band kar rahe hain..." -ForegroundColor Yellow
    Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*VOCIRA-feature-backend*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

    Write-Host "Infra containers band kar rahe hain..." -ForegroundColor Yellow
    docker compose -f docker-compose.infra.yml stop | Out-Null

    if ($WithErp -or $All) {
        Write-Host "ERPNext band kar rahe hain..." -ForegroundColor Yellow
        Push-Location $ERP; docker compose -f pwd.yml stop | Out-Null; Pop-Location
    }
    Write-Host "Ho gaya." -ForegroundColor Green
    return
}

# =====================================================================
# START
# =====================================================================

# ---------------------------------------------------------------------
# 0. PURANE PROCESSES SAAF
#
# Bina iske dobara chalane par purani services zinda reh jati thin.
# Sab se bura asar agent worker par: DO worker chalne lagte the aur
# dono ek hi queue se messages uthate the.
# ---------------------------------------------------------------------
$old = @(Get-VociraPython)
if ($old.Count -gt 0) {
    Write-Host ("`n[0/5] {0} purane process mil gaye - band kar rahe hain..." -f $old.Count) -ForegroundColor Yellow
    Stop-VociraPython | Out-Null
}

# ---------------------------------------------------------------------
# 1. INFRA  (Postgres 5433, Redis 6380, RabbitMQ 5672, LiveKit 7880)
# ---------------------------------------------------------------------
Write-Host "`n[1/5] Infra containers..." -ForegroundColor Cyan
docker compose -f docker-compose.infra.yml up -d | Out-Null

Write-Host "      Postgres ka intezaar..." -ForegroundColor DarkGray
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    docker exec vocira-postgres pg_isready -U vocira -d vocira 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $ok = $true; break }
    Start-Sleep -Seconds 2
}
if ($ok) { Write-Host "      Postgres tayyar." -ForegroundColor Green }
else     { Write-Host "      Postgres ne jawab nahi diya." -ForegroundColor Red }

# ---------------------------------------------------------------------
# 2. PURANI ATKI HUI CALLS SAAF
#
# Agar pichhli baar koi tab band kar diya gaya ho (end call dabaye
# baghair) to us ki session "active" reh jati hai aur RabbitMQ message
# atka reh jata hai - phir worker nayi calls nahi uthata.
# ---------------------------------------------------------------------
Write-Host "`n[2/5] Purani atki hui calls saaf..." -ForegroundColor Cyan

# RabbitMQ ko uthne mein 20-30 second lag jate hain. Pehle yahan
# intezaar nahi tha, is liye purge chup chaap fail ho jata tha - aur
# yahi wo step hai jo atki hui calls saaf karta hai.
$rmqAuth = @{ Authorization = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("guest:guest")) }
$rmqReady = $false
Write-Host "      RabbitMQ ka intezaar..." -ForegroundColor DarkGray
for ($i = 0; $i -lt 60; $i += 3) {
    try {
        Invoke-RestMethod "http://localhost:15672/api/overview" -Headers $rmqAuth -TimeoutSec 3 | Out-Null
        $rmqReady = $true
        break
    } catch { Start-Sleep -Seconds 3 }
}

if ($rmqReady) {
    try {
        Invoke-RestMethod "http://localhost:15672/api/queues/%2F/vocira_queue/contents" -Method Delete -Headers $rmqAuth -TimeoutSec 5 | Out-Null
        Write-Host "      Queue saaf." -ForegroundColor Green
    } catch {
        # Queue abhi bani hi nahi (pehli baar) - koi masla nahi
        Write-Host "      Queue abhi maujood nahi - theek hai." -ForegroundColor DarkGray
    }
} else {
    Write-Host "      RabbitMQ ne jawab nahi diya - atki hui calls saaf nahi hui." -ForegroundColor Red
}

try {
    docker exec vocira-postgres psql -U vocira -d vocira -c "UPDATE sessions SET status='closed', end_at=NOW() WHERE status='active';" 2>&1 | Out-Null
    Write-Host "      Purani sessions band." -ForegroundColor Green
} catch { }

# ---------------------------------------------------------------------
# 3. ERPNext  (port 8081)
# ---------------------------------------------------------------------
if ($WithErp) {
    Write-Host "`n[3/5] ERPNext..." -ForegroundColor Cyan
    Push-Location $ERP
    # NOTE: 'down' KABHI mat chalayein - education app container mein
    #       hai, volume mein nahi. 'stop'/'start' mehfooz hain.
    docker compose -f pwd.yml start | Out-Null
    Pop-Location
    Write-Host "      http://localhost:8081  (Administrator / admin)" -ForegroundColor Green
} else {
    Write-Host "`n[3/5] ERPNext skip (-WithErp ya -All se chalta hai)" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------
# 4. BACKEND SERVICES
# ---------------------------------------------------------------------
Write-Host "`n[4/5] Backend services..." -ForegroundColor Cyan

function Start-Svc($title, $cmd) {
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "`$host.UI.RawUI.WindowTitle='$title'; `$env:PYTHONUNBUFFERED='1'; Set-Location '$ROOT'; $cmd"
    )
    Write-Host "      $title" -ForegroundColor Green
}

# Fixed sleep par bharosa na karein - service ke asal mein jawab dene
# ka intezaar karein. Pehle auth ko kabhi kabhi der lag jati thi aur
# script aage barh jati thi, phir health check use "band" batata tha.
function Wait-Svc($title, $url, $seconds = 60) {
    for ($i = 0; $i -lt $seconds; $i += 2) {
        try {
            Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 3 | Out-Null
            Write-Host ("      -> {0} tayyar ({1}s)" -f $title, $i) -ForegroundColor DarkGreen
            return $true
        } catch { Start-Sleep -Seconds 2 }
    }
    Write-Host ("      -> {0} ne {1}s mein jawab nahi diya - us ki window dekhein" -f $title, $seconds) -ForegroundColor Red
    return $false
}

Start-Svc "VOCIRA auth :8000" `
    "uv run --project $AUTH python -u -m uvicorn backend.microservices.auth_services.main.main:app --host 127.0.0.1 --port 8000"
Wait-Svc "auth" "http://127.0.0.1:8000/docs" 60 | Out-Null

Start-Svc "VOCIRA livekit :8001" `
    "uv run --project $LK python -u -m uvicorn backend.microservices.livekit_Rag_services.main.main:app --host 127.0.0.1 --port 8001"
Wait-Svc "livekit" "http://127.0.0.1:8001/docs" 90 | Out-Null

Start-Svc "VOCIRA gateway :9000" `
    "uv run --project $LK python -u -m uvicorn backend.microservices.gateway_api.main:app --host 127.0.0.1 --port 9000"
Wait-Svc "gateway" "http://127.0.0.1:9000/docs" 60 | Out-Null

# LAZMI: ye RabbitMQ se "session.created" sunta hai aur AI agent ko
# LiveKit room mein bhejta hai. Iske baghair call to lag jayegi magar
# koi agent join nahi karega - user akela baitha rahega.
Start-Svc "VOCIRA agent worker" `
    "uv run --project $LK python -u -m backend.microservices.livekit_Rag_services.livekit_worker"

# ---------------------------------------------------------------------
# 5. FRONTEND  (port 3000)
# ---------------------------------------------------------------------
if ($WithFrontend) {
    Write-Host "`n[5/5] Frontend..." -ForegroundColor Cyan
    if (-not (Test-Path (Join-Path $ROOT "frontend\node_modules"))) {
        Write-Host "      node_modules nahi hai - pehle 'cd frontend ; npm install' chalayein." -ForegroundColor Red
    } else {
        Start-Process powershell -ArgumentList @(
            "-NoExit", "-Command",
            "`$host.UI.RawUI.WindowTitle='VOCIRA frontend :3000'; Set-Location '$ROOT\frontend'; npm run dev"
        )
        Write-Host "      VOCIRA frontend :3000" -ForegroundColor Green
    }
} else {
    Write-Host "`n[5/5] Frontend skip (-WithFrontend ya -All se chalta hai)" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------------------
Write-Host "`nAgent worker aur frontend ka intezaar..." -ForegroundColor Cyan
Start-Sleep -Seconds 35
& $PSCommandPath -Status

Write-Host @"
---------------------------------------------------------------
  Frontend  http://localhost:3000    <- yahan se shuru karein
  Gateway   http://localhost:9000/docs
  RabbitMQ  http://localhost:15672   (guest / guest)
"@ -ForegroundColor Cyan
if ($WithErp) { Write-Host "  ERPNext   http://localhost:8081     (Administrator / admin)" -ForegroundColor Cyan }
Write-Host @"

  Login     ahmed@test.com / Test@1234
  Band      .\start-vocira.ps1 -Stop
  Haal      .\start-vocira.ps1 -Status
---------------------------------------------------------------
"@ -ForegroundColor Cyan
