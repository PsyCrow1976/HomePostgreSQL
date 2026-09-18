# Deploy HomePostgreSQL on Unraid

PostgreSQL plus a small web UI, started with Docker Compose.

**Server:** `192.168.1.130`  
**UI:** `http://192.168.1.130:8087`  
**Postgres:** `192.168.1.130:5432`

| Container | Role |
|-----------|------|
| `db` | PostgreSQL |
| `web` | FastHTML UI on port `8087` |

See **[README.md](README.md)** for what this is for. This file is only how to run it on Unraid.

---

## Prerequisites

SSH in:

```bash
ssh root@192.168.1.130
```

Need Docker, `docker compose`, and git. Ports **8087** and **5432** must be free.

```bash
docker compose version
git --version
```

If Compose is missing, Unraid **Apps** → **Compose Manager Plus**.

---

## Install

### 1. Folder and clone

```bash
mkdir -p /mnt/user/appdata/homepostgresql
cd /mnt/user/appdata/homepostgresql
git clone https://github.com/PsyCrow1976/HomePostgreSQL.git .
```

The trailing `.` clones **into this folder**. Confirm you see `docker-compose.yml`, `.env.example`, and `deploy.md`.

### 2. Passwords (`.env`)

```bash
cp .env.example .env
nano .env
```

Set the database user, password, and database name. Other home apps will use these to connect.

```env
HTTP_PORT=8087
POSTGRES_PORT=5432
POSTGRES_USER=home
POSTGRES_PASSWORD=your-strong-db-password
POSTGRES_DB=home
TZ=Europe/Copenhagen
```

Save: `Ctrl+O`, Enter, `Ctrl+X`.

### 3. Store data on appdata

```bash
mkdir -p /mnt/user/appdata/homepostgresql/postgres
```

If a compose override example exists:

```bash
cp docker-compose.override.example.yml docker-compose.override.yml
```

That keeps Postgres files on the Unraid share so backups are obvious.

### 4. Start

```bash
cd /mnt/user/appdata/homepostgresql
docker compose up -d --build
docker compose ps
```

You want `db` **healthy** and `web` **Up**.

Compose Manager: stack path `/mnt/user/appdata/homepostgresql/docker-compose.yml`, env path `/mnt/user/appdata/homepostgresql/.env`.

### 5. First start — admin account

Open `http://192.168.1.130:8087`.

The first time, the UI asks you to create the admin account for the shared user database. After that, log in with that account.

---

## Using it from other apps

Other homemade apps on the same Unraid box can connect with:

- **Host:** `192.168.1.130` (or the Docker host name if they share a network)
- **Port:** `5432`
- **User / password / database:** the values in `.env`

---

## Later updates

```bash
cd /mnt/user/appdata/homepostgresql
git pull
docker compose up -d --build
```

---

## Backup and restore

Use the web UI to export or import selected tables or the whole home database.

From the command line, a full dump:

```bash
cd /mnt/user/appdata/homepostgresql
docker compose exec db pg_dump -U home home > backup-$(date +%F).sql
```

Also copy the `postgres/` folder if you used step 3.

---

## Troubleshooting

**UI not up** — wait a bit, then:

```bash
docker compose logs web --tail 50
docker compose logs db --tail 50
```

**Port in use** — change `HTTP_PORT` or `POSTGRES_PORT` in `.env` and run `docker compose up -d` again.

**Wipe the database and start empty again** (keeps the git folder):

```bash
cd /mnt/user/appdata/homepostgresql
docker compose down
rm -rf postgres
mkdir -p postgres
docker volume rm homepostgresql_postgres_data 2>/dev/null || true
docker compose up -d --build
```

Then open the UI again and create the admin account.
