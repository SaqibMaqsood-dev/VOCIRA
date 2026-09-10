# VOCIRA — free deployment

The whole system on a single always-free VM, with the frontend on Vercel.

| Part | Where |
|---|---|
| Next.js frontend | Vercel (free) |
| gateway, auth, livekit_Rag, worker | Oracle Cloud "Always Free" VM |
| Postgres, Redis, RabbitMQ, LiveKit server | the same VM |
| ERPNext (all containers) | the same VM |
| HTTPS + reverse proxy | Caddy, on the same VM |
| Whisper / LLM / embeddings / vector DB | Groq, Gemini, Pinecone (already external) |

Only Oracle's **Ampere A1** shape (4 OCPU / 24 GB RAM) gives you a free VM
large enough to run this whole stack at once. The full stack needs roughly
**4–5 GB RAM**, so there is plenty of headroom.

---

## What is in this folder

| File | Purpose |
|---|---|
| `docker-compose.prod.yml` | the whole VOCIRA stack + Caddy |
| `Dockerfile.backend` | gateway + livekit_Rag + worker (one image) |
| `Dockerfile.auth` | auth service (light image) |
| `Caddyfile` | reverse proxy + automatic HTTPS |
| `livekit.yaml` | the LiveKit server's production config |
| `erpnext-edge.override.yml` | the override that joins ERPNext to Caddy |
| `gen-secrets.py` | generates `.env.prod` (new secrets + existing API keys) |
| `.env.example` | template (stays in git, holds no real secret) |
| `.env.prod` | the real values — **gitignored**, must never be committed |

---

## How this differs from local

| | Local | Production |
|---|---|---|
| Postgres / Redis / RabbitMQ ports | open on the host (5433 / 6380 / 5672) | **closed** — inside Docker only |
| RabbitMQ login | `guest / guest` | own user + random password |
| LiveKit | `--dev` (well-known devkey/secret) | own keys, `use_external_ip` |
| JWT secret | 6 bytes | 64 bytes |
| CORS | `*` | your Vercel domain only |
| HTTPS | none | Caddy + Let's Encrypt |

---

## Step by step

### 1. Generate the secrets (now, on your own machine)

```bash
python deploy/gen-secrets.py
```

This creates `deploy/.env.prod`: strong new secrets, plus the API keys
carried over from your existing `.env` files.

Then fill in these four by hand in that file:

```env
DOMAIN=vocira.example.com
ACME_EMAIL=you@example.com
CORS_ORIGINS=https://vocira.vercel.app
ERP_BASE_URL=http://erpnext:8080
```

If you have a real domain, that is all you need — `api.<DOMAIN>`,
`rt.<DOMAIN>`, `lk.<DOMAIN>` and `erp.<DOMAIN>` are built from it
automatically. On a free service like DuckDNS there is no wildcard —
each name is one flat registration — so add these four instead, once
you have registered the four names in step 4:

```env
API_DOMAIN=api-vocira.duckdns.org
RT_DOMAIN=rt-vocira.duckdns.org
LK_DOMAIN=lk-vocira.duckdns.org
ERP_DOMAIN=erp-vocira.duckdns.org
```

With all four set, `DOMAIN` itself is never actually used — leave it
as whatever `gen-secrets.py` filled in.

> `JWT_SECRET_KEY` is now 64 bytes. The old one was 6 bytes — on the
> internet that can be brute-forced, letting anyone mint an admin token.

### 2. A VM on Oracle Cloud

- Shape: **VM.Standard.A1.Flex**, 4 OCPU / 24 GB (Always Free)
- Image: Ubuntu 22.04 or 24.04
- Boot volume: 100 GB+ (the images are large)

On the VM:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # then log in again
```

### 3. Open the ports — **in both places**

Oracle has two separate firewalls, and nothing works until both are open.
This is the single biggest time-waster here.

**(a) VCN → Security List → Ingress Rules:**

| Port | Protocol | What for |
|---|---|---|
| 80 | TCP | Let's Encrypt's HTTP challenge |
| 443 | TCP | HTTPS + all WebSockets |
| 7881 | TCP | LiveKit's TCP fallback (when UDP is blocked) |
| 7882 | **UDP** | **LiveKit's actual audio (RTP)** |

**(b) The firewall inside the VM:**

Oracle's Ubuntu image ships with its own iptables rules, and they are
separate from the Security List — both have to be opened.

```bash
sudo apt-get install -y iptables-persistent

sudo iptables -I INPUT -p tcp -m multiport --dports 80,443,7881 -j ACCEPT
sudo iptables -I INPUT -p udp --dport 7882 -j ACCEPT

sudo netfilter-persistent save    # or the rules are lost on reboot
```

> **What happens if you forget 7882/UDP:** the call hangs at
> "connecting". Signalling connects (that runs on 443), so everything
> looks fine — but the audio has no route at all.

### 4. DNS

**With your own domain**, four subdomains, all pointing at the VM's
public IP:

```
api.<domain>    →  <VM public IP>
rt.<domain>     →  <VM public IP>
lk.<domain>     →  <VM public IP>
erp.<domain>    →  <VM public IP>
```

`*.<domain>` covers all four in one DNS record.

**With DuckDNS** (free, no domain purchase needed): DuckDNS gives out
one flat name per registration, not a wildcard, so register four
separate names at [duckdns.org](https://www.duckdns.org) — sign in,
pick a base like `vocira`, and add these four in the dashboard, each
pointed at the VM's public IP:

```
api-vocira.duckdns.org
rt-vocira.duckdns.org
lk-vocira.duckdns.org
erp-vocira.duckdns.org
```

Then set `API_DOMAIN` / `RT_DOMAIN` / `LK_DOMAIN` / `ERP_DOMAIN` to
these in `.env.prod` (step 1) — `docker-compose.prod.yml` and the
`Caddyfile` both read from those, so nothing else needs editing.

Oracle's default public IP is ephemeral: stopping and starting the
instance can change it. Reserve a **Reserved Public IP** in the
console (still free) before pointing DNS at it, or DuckDNS's records
will need updating every time the VM restarts.

### 5. Code and secrets onto the VM

```bash
git clone <your repo> vocira
cd vocira
```

`deploy/.env.prod` is deliberately not in git — send it separately:

```bash
scp deploy/.env.prod ubuntu@<VM IP>:~/vocira/deploy/.env.prod
```

### 6. Shared network, then start the stack

```bash
docker network create vocira-edge

docker compose -f deploy/docker-compose.prod.yml \
               --env-file deploy/.env.prod \
               up -d --build
```

The first build can take 15–25 minutes (in the backend image, packages
like librosa/numba sometimes build from source on ARM).

### 7. ERPNext

```bash
cd frappe_test
docker compose -f pwd.yml -f ../deploy/erpnext-edge.override.yml up -d
```

The override does two things: it brings ERPNext onto the `vocira-edge`
network (so Caddy can find it by the name `erpnext`), and it removes the
host port 8081 — otherwise ERPNext would also stay open on
`http://<IP>:8081` with no HTTPS.

Your existing ERPNext data is restored from the `frappe_test/*.sql.gz` and
`*.tar` backups:

```bash
docker compose -f pwd.yml exec backend \
  bench --site frontend restore /path/to/database.sql.gz \
  --with-public-files /path/to/files.tar \
  --with-private-files /path/to/private-files.tar
```

### 8. The frontend on Vercel

Import the repo on Vercel, set **Root Directory** to `frontend`, and add
two environment variables:

```
NEXT_PUBLIC_API_URL       = https://api.<domain>
NEXT_PUBLIC_REALTIME_URL  = https://rt.<domain>
```

Once it deploys, put the URL Vercel gives you into `CORS_ORIGINS` in
`.env.prod` and restart the gateway:

```bash
docker compose -f deploy/docker-compose.prod.yml \
               --env-file deploy/.env.prod up -d gateway
```

### 9. The first admin

```bash
docker compose -f deploy/docker-compose.prod.yml \
               --env-file deploy/.env.prod \
               exec auth python create_admin.py
```

### 10. Checks

- `https://api.<domain>/docs` opens
- you can log in on the frontend
- one voice call — audio arrives in both directions (this is where a UDP
  problem shows up)
- ask the assistant to "connect me to a human" — the admin panel rings
- ERPNext login at `https://erp.<domain>`

---

## Things that can trip you up

**ARM (aarch64).** This Oracle VM is ARM, not x86. Postgres, Redis,
RabbitMQ, MariaDB and Caddy all run fine on ARM. Watch the
`livekit/livekit-server` image, and `llvmlite`/`numba`, which come with
`librosa` — ARM wheels for these are usually available, but when they are
not, the build gets long. If the LiveKit image will not run on ARM at
all, move just that one to **LiveKit Cloud**'s free tier — changing
`LIVEKIT_URL`, `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` is enough, and
no code changes.

**Users behind very restrictive networks.** UDP plus the TCP fallback
covers most places. If a corporate or college firewall still causes
trouble, you will need TURN — and there too the simplest route is LiveKit
Cloud.

**Image size.** The backend image is roughly 4–5 GB because
`pyproject.toml` includes `torch`, `sentence-transformers` and
`faster-whisper`. You use `EMBEDDING_PROVIDER=gemini` and Groq Whisper, so
none of those three are even imported at runtime — moving them into an
optional dependency group would make the image considerably smaller. Not
necessary; it would just speed up the build.

**Backups.** Postgres data lives in the `pgdata` volume, ERPNext's in its
own volumes. Nothing is backed up automatically on the free tier:

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.prod \
  exec postgres pg_dump -U vocira vocira | gzip > vocira-$(date +%F).sql.gz
```
