# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.1] - 2026-09-18

Initial release. Shared PostgreSQL for homemade apps, started with Docker Compose, plus a small FastHTML admin UI.

### Added

- PostgreSQL 16 in Docker Compose, with username, password, and database name set in `.env`.
- Web UI container (Python, FastHTML) on the same compose stack.
- Shared `users` table created on first start.
- First-run page to create the admin account.
- Login for admin accounts.
- Users page: list accounts and create new users for other apps (optional admin flag).
- Tables page: list tables, open a table (columns and first 100 rows).
- Export selected tables or the whole database as `.sql`.
- Import a `.sql` file into the database.
- Docker network named `home` and container name `homepostgresql-db` so other compose stacks can join and connect.
- Postgres published on all host interfaces so other machines on the same LAN can connect.
- `deploy.md` for running the stack with Docker Compose on Unraid.
- `.env.example` and optional compose override to store data on appdata.

### Notes

- Only admin users can log in to the UI. Other rows in `users` are meant for homemade apps that share this database.
- Dump and restore use `pg_dump` / `psql` at the same PostgreSQL major version as the database image.
