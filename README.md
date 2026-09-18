# HomePostgreSQL

Shared PostgreSQL for homemade apps on the Unraid home server.

GitHub: [https://github.com/PsyCrow1976/HomePostgreSQL](https://github.com/PsyCrow1976/HomePostgreSQL)

## Purpose

One PostgreSQL in Docker, started with Docker Compose. It is the main database for homemade apps on the home Unraid server, instead of each app running its own database.

Database username and password are set in the compose `.env` file.

The first database is a shared **users** database. Other apps can use those accounts.

The first time the stack starts, a simple Python + FastHTML web page is used to create the admin account for that user database.

After that you can log in to the same UI, create users for other apps, see the tables in the database, and backup (export) or restore (import) selected tables or the whole home database.

Keep it simple. No extra services.

## Intended usage

1. Deploy on Unraid with Docker Compose. See [deploy.md](deploy.md).
2. Set `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` in `.env`.
3. Start the stack.
4. Open the web UI and create the admin user (first start only).
5. Log in, create users, look at tables, export or import as needed.
6. Point other home apps at this Postgres host and port.

## Stack

| Container | Role |
|-----------|------|
| `homepostgresql-db` | PostgreSQL |
| `homepostgresql-web` | FastHTML UI (Python): first-time admin setup, login, users, table list, backup and restore |

Postgres listens on all host addresses (`0.0.0.0`) and sits on a Docker network named `home`.

| Who | How to connect |
|-----|----------------|
| Web UI on the LAN | `http://192.168.*.*:8087` |
| PC, phone, or other device on the LAN (Postgres) | `192.168.*.*:5432` |
| Other Docker containers on Unraid | Join the `home` network, host `homepostgresql-db`, port `5432` |

User, password, and database name come from `.env`.

## Unraid

See **[deploy.md](deploy.md)** for how to run it on the Unraid server.
