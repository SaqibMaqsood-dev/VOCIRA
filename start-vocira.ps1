# =====================================================================
# VOCIRA - sab kuch chalane ka script
#
#   .\start-vocira.ps1                  backend + infra
#   .\start-vocira.ps1 -All             + ERPNext + frontend  (aam istemal)
#   .\start-vocira.ps1 -WithErp         + sirf ERPNext
#   .\start-vocira.ps1 -WithFrontend    + sirf frontend
#   .\start-vocira.ps1 -WithTunnel      + Cloudflare tunnel (Vercel ke liye)
#   .\start-vocira.ps1 -Stop            sab band
#   .\start-vocira.ps1 -Status          kya chal raha hai
#
# Har service apni window mein khulti hai taake logs nazar aayen.
#
# -WithTunnel jaan bujh kar -All mein shamil nahi hai: ye backend ko
# internet par khol deta hai, jis ki zaroorat sirf Vercel wali site
# test karte waqt hoti hai - roz ke local kaam mein nahi.
# =====================================================================

param(
    [switch]$All,
    [switch]$WithErp,
    [switch]$WithFrontend,
    [switch]$WithTunnel,
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

# Tunnel ka log aur us se nikali hui URL. -Status baad mein yahin se
# padhta hai, taake URL dobara dhoondni na pare.
$TUNNEL_LOG = Join-Path $ROOT ".tunnel.log"
$TUNNEL_URL = Join-Path $ROOT ".tunnel-url.txt"

# Quick tunnel ki URL har baar nayi hoti hai - ye pattern usay log se
# nikalta hai. api.trycloudflare.com Cloudflare ka apna endpoint hai,
# hamari URL nahi, is liye usay chhod dete hain.
$TUNNEL_RX = 'https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com'

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
        Write-Host ("      {0} process(es) still alive" -f $left.Count) -ForegroundColor Red
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
            Write-Host ("  {0}  down" -f $c.n) -ForegroundColor DarkGray
        }
    }

    Write-Host "`n--- Agent worker ---" -ForegroundColor Cyan
    try {
        $q = Invoke-RestMethod "http://localhost:15672/api/queues/%2F/vocira_queue" -TimeoutSec 5 `
             -Headers @{ Authorization = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("guest:guest")) }
        $col = if ($q.consumers -ge 1) { "Green" } else { "Red" }
        Write-Host ("  consumers={0}  queued={1}  running={2}" -f $q.consumers, $q.messages_ready, $q.messages_unacknowledged) -ForegroundColor $col
        if ($q.consumers -lt 1) { Write-Host "  worker is not running - no call will connect" -ForegroundColor Red }
    } catch { Write-Host "  Could not reach RabbitMQ" -ForegroundColor DarkGray }

    Write-Host "`n--- Cloudflare tunnel ---" -ForegroundColor Cyan
    $cf = @(Get-Process cloudflared -ErrorAction SilentlyContinue)
    if ($cf.Count -eq 0) {
        Write-Host "  down  (starts with -WithTunnel)" -ForegroundColor DarkGray
    } elseif (Test-Path $TUNNEL_URL) {
        $u = (Get-Content $TUNNEL_URL -Raw).Trim()
        Write-Host "  $u" -ForegroundColor Green
        Write-Host "  ^ this should be Vercel's NEXT_PUBLIC_API_URL" -ForegroundColor DarkGray
    } else {
        Write-Host "  running but the URL was not found - check .tunnel.log" -ForegroundColor Yellow
    }

    Write-Host ""
    return
}

# ---------------------------------------------------------------------
# STOP
# ---------------------------------------------------------------------
if ($Stop) {
    Write-Host "Stopping Python services..." -ForegroundColor Yellow
    Stop-VociraPython | Out-Null

    Write-Host "Stopping frontend..." -ForegroundColor Yellow
    Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*VOCIRA-feature-backend*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

    Write-Host "Stopping tunnel..." -ForegroundColor Yellow
    Get-Process cloudflared -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
    Remove-Item $TUNNEL_URL -ErrorAction SilentlyContinue

    Write-Host "Stopping infra containers..." -ForegroundColor Yellow
    docker compose -f docker-compose.infra.yml stop 2>$null | Out-Null

    if ($WithErp -or $All) {
        Write-Host "Stopping ERPNext..." -ForegroundColor Yellow
        Push-Location $ERP; docker compose -f pwd.yml stop 2>$null | Out-Null; Pop-Location
    }
    Write-Host "Done." -ForegroundColor Green
    return
}

# =====================================================================
# START
# =====================================================================

# ---------------------------------------------------------------------
# DOCKER PEHLE
#
# Docker Desktop band ho to Postgres/RabbitMQ uthte hi nahi, aur script
# aage chal kar sirf "Postgres ne jawab nahi diya" kehti thi - asli
# wajah nazar hi nahi aati thi. Ab shuru mein hi saaf bata dete hain.
# ---------------------------------------------------------------------
docker info 2>$null | Out-Null
if (-not $?) {
    Write-Host "`nDocker Desktop is not running." -ForegroundColor Red
    Write-Host "  Postgres, RabbitMQ, LiveKit and ERPNext all run on it."

    $dockerExe = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($dockerExe) {
        Write-Host "  Starting it..." -ForegroundColor Yellow
        Start-Process $dockerExe

        for ($i = 0; $i -lt 90; $i++) {
            Start-Sleep -Seconds 2
            docker info 2>$null | Out-Null
            if ($?) { break }
        }

        docker info 2>$null | Out-Null
        if ($?) {
            Write-Host "  Docker is ready." -ForegroundColor Green
        } else {
            Write-Host "  Docker did not become ready within 3 minutes." -ForegroundColor Red
            Write-Host "  Open Docker Desktop yourself and try again."
            return
        }
    } else {
        Write-Host "  Open Docker Desktop and try again." -ForegroundColor Yellow
        return
    }
}

# ---------------------------------------------------------------------
# 0. PURANE PROCESSES SAAF
#
# Bina iske dobara chalane par purani services zinda reh jati thin.
# Sab se bura asar agent worker par: DO worker chalne lagte the aur
# dono ek hi queue se messages uthate the.
# ---------------------------------------------------------------------
$old = @(Get-VociraPython)
if ($old.Count -gt 0) {
    Write-Host ("`n[0/6] Found {0} old process(es) - stopping them..." -f $old.Count) -ForegroundColor Yellow
    Stop-VociraPython | Out-Null
}

# ---------------------------------------------------------------------
# 1. INFRA  (Postgres 5433, Redis 6380, RabbitMQ 5672, LiveKit 7880)
# ---------------------------------------------------------------------
Write-Host "`n[1/6] Infra containers..." -ForegroundColor Cyan
# 2>$null, not 2>&1: docker writes its progress ("Container X
# Running") to stderr, and PowerShell turns native stderr into
# ErrorRecords - which printed a wall of red NativeCommandError at the
# end of a completely successful start.
docker compose -f docker-compose.infra.yml up -d 2>$null | Out-Null

Write-Host "      Waiting for Postgres..." -ForegroundColor DarkGray
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    docker exec vocira-postgres pg_isready -U vocira -d vocira 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $ok = $true; break }
    Start-Sleep -Seconds 2
}
if ($ok) { Write-Host "      Postgres is ready." -ForegroundColor Green }
else     { Write-Host "      Postgres did not respond." -ForegroundColor Red }

# ---------------------------------------------------------------------
# 2. PURANI ATKI HUI CALLS SAAF
#
# Agar pichhli baar koi tab band kar diya gaya ho (end call dabaye
# baghair) to us ki session "active" reh jati hai aur RabbitMQ message
# atka reh jata hai - phir worker nayi calls nahi uthata.
# ---------------------------------------------------------------------
Write-Host "`n[2/6] Clearing stuck old calls..." -ForegroundColor Cyan

# RabbitMQ ko uthne mein 20-30 second lag jate hain. Pehle yahan
# intezaar nahi tha, is liye purge chup chaap fail ho jata tha - aur
# yahi wo step hai jo atki hui calls saaf karta hai.
$rmqAuth = @{ Authorization = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("guest:guest")) }
$rmqReady = $false
Write-Host "      Waiting for RabbitMQ..." -ForegroundColor DarkGray
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
        Write-Host "      Queue cleared." -ForegroundColor Green
    } catch {
        # Queue abhi bani hi nahi (pehli baar) - koi masla nahi
        Write-Host "      Queue does not exist yet - that's fine." -ForegroundColor DarkGray
    }
} else {
    Write-Host "      RabbitMQ did not respond - stuck calls were not cleared." -ForegroundColor Red
}

try {
    docker exec vocira-postgres psql -U vocira -d vocira -c "UPDATE sessions SET status='closed', end_at=NOW() WHERE status='active';" 2>$null | Out-Null
    Write-Host "      Old sessions closed." -ForegroundColor Green
} catch { }

# ---------------------------------------------------------------------
# 3. ERPNext  (port 8081)
# ---------------------------------------------------------------------
if ($WithErp) {
    Write-Host "`n[3/6] ERPNext..." -ForegroundColor Cyan
    Push-Location $ERP
    # NOTE: 'down' KABHI mat chalayein - education app container mein
    #       hai, volume mein nahi. 'stop'/'start' mehfooz hain.
    docker compose -f pwd.yml start 2>$null | Out-Null
    Pop-Location
    Write-Host "      http://localhost:8081  (Administrator / admin)" -ForegroundColor Green

    # -----------------------------------------------------------------
    # nginx apne startup par backend container ka IP resolve kar ke
    # cache kar leta hai. Jab backend container restart hota hai
    # (jaisa upar 'docker compose start' abhi kar sakta hai), us ka IP
    # badal jata hai - nginx purana IP par bhejta rehta hai aur har
    # request 502 deti hai, jab tak nginx khud restart na ho aur naya
    # IP resolve na kare.
    #
    # Isay pehle haath se pakra gaya tha (docker restart
    # frappe_test-frontend-1). Ab yahan khud check + fix ho jata hai.
    # -----------------------------------------------------------------
    Write-Host "      Checking for a stale-IP 502..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 3
    $erpOk = $false
    for ($i = 0; $i -lt 20; $i++) {
        try {
            $r = Invoke-WebRequest "http://localhost:8081/api/method/ping" -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -eq 200) { $erpOk = $true; break }
        } catch {
            $code = $_.Exception.Response.StatusCode.value__
            if ($code -eq 502) {
                Write-Host "      -> 502 (stale nginx IP) - restarting frappe_test-frontend-1..." -ForegroundColor Yellow
                docker restart frappe_test-frontend-1 2>$null | Out-Null
                Start-Sleep -Seconds 5
            }
        }
        Start-Sleep -Seconds 2
    }
    if ($erpOk) {
        Write-Host "      -> ERPNext responding normally" -ForegroundColor DarkGreen
    } else {
        Write-Host "      -> ERPNext still not responding - check 'docker logs frappe_test-frontend-1'" -ForegroundColor Red
    }
} else {
    Write-Host "`n[3/6] ERPNext skipped (starts with -WithErp or -All)" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------
# 4. BACKEND SERVICES
# ---------------------------------------------------------------------
Write-Host "`n[4/6] Backend services..." -ForegroundColor Cyan

# A crash used to mean the window just closed - or sat there with
# nothing to check, if -NoExit kept it open. Now every service's
# output also lands in logs/<name>.log (overwritten fresh each start
# stopped, not appended forever), so "why did it die" has an answer
# without needing to have been watching the window at the time.
$LOG_DIR = Join-Path $ROOT "logs"
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR | Out-Null
}

# NOTE on `cmd /c`: uvicorn writes its normal INFO lines to stderr,
# not stdout. Merging that with PowerShell's own `2>&1` wraps every
# one of those lines in an ErrorRecord, so a perfectly healthy start
# filled the window with red "NativeCommandError" text and the log
# with the same noise. Letting cmd.exe do the merge means PowerShell
# only ever sees plain stdout, and the window shows what the service
# actually said.
# A single click inside a service window used to freeze that service.
# QuickEdit turns the click into a text selection ("Select" in the
# title), and while it lasts the console stops taking output - the
# service blocks on its very next log line and answers nothing. It
# froze the gateway once, so every token request hung. Each window
# switches QuickEdit off for itself before starting its service.
$NO_QUICKEDIT = @'
Add-Type -Name ConsoleMode -Namespace Vocira -MemberDefinition @"
[DllImport("kernel32.dll")] public static extern IntPtr GetStdHandle(int handle);
[DllImport("kernel32.dll")] public static extern bool GetConsoleMode(IntPtr handle, out uint mode);
[DllImport("kernel32.dll")] public static extern bool SetConsoleMode(IntPtr handle, uint mode);
"@
$stdin = [Vocira.ConsoleMode]::GetStdHandle(-10)
$mode = [uint32]0
if ([Vocira.ConsoleMode]::GetConsoleMode($stdin, [ref]$mode)) {
    [void][Vocira.ConsoleMode]::SetConsoleMode($stdin, ($mode -band (-bnot [uint32]0x40)) -bor [uint32]0x80)
}
'@

# -EncodedCommand, because the QuickEdit snippet needs double quotes
# that would not survive being passed on a command line.
function Start-Window($command) {
    $encoded = [Convert]::ToBase64String(
        [Text.Encoding]::Unicode.GetBytes("$NO_QUICKEDIT`n$command")
    )
    Start-Process powershell -ArgumentList "-NoExit", "-EncodedCommand", $encoded
}

function Start-Svc($title, $cmd, $logName) {
    $logPath = Join-Path $LOG_DIR "$logName.log"
    Start-Window "`$host.UI.RawUI.WindowTitle='$title'; `$env:PYTHONUNBUFFERED='1'; Set-Location '$ROOT'; cmd /c '$cmd 2>&1' | Tee-Object -FilePath '$logPath'"
    Write-Host "      $title  (log: logs/$logName.log)" -ForegroundColor Green
}

# Fixed sleep par bharosa na karein - service ke asal mein jawab dene
# ka intezaar karein. Pehle auth ko kabhi kabhi der lag jati thi aur
# script aage barh jati thi, phir health check use "band" batata tha.
# livekit takes ~40s to boot (heavy ML imports), and this used to
# print nothing at all until it was done - forty silent seconds look
# exactly like a hang, which is why "it gets stuck here" was the usual
# report. It now counts up on one line, so a slow start is visibly a
# slow start and not a frozen script.
function Wait-Svc($title, $url, $seconds = 60) {
    Write-Host ("      waiting for {0}" -f $title) -NoNewline -ForegroundColor DarkGray

    for ($i = 0; $i -lt $seconds; $i += 2) {
        try {
            Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 3 | Out-Null
            Write-Host ""
            Write-Host ("      -> {0} ready ({1}s)" -f $title, $i) -ForegroundColor DarkGreen
            return $true
        } catch {
            Write-Host "." -NoNewline -ForegroundColor DarkGray
            Start-Sleep -Seconds 2
        }
    }

    Write-Host ""
    Write-Host ("      -> {0} did not respond within {1}s" -f $title, $seconds) -ForegroundColor Red
    Write-Host ("         check logs/{0}.log or its window" -f $title) -ForegroundColor DarkGray
    return $false
}

# All three are launched back-to-back, THEN waited on - not
# start-wait-start-wait. They are independent processes on independent
# ports (gateway proxies to the others over HTTP at request time, not
# at startup), so there was never a real reason for livekit's process
# to sit unstarted for up to 60s just because auth hadn't answered yet.
# Waiting serially added the FULL readiness time of each service on
# top of the others (up to 60+90+60=210s); starting them together
# means their startup overlaps, so the total wait is roughly the
# slowest one (livekit, the heaviest import) instead of the sum of all
# three.
Start-Svc "VOCIRA auth :8000" `
    "uv run --project $AUTH python -u -m uvicorn backend.microservices.auth_services.main.main:app --host 127.0.0.1 --port 8000" `
    "auth"

Start-Svc "VOCIRA livekit :8001" `
    "uv run --project $LK python -u -m uvicorn backend.microservices.livekit_Rag_services.main.main:app --host 127.0.0.1 --port 8001" `
    "livekit"

Start-Svc "VOCIRA gateway :9000" `
    "uv run --project $LK python -u -m uvicorn backend.microservices.gateway_api.main:app --host 127.0.0.1 --port 9000" `
    "gateway"

# A failed service used to be announced once and then ignored - the
# script carried on, and the first real sign of trouble was the app
# saying "Could not reach the server" much later. Now whatever failed
# is named here, with the end of its own log, while it is still
# obvious which step it belongs to.
$svcResults = @{
    auth    = (Wait-Svc "auth" "http://127.0.0.1:8000/docs" 60)
    livekit = (Wait-Svc "livekit" "http://127.0.0.1:8001/docs" 120)
    gateway = (Wait-Svc "gateway" "http://127.0.0.1:9000/docs" 60)
}

foreach ($name in @("auth", "livekit", "gateway")) {
    if ($svcResults[$name]) { continue }

    Write-Host ""
    Write-Host ("      !! {0} did not start - last lines of logs/{1}.log:" -f $name, $name) -ForegroundColor Red

    $svcLog = Join-Path $LOG_DIR "$name.log"
    if (Test-Path $svcLog) {
        Get-Content $svcLog -Tail 12 | ForEach-Object {
            Write-Host "         $_" -ForegroundColor DarkGray
        }
    } else {
        Write-Host "         (no log was written - the window may have closed instantly)" -ForegroundColor DarkGray
    }
}

# LAZMI: ye RabbitMQ se "session.created" sunta hai aur AI agent ko
# LiveKit room mein bhejta hai. Iske baghair call to lag jayegi magar
# koi agent join nahi karega - user akela baitha rahega.
Start-Svc "VOCIRA agent worker" `
    "uv run --project $LK python -u -m backend.microservices.livekit_Rag_services.livekit_worker" `
    "agent-worker"

# ---------------------------------------------------------------------
# 5. CLOUDFLARE TUNNEL  (gateway :9000 ko internet par le aata hai)
#
# Quick tunnel ko Cloudflare account nahi chahiye, magar do baatein
# yaad rakhein:
#
#   - URL har baar nayi banti hai. Process band, URL khatam. Is liye
#     har restart ke baad Vercel ka NEXT_PUBLIC_API_URL badalna parta
#     hai (aur redeploy).
#   - Cloudflare ka quick-tunnel API kabhi kabhi slow hota hai aur
#     cloudflared apna intezaar chhod deta hai. Is liye neeche 3 baar
#     koshish hoti hai - warna script bilkul chup chaap URL ke baghair
#     aage nikal jati thi.
# ---------------------------------------------------------------------
$tunnelUrl = $null

if ($WithTunnel) {
    Write-Host "`n[5/6] Cloudflare tunnel..." -ForegroundColor Cyan

    if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
        Write-Host "      cloudflared is not installed - skipping tunnel." -ForegroundColor Red
    } else {
        # Purani tunnel zinda ho to nayi ke saath do URL chal parti hain
        Get-Process cloudflared -ErrorAction SilentlyContinue |
            ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }

        for ($try = 1; $try -le 3 -and -not $tunnelUrl; $try++) {
            Remove-Item $TUNNEL_LOG -ErrorAction SilentlyContinue

            $cf = Start-Process cloudflared `
                -ArgumentList "tunnel", "--url", "http://localhost:9000", "--no-autoupdate" `
                -RedirectStandardError $TUNNEL_LOG `
                -RedirectStandardOutput "$TUNNEL_LOG.out" `
                -WindowStyle Hidden -PassThru

            for ($i = 0; $i -lt 40 -and -not $tunnelUrl; $i += 2) {
                Start-Sleep -Seconds 2
                if (Test-Path $TUNNEL_LOG) {
                    $hit = Select-String -Path $TUNNEL_LOG -Pattern $TUNNEL_RX -ErrorAction SilentlyContinue |
                           Select-Object -First 1
                    if ($hit) { $tunnelUrl = $hit.Matches[0].Value }
                }
            }

            if (-not $tunnelUrl) {
                Write-Host ("      attempt {0} failed - retrying..." -f $try) -ForegroundColor DarkGray
                Stop-Process -Id $cf.Id -Force -ErrorAction SilentlyContinue
            }
        }

        if ($tunnelUrl) {
            Set-Content -Path $TUNNEL_URL -Value $tunnelUrl
            Write-Host "      $tunnelUrl" -ForegroundColor Green
        } else {
            Write-Host "      Tunnel could not be created (Cloudflare's API is slow)." -ForegroundColor Red
            Write-Host "      Later: cloudflared tunnel --url http://localhost:9000" -ForegroundColor DarkGray
        }
    }
} else {
    Write-Host "`n[5/6] Tunnel skipped (starts with -WithTunnel)" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------
# 6. FRONTEND  (port 3000)
# ---------------------------------------------------------------------
if ($WithFrontend) {
    Write-Host "`n[6/6] Frontend..." -ForegroundColor Cyan
    if (-not (Test-Path (Join-Path $ROOT "frontend\node_modules"))) {
        Write-Host "      node_modules not found - run 'cd frontend ; npm install' first." -ForegroundColor Red
    } else {
        Start-Window "`$host.UI.RawUI.WindowTitle='VOCIRA frontend :3000'; Set-Location '$ROOT\frontend'; npm run dev"
        Write-Host "      VOCIRA frontend :3000" -ForegroundColor Green
    }
} else {
    Write-Host "`n[6/6] Frontend skipped (starts with -WithFrontend or -All)" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------------------
Write-Host "`nWaiting for the agent worker and frontend..." -ForegroundColor Cyan
# Frontend has its own readiness check (bounded at 40s, same idea as
# Wait-Svc).
#
# The worker used to get a flat 5s grace period before -Status read
# its consumer count. It takes longer than that to register with
# RabbitMQ, so the summary regularly ended on "worker is not running
# - no call will connect" about a worker that was starting perfectly
# well. (Speeding livekit's boot up made it worse: the services were
# ready sooner, so the worker had even less of a head start.) It has
# no HTTP endpoint, but its consumer count is the real readiness
# signal - so poll that instead of guessing with a sleep.
if ($WithFrontend) {
    Wait-Svc "frontend" "http://localhost:3000" 40 | Out-Null
}

Write-Host "      waiting for agent worker" -NoNewline -ForegroundColor DarkGray
$workerReady = $false
for ($i = 0; $i -lt 60; $i += 2) {
    try {
        $q = Invoke-RestMethod "http://localhost:15672/api/queues/%2F/vocira_queue" -TimeoutSec 3 `
             -Headers @{ Authorization = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("guest:guest")) }
        if ($q.consumers -ge 1) { $workerReady = $true; break }
    } catch { }
    Write-Host "." -NoNewline -ForegroundColor DarkGray
    Start-Sleep -Seconds 2
}
Write-Host ""
if ($workerReady) {
    Write-Host "      -> agent worker connected" -ForegroundColor DarkGreen
} else {
    Write-Host "      -> agent worker never registered - see logs/agent-worker.log" -ForegroundColor Red
}
& $PSCommandPath -Status

Write-Host @"
---------------------------------------------------------------
  Frontend  http://localhost:3000    <- start here
  Gateway   http://localhost:9000/docs
  RabbitMQ  http://localhost:15672   (guest / guest)
"@ -ForegroundColor Cyan
if ($WithErp) { Write-Host "  ERPNext   http://localhost:8081     (Administrator / admin)" -ForegroundColor Cyan }
Write-Host @"

  Login     muhmmadahmed763@edu.com / Test@1234
  Stop      .\start-vocira.ps1 -Stop
  Status    .\start-vocira.ps1 -Status
---------------------------------------------------------------
"@ -ForegroundColor Cyan

# Sab se aakhir mein, taake health check ke shor mein gum na ho jaye -
# har restart par yehi ek cheez hai jo haath se karni parti hai.
if ($tunnelUrl) {
    Write-Host @"

===============================================================
  TUNNEL URL (changes on every restart)

  $tunnelUrl

  Vercel -> Settings -> Environment Variables
      NEXT_PUBLIC_API_URL  =  $tunnelUrl
  then Deployments -> Redeploy

  (if NEXT_PUBLIC_REALTIME_URL exists, delete it - otherwise
   admin notifications will not work)
===============================================================
"@ -ForegroundColor Yellow
}
