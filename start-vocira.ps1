# =====================================================================
# VOCIRA - sab kuch chalane ka script
#
#   .\start-vocira.ps1                  backend + infra
#   .\start-vocira.ps1 -All             + ERPNext + frontend  (aam istemal)
#   .\start-vocira.ps1 -WithErp         + sirf ERPNext
#   .\start-vocira.ps1 -WithFrontend    + sirf frontend
#   .\start-vocira.ps1 -WithTunnel      + Cloudflare tunnel (Vercel ke liye)
#   .\start-vocira.ps1 -TunnelOnly      sirf tunnel (dobara) - services jaisi hain waisi
#   .\start-vocira.ps1 -LegacyWorker    purana RabbitMQ agent worker (fallback)
#   .\start-vocira.ps1 -Stop            sab band
#   .\start-vocira.ps1 -Status          kya chal raha hai
#
# Calls are answered by the LiveKit Agents worker (services/agent) by
# default. -LegacyWorker runs the older livekit_worker.py instead, and
# tells the livekit service to hand calls to it (VOICE_ENGINE=legacy).
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
    [switch]$TunnelOnly,
    [switch]$LegacyWorker,
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

# Tunnel ka log aur us ki URL. -Status baad mein URL yahin se padhta hai.
$TUNNEL_LOG = Join-Path $ROOT ".tunnel.log"
$TUNNEL_URL = Join-Path $ROOT ".tunnel-url.txt"

# The quick tunnel's credentials (its id, secret and address), kept so the
# next start reconnects the SAME tunnel - same URL. Gitignored: whoever has
# this file can serve traffic on that URL.
$TUNNEL_CREDS = Join-Path $ROOT ".tunnel-credentials.json"
$QUICK_TUNNEL_API = "https://api.trycloudflare.com/tunnel"

# ---------------------------------------------------------------------
# CLOUDFLARE QUICK TUNNEL  (gateway :9000 ko internet par le aata hai)
#
# Quick tunnel do hisson mein banti hai:
#   1. Cloudflare se nayi tunnel maangna (POST api.trycloudflare.com/tunnel)
#      - jawab mein us ka pata (xxx.trycloudflare.com) aur chaabi aati hai
#   2. cloudflared us chaabi se Cloudflare se jurta hai aur requests
#      gateway (127.0.0.1:9000) tak lata hai
#
# Kyun baar baar fail hoti thi (2026-10-04): "cloudflared tunnel --url"
# pehla hissa khud karta hai, aur jawab ka sirf 15 second intezaar karta hai
# (cloudflared ke andar fix, koi flag nahi). Cloudflare ko tunnel banane mein
# 6-12 second lagte hain, kabhi is se zyada - tab cloudflared "Client.Timeout
# exceeded while awaiting headers" keh kar band ho jata tha. Yeh error
# stderr par aata hai, .tunnel.log mein nahi, is liye nazar bhi nahi aata tha.
# Ab:
#   - pehla hissa yeh script khud karta hai: curl, 60 second, kai koshishein
#   - chaabi .tunnel-credentials.json mein rehti hai, aur agli dafa WOHI
#     tunnel dobara jurti hai - URL wohi, Vercel mein kuch nahi badalna.
#     Cloudflare ne woh tunnel mita di ho ("Unauthorized: Tunnel not
#     found") to khud nayi banti hai.
#   - cloudflared sirf jurta hai: "tunnel run --credentials-file"
#   - --edge-ip-version 4 aur curl -4: Developers Room Wi-Fi par IPv6
#     Cloudflare tak nahi pohanchta tha (2026-10-03)
#   - aakhir mein internet ki taraf se asal check: URL se gateway ka /docs
# ---------------------------------------------------------------------

# The saved tunnel, or $null.
function Read-SavedTunnel {
    if (-not (Test-Path $TUNNEL_CREDS)) { return $null }
    try {
        $saved = Get-Content $TUNNEL_CREDS -Raw | ConvertFrom-Json
        if ($saved.AccountTag -and $saved.TunnelSecret -and $saved.TunnelID -and $saved.Hostname) { return $saved }
    } catch { }
    return $null
}

# Asks Cloudflare for a new quick tunnel, giving it 60 seconds to answer,
# and saves it. $null after every try failed.
function New-QuickTunnel {
    $tries = 6
    for ($try = 1; $try -le $tries; $try++) {
        $lines = @(& curl.exe -4 --http1.1 -s --max-time 60 -X POST -H "Content-Type: application/json" `
                    -w '\n%{http_code}' $QUICK_TUNNEL_API 2>$null)
        $curlExit = $LASTEXITCODE
        $code = if ($lines.Count -gt 0) { "$($lines[-1])".Trim() } else { "" }
        $body = ($lines | Select-Object -SkipLast 1) -join "`n"

        $reply = $null
        try { $reply = $body | ConvertFrom-Json } catch { }
        if ($curlExit -eq 0 -and $code -eq "200" -and $reply.success -and
            $reply.result.id -and $reply.result.secret -and $reply.result.hostname) {
            # The fields cloudflared reads from a credentials file, plus the
            # address (cloudflared ignores fields it does not know).
            $tunnel = [pscustomobject][ordered]@{
                AccountTag   = $reply.result.account_tag
                TunnelSecret = $reply.result.secret
                TunnelID     = $reply.result.id
                Hostname     = $reply.result.hostname
            }
            # UTF-8 without a BOM - cloudflared's JSON reader stops at a BOM
            [IO.File]::WriteAllText($TUNNEL_CREDS, ($tunnel | ConvertTo-Json -Compress), (New-Object Text.UTF8Encoding($false)))
            return $tunnel
        }

        $why = switch ($curlExit) {
            0       { "HTTP $code" }
            6       { "could not look up api.trycloudflare.com (DNS)" }
            7       { "could not connect to Cloudflare" }
            28      { "no answer within 60 seconds" }
            default { "curl error $curlExit" }
        }
        Write-Host ("      Cloudflare gave no tunnel (try {0}/{1}): {2}" -f $try, $tries, $why) -ForegroundColor DarkGray
        if ($try -lt $tries) { Start-Sleep -Seconds ([Math]::Min(5 * $try, 20)) }
    }
    return $null
}

function Stop-Cloudflared {
    $procs = @(Get-Process cloudflared -ErrorAction SilentlyContinue)
    $procs | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
    # Until it has really exited, cloudflared keeps .tunnel.log open - and
    # the next connection then read the old process's "Registered" lines.
    $procs | ForEach-Object { try { [void]$_.WaitForExit(10000) } catch { } }
}

# Starts cloudflared on a tunnel. "ok" once Cloudflare has taken a
# connection; "refused" when Cloudflare no longer knows the tunnel (or its
# key); "exited" / "timeout" when nothing came of it.
function Connect-QuickTunnel($tunnel, $exe) {
    Stop-Cloudflared
    for ($i = 0; $i -lt 10 -and (Test-Path $TUNNEL_LOG); $i++) {
        Remove-Item $TUNNEL_LOG -Force -ErrorAction SilentlyContinue
        if (Test-Path $TUNNEL_LOG) { Start-Sleep -Milliseconds 300 }
    }
    Remove-Item "$TUNNEL_LOG.out" -ErrorAction SilentlyContinue
    if (Test-Path $TUNNEL_LOG) {
        # an old log here would be read as this connection's
        Write-Host "      could not clear the old .tunnel.log (still in use)" -ForegroundColor Red
        return "exited"
    }

    # cloudflared writes its own log. Redirecting its output instead made it
    # inherit - and hold open - the output of whoever ran this script, so a
    # piped run (VS Code, a tool) never finished. 127.0.0.1, not localhost:
    # cloudflared tries localhost as ::1, and the gateway listens on IPv4 only.
    $proc = Start-Process $exe `
        -ArgumentList "tunnel", "--no-autoupdate", "--edge-ip-version", "4", "--logfile", "`"$TUNNEL_LOG`"", `
                      "--url", "http://127.0.0.1:9000", `
                      "run", "--credentials-file", "`"$TUNNEL_CREDS`"", $tunnel.TunnelID `
        -WindowStyle Hidden -PassThru

    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Path $TUNNEL_LOG) {
            if (Select-String -Path $TUNNEL_LOG -Pattern "Registered tunnel connection" -Quiet -ErrorAction SilentlyContinue) { return "ok" }
            if (Select-String -Path $TUNNEL_LOG -Pattern "Unauthorized" -Quiet -ErrorAction SilentlyContinue) { return "refused" }
        }
        if ($proc.HasExited) { return "exited" }
    }
    return "timeout"
}

# HTTP status of the gateway's /docs through a URL ("000": no answer).
function Test-GatewayAt($url, $seconds = 20) {
    return "$(& curl.exe -s -o NUL -w "%{http_code}" --max-time $seconds "$url/docs" 2>$null)".Trim()
}

# The real test, from the internet's side: a few tries, since a request
# across the world can drop once.
function Test-TunnelEndToEnd($url) {
    $code = ""
    for ($i = 0; $i -lt 4; $i++) {
        $code = Test-GatewayAt $url
        if ($code -eq "200") { return "200" }
        Start-Sleep -Seconds 3
    }
    return $code
}

function Start-VociraTunnel {
    $script:TunnelReused = $false
    $exe = Get-Command cloudflared -ErrorAction SilentlyContinue
    if (-not $exe) {
        Write-Host "      cloudflared is not installed - skipping tunnel." -ForegroundColor Red
        return $null
    }
    $exe = $exe.Source
    Remove-Item $TUNNEL_URL -ErrorAction SilentlyContinue

    $gatewayUp = (Test-GatewayAt "http://127.0.0.1:9000" 5) -eq "200"
    if (-not $gatewayUp) {
        Write-Host "      the gateway (:9000) is not running - the tunnel will have nothing behind it" -ForegroundColor Yellow
    }

    $url = $null

    # 1. last time's tunnel - same URL, nothing to change on Vercel
    $tunnel = Read-SavedTunnel
    if ($tunnel) {
        $state = Connect-QuickTunnel $tunnel $exe
        if ($state -ne "ok" -and $state -ne "refused") {
            # a dropped packet on a slow network - not a reason to give up the URL
            $state = Connect-QuickTunnel $tunnel $exe
        }
        $works = $state -eq "ok"
        if ($works -and $gatewayUp) {
            $code = Test-TunnelEndToEnd "https://$($tunnel.Hostname)"
            if ($code -ne "200") { $works = $false; $state = "its URL answered HTTP $code" }
        }
        if ($works) {
            $url = "https://$($tunnel.Hostname)"
            $script:TunnelReused = $true
            Write-Host "      reconnected last time's tunnel" -ForegroundColor DarkGreen
        } else {
            Write-Host "      last time's tunnel is gone ($state) - asking Cloudflare for a new one" -ForegroundColor DarkGray
            Stop-Cloudflared
            Remove-Item $TUNNEL_CREDS -ErrorAction SilentlyContinue
        }
    }

    # 2. a new tunnel
    if (-not $url) {
        $tunnel = New-QuickTunnel
        if ($tunnel) {
            for ($attempt = 1; $attempt -le 3 -and -not $url; $attempt++) {
                $state = Connect-QuickTunnel $tunnel $exe
                if ($state -eq "ok") {
                    $url = "https://$($tunnel.Hostname)"
                } else {
                    Write-Host ("      cloudflared could not connect yet ({0}, try {1}/3)" -f $state, $attempt) -ForegroundColor DarkGray
                    Start-Sleep -Seconds 3
                }
            }
            if ($url -and $gatewayUp) {
                $code = Test-TunnelEndToEnd $url
                if ($code -ne "200") {
                    Write-Host "      the tunnel is connected, but a test request through it got HTTP $code - see .tunnel.log" -ForegroundColor Yellow
                }
            }
        }
    }

    if (-not $url) {
        Stop-Cloudflared
        Write-Host "      No tunnel - Cloudflare could not be reached properly from this network." -ForegroundColor Red
        Write-Host "      Run .\start-vocira.ps1 -TunnelOnly again, or try another network (phone hotspot)." -ForegroundColor Red
        return $null
    }

    Set-Content -Path $TUNNEL_URL -Value $url
    Write-Host "      $url" -ForegroundColor Green
    if ($gatewayUp) {
        Write-Host "      -> checked from the internet: it reaches the gateway" -ForegroundColor DarkGreen
    }
    return $url
}

# What has to be done by hand - only when the URL is a new one
function Show-TunnelUrl($url) {
    if (-not $url) { return }
    if ($script:TunnelReused) {
        Write-Host @"

===============================================================
  TUNNEL URL - the same as last time

  $url

  If Vercel's NEXT_PUBLIC_API_URL is already this, there is
  nothing to do.
===============================================================
"@ -ForegroundColor Green
        return
    }
    Write-Host @"

===============================================================
  NEW TUNNEL URL - Vercel needs it once

  $url

  Vercel -> Settings -> Environment Variables
      NEXT_PUBLIC_API_URL  =  $url
  then Deployments -> Redeploy

  The next starts reconnect this same tunnel, so this is not
  needed every time - only when this box says NEW again.

  (if NEXT_PUBLIC_REALTIME_URL exists, delete it - otherwise
   admin notifications will not work)
===============================================================
"@ -ForegroundColor Yellow
}

if ($All) { $WithErp = $true; $WithFrontend = $true }

Set-Location $ROOT

# The project's own pythons, plus the ones that do not name the project on
# their command line: uv's launcher starts the real interpreter as
# "python -m backend.microservices...", and the voice agent's job runners,
# turn detector and Piper are multiprocessing children whose command line
# is only "spawn_main(parent_pid=...)" - found through their parent. Left
# behind, six of those once held ~6 GB of memory between them.
function Get-VociraPython {
    $all = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue)
    $ours = @{}
    $all | Where-Object {
        $_.CommandLine -and ($_.CommandLine -like "*VOCIRA-feature-backend*" -or $_.CommandLine -like "*-m backend.microservices.*" -or $_.CommandLine -like "*-m uvicorn backend.microservices.*")
    } | ForEach-Object { $ours[[int]$_.ProcessId] = $true }
    $all | Where-Object {
        $ours.ContainsKey([int]$_.ProcessId) -or
        ($_.CommandLine -match "spawn_main\(parent_pid=(\d+)" -and $ours.ContainsKey([int]$Matches[1]))
    }
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

    Write-Host "`n--- Voice agent ---" -ForegroundColor Cyan
    $agentsUp = $false
    try {
        Invoke-WebRequest "http://127.0.0.1:8091/" -UseBasicParsing -TimeoutSec 5 | Out-Null
        Write-Host "  LiveKit Agents worker  up (:8091)" -ForegroundColor Green
        $agentsUp = $true
    } catch { Write-Host "  LiveKit Agents worker  down" -ForegroundColor DarkGray }
    $legacyUp = $false
    try {
        $q = Invoke-RestMethod "http://localhost:15672/api/queues/%2F/vocira_queue" -TimeoutSec 5 `
             -Headers @{ Authorization = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("guest:guest")) }
        $legacyUp = $q.consumers -ge 1
        $col = if ($legacyUp) { "Green" } else { "DarkGray" }
        Write-Host ("  legacy worker          consumers={0}  queued={1}  running={2}" -f $q.consumers, $q.messages_ready, $q.messages_unacknowledged) -ForegroundColor $col
    } catch { Write-Host "  Could not reach RabbitMQ" -ForegroundColor DarkGray }
    if (-not $agentsUp -and -not $legacyUp) { Write-Host "  no voice agent is running - no call will be answered" -ForegroundColor Red }

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

    # .tunnel-credentials.json stays: the next start reconnects the same
    # tunnel, with the same URL.
    Write-Host "Stopping tunnel..." -ForegroundColor Yellow
    Stop-Cloudflared
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

# ---------------------------------------------------------------------
# TUNNEL ONLY - services jaisi hain waisi rehti hain
# ---------------------------------------------------------------------
if ($TunnelOnly) {
    Write-Host "Cloudflare tunnel..." -ForegroundColor Cyan
    $url = Start-VociraTunnel
    Show-TunnelUrl $url
    # not the last curl's exit code (7 while the gateway is down)
    if ($url) { exit 0 } else { exit 1 }
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

# Which voice agent the livekit service hands calls to (VOICE_ENGINE).
$ENGINE = if ($LegacyWorker) { "legacy" } else { "agents" }

# Python writes UTF-8; read with the console's own code page, Urdu in the
# logs came out as mojibake.
function Start-Svc($title, $cmd, $logName) {
    $logPath = Join-Path $LOG_DIR "$logName.log"
    Start-Window "`$host.UI.RawUI.WindowTitle='$title'; [Console]::OutputEncoding=[Text.Encoding]::UTF8; `$env:PYTHONUNBUFFERED='1'; `$env:VOICE_ENGINE='$ENGINE'; Set-Location '$ROOT'; cmd /c '$cmd 2>&1' | Tee-Object -FilePath '$logPath'"
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

# LAZMI: the voice agent. Without it a call connects but nobody answers -
# the caller sits alone in the room.
#   default        the LiveKit Agents worker: LiveKit sends it into each
#                  call's room (the call token asks for it)
#   -LegacyWorker  the older worker: hears "session.created" on RabbitMQ
#                  and joins the room itself
if ($LegacyWorker) {
    Start-Svc "VOCIRA agent worker (legacy)" `
        "uv run --project $LK python -u -m backend.microservices.livekit_Rag_services.livekit_worker" `
        "agent-worker"
} else {
    Start-Svc "VOCIRA voice agent" `
        "uv run --project $LK python -u -m backend.microservices.livekit_Rag_services.services.agent.run start" `
        "voice-agent"
}

# ---------------------------------------------------------------------
# 5. CLOUDFLARE TUNNEL  (Start-VociraTunnel, upar)
# ---------------------------------------------------------------------
$tunnelUrl = $null

if ($WithTunnel) {
    Write-Host "`n[5/6] Cloudflare tunnel..." -ForegroundColor Cyan
    $tunnelUrl = Start-VociraTunnel
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

if ($LegacyWorker) {
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
} else {
    # Its health port answers once it is registered with LiveKit; loading
    # the voices and warming the knowledge search goes on for a few
    # seconds more, before the first call.
    Wait-Svc "voice-agent" "http://127.0.0.1:8091/" 120 | Out-Null
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
Show-TunnelUrl $tunnelUrl
