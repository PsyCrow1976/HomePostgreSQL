# Deploy HomePostgreSQL on Unraid

PostgreSQL and a small web UI, started with Docker Compose. Reachable from the home LAN and from other Unraid containers.

**Server:** `192.168.*.*`  
**Web UI:** `http://192.168.*.*:8087`  
**Postgres (LAN):** `192.168.*.*:5432`  
**Postgres (other Unraid containers):** host `homepostgresql-db` on network `home`

| Container | Role |
|-----------|------|
| `homepostgresql-db` | PostgreSQL, published on the LAN and on Docker network `home` |
| `homepostgresql-web` | FastHTML UI on port `8087` |

See **[README.md](README.md)** for what this is for. This file is only how to run it on Unraid.

---

## Prerequisites

SSH in:

```bash
ssh user@192.168.*.*
```

Need Docker, `docker compose`, and git. Ports **5432** and **8087** must be free on Unraid (or change `POSTGRES_PORT` / `HTTP_PORT` in `.env`).

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
SESSION_SECRET=your-long-random-string
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

You want `homepostgresql-db` **healthy** and `homepostgresql-web` **Up**.

Compose Manager: stack path `/mnt/user/appdata/homepostgresql/docker-compose.yml`, env path `/mnt/user/appdata/homepostgresql/.env`.

### 5. First start — admin account

Open `http://192.168.*.*:8087`.

The first time, the UI asks you to create the admin account for the shared `users` table. After that, log in with that account to see tables and to export or import.

---

## Using it from other apps

User, password, and database are the values in `.env`.

### Devices on the home network (PC, phone, another machine)

Connect to **`192.168.*.*:5432`**.

The compose file binds Postgres to `0.0.0.0`, so it is reachable on the Unraid LAN IP, not only localhost.

### Other Docker containers on Unraid (preferred)

Join the existing Docker network named `home` and use host **`homepostgresql-db`** port **`5432`**.

In the other app’s `docker-compose.yml`:

```yaml
services:
  web:
    networks:
      - default
      - home
    environment:
      DATABASE_URL: postgresql://home:your-strong-db-password@homepostgresql-db:5432/home

networks:
  home:
    external: true
    name: home
```

Inside Docker the port is always `5432`. `POSTGRES_PORT` only changes the LAN port on Unraid.

### Other Docker containers via the LAN IP

You can also use `192.168.*.*:5432` from a container. On Unraid that often needs **Settings → Docker → Host access to custom networks → Enabled**. Joining the `home` network above avoids that.

---

## Later updates

```bash
cd /mnt/user/appdata/homepostgresql
git pull
docker compose up -d --build
```

---

## Backup and restore

Use the web UI to export selected tables or the whole database, and to import a `.sql` file.

Full dump from the command line:

```bash
cd /mnt/user/appdata/homepostgresql
docker compose exec db pg_dump -U home home > backup-$(date +%F).sql
```

Also copy the `postgres/` folder if you used step 3.

---

## Troubleshooting

**Database or UI not up** — wait a bit, then:

```bash
docker compose logs db --tail 50
docker compose logs web --tail 50
```

**Port in use** — change `POSTGRES_PORT` or `HTTP_PORT` in `.env` and run `docker compose up -d` again. LAN clients must use the new Postgres port. Containers on the `home` network still use `5432`.

**Other container cannot connect** — confirm it is on the `home` network (`docker network inspect home`) and the host name is `homepostgresql-db`.

**Wipe the database and start empty again** (keeps the git folder):

```bash
cd /mnt/user/appdata/homepostgresql
docker compose down
rm -rf postgres
mkdir -p postgres
docker volume rm homepostgresql_postgres_data 2>/dev/null || true
docker compose up -d --build
```
