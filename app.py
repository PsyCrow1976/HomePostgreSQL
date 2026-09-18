import hashlib
import os
import re
import secrets
import subprocess
import time
from urllib.parse import quote_plus

import psycopg
from fasthtml.common import *
from psycopg import sql
from starlette.datastructures import UploadFile
from starlette.responses import RedirectResponse, Response

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_IMPORT_BYTES = 50 * 1024 * 1024

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "homepostgresql-db")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_USER = os.environ["POSTGRES_USER"]
POSTGRES_PASSWORD = os.environ["POSTGRES_PASSWORD"]
POSTGRES_DB = os.environ["POSTGRES_DB"]
SESSION_SECRET = os.environ["SESSION_SECRET"]


def connect():
    return psycopg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        dbname=POSTGRES_DB,
        autocommit=True,
    )


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, hashed = stored.split("$", 1)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return secrets.compare_digest(dk.hex(), hashed)


def init_db():
    last = None
    for _ in range(30):
        try:
            with connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            return
        except Exception as exc:
            last = exc
            time.sleep(1)
    raise RuntimeError(f"could not connect to postgres: {last}")


def admin_exists() -> bool:
    with connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM users WHERE is_admin").fetchone()[0]
    return n > 0


def pg_env():
    env = os.environ.copy()
    env["PGPASSWORD"] = POSTGRES_PASSWORD
    env["PGHOST"] = POSTGRES_HOST
    env["PGPORT"] = str(POSTGRES_PORT)
    env["PGUSER"] = POSTGRES_USER
    env["PGDATABASE"] = POSTGRES_DB
    return env


def valid_ident(name: str) -> bool:
    return bool(IDENT.match(name or ""))


def parse_table_ref(value: str):
    parts = (value or "").split(".")
    if len(parts) != 2:
        return None
    schema, table = parts
    if not valid_ident(schema) or not valid_ident(table):
        return None
    return schema, table


def listed_tables():
    with connect() as conn:
        return conn.execute(
            """
            SELECT schemaname, relname, n_live_tup
            FROM pg_stat_user_tables
            ORDER BY schemaname, relname
            """
        ).fetchall()


def table_exists(schema: str, table: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s AND table_type = 'BASE TABLE'
            """,
            (schema, table),
        ).fetchone()
    return row is not None


def dump_sql(tables=None) -> bytes:
    cmd = ["pg_dump", "--no-owner", "--no-acl", "--clean", "--if-exists"]
    if tables:
        for schema, table in tables:
            cmd.extend(["-t", f"{schema}.{table}"])
    result = subprocess.run(cmd, env=pg_env(), capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace") or "pg_dump failed")
    return result.stdout


def sql_download(content: bytes, filename: str):
    return Response(
        content,
        media_type="application/sql",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def redirect_home(msg=None, err=None):
    q = []
    if msg:
        q.append(f"msg={quote_plus(msg)}")
    if err:
        q.append(f"err={quote_plus(err[:300])}")
    suffix = ("?" + "&".join(q)) if q else ""
    return RedirectResponse("/" + suffix, status_code=303)


def auth(req, session):
    path = req.url.path
    if path in ("/health", "/favicon.ico") or path.startswith("/static"):
        return
    if not admin_exists():
        if path != "/setup":
            return RedirectResponse("/setup", status_code=303)
        return
    if path == "/setup":
        return RedirectResponse("/login", status_code=303)
    if not session.get("user_id") and path != "/login":
        return RedirectResponse("/login", status_code=303)


app, rt = fast_app(
    secret_key=SESSION_SECRET,
    before=Beforeware(auth, skip=["/health", "/favicon.ico"]),
    hdrs=(
        Style(
            """
            main { max-width: 960px; margin: 2rem auto; padding: 0 1rem; }
            .msg { background: #eef; padding: 0.6rem 0.8rem; }
            .err { background: #fdd; padding: 0.6rem 0.8rem; }
            .rows { overflow-x: auto; }
            """
        ),
    ),
)


def layout(*content, title="HomePostgreSQL", session=None, msg=None, err=None):
    nav = None
    if session and session.get("user_id"):
        nav = P(
            A("Tables", href="/"),
            " | ",
            A("Logout", href="/logout"),
            f"  ({session.get('username', '')})",
        )
    bits = [H1("HomePostgreSQL")]
    if nav:
        bits.append(nav)
    if title != "HomePostgreSQL":
        bits.append(H2(title))
    if msg:
        bits.append(P(msg, cls="msg"))
    if err:
        bits.append(P(err, cls="err"))
    bits.extend(content)
    return Title(title), Main(*bits)


@rt("/health", methods=["GET"])
def health():
    return {"status": "ok"}


@rt("/setup", methods=["GET"])
def setup_get():
    return layout(
        Form(
            Label("Username", Input(name="username", required=True, autofocus=True)),
            Label("Password", Input(name="password", type="password", required=True)),
            Label("Confirm password", Input(name="confirm", type="password", required=True)),
            Button("Create admin"),
            method="post",
            action="/setup",
        ),
        title="Create admin account",
    )


@rt("/setup", methods=["POST"])
def setup_post(username: str, password: str, confirm: str):
    if admin_exists():
        return RedirectResponse("/login", status_code=303)
    username = (username or "").strip()
    err = None
    if not username:
        err = "Username is required."
    elif len(password or "") < 8:
        err = "Password must be at least 8 characters."
    elif password != confirm:
        err = "Passwords do not match."
    if err:
        return layout(P(err, cls="err"), A("Back", href="/setup"), title="Create admin account")
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO users (username, password_hash, is_admin)
            VALUES (%s, %s, TRUE)
            """,
            (username, hash_password(password)),
        )
    return RedirectResponse("/login", status_code=303)


@rt("/login", methods=["GET"])
def login_get():
    return layout(
        Form(
            Label("Username", Input(name="username", required=True, autofocus=True)),
            Label("Password", Input(name="password", type="password", required=True)),
            Button("Log in"),
            method="post",
            action="/login",
        ),
        title="Log in",
    )


@rt("/login", methods=["POST"])
def login_post(session, username: str, password: str):
    username = (username or "").strip()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, username, password_hash
            FROM users
            WHERE username = %s AND is_admin
            """,
            (username,),
        ).fetchone()
    if not row or not verify_password(password or "", row[2]):
        return layout(
            P("Wrong username or password.", cls="err"),
            Form(
                Label("Username", Input(name="username", required=True, value=username)),
                Label("Password", Input(name="password", type="password", required=True, autofocus=True)),
                Button("Log in"),
                method="post",
                action="/login",
            ),
            title="Log in",
        )
    session["user_id"] = row[0]
    session["username"] = row[1]
    return RedirectResponse("/", status_code=303)


@rt("/logout", methods=["GET"])
def logout(session):
    session.clear()
    return RedirectResponse("/login", status_code=303)


@rt("/", methods=["GET"])
def home(session, msg: str = "", err: str = ""):
    tables = listed_tables()
    if not tables:
        table_list = P("No user tables yet.")
    else:
        rows = []
        for schema, name, n in tables:
            ref = f"{schema}.{name}"
            rows.append(
                Tr(
                    Td(Input(type="checkbox", name="tables", value=ref)),
                    Td(A(ref, href=f"/table/{schema}/{name}")),
                    Td(str(n)),
                )
            )
        table_list = Form(
            Table(
                Thead(Tr(Th(""), Th("Table"), Th("Rows (approx)"))),
                Tbody(*rows),
            ),
            P(
                Button("Export selected tables", formaction="/export/tables", formmethod="post"),
                " ",
                Button("Export whole database", formaction="/export/all", formmethod="post"),
            ),
            method="post",
        )
    return layout(
        table_list,
        H3("Import"),
        P("Upload a .sql file from a previous export. This runs the SQL on the database."),
        Form(
            Input(type="file", name="file", accept=".sql,text/plain", required=True),
            Button("Import"),
            method="post",
            action="/import",
            enctype="multipart/form-data",
        ),
        title="Tables",
        session=session,
        msg=msg or None,
        err=err or None,
    )


@rt("/table/{schema}/{name}", methods=["GET"])
def show_table(session, schema: str, name: str):
    if not valid_ident(schema) or not valid_ident(name) or not table_exists(schema, name):
        return layout(P("Unknown table.", cls="err"), A("Back", href="/"), title="Table", session=session)
    with connect() as conn:
        cols = conn.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema, name),
        ).fetchall()
        cur = conn.execute(
            sql.SQL("SELECT * FROM {}.{} LIMIT 100").format(
                sql.Identifier(schema), sql.Identifier(name)
            )
        )
        col_names = [d.name for d in cur.description]
        data = cur.fetchall()
    head = Thead(Tr(*[Th(c) for c in col_names]))
    body = Tbody(*[Tr(*[Td("" if v is None else str(v)) for v in row]) for row in data])
    return layout(
        P(A("Back", href="/")),
        H3("Columns"),
        Ul(*[Li(f"{c} ({t})") for c, t in cols]),
        H3("Rows (first 100)"),
        Div(Table(head, body) if data else P("No rows."), cls="rows"),
        title=f"{schema}.{name}",
        session=session,
    )


@rt("/export/all", methods=["POST"])
def export_all(session):
    try:
        data = dump_sql()
    except RuntimeError as exc:
        return redirect_home(err=str(exc))
    return sql_download(data, f"{POSTGRES_DB}.sql")


@rt("/export/tables", methods=["POST"])
async def export_tables(request, session):
    form = await request.form()
    tables = []
    for ref in form.getlist("tables"):
        parsed = parse_table_ref(ref)
        if parsed and table_exists(*parsed):
            tables.append(parsed)
    if not tables:
        return redirect_home(err="Select at least one table")
    try:
        data = dump_sql(tables)
    except RuntimeError as exc:
        return redirect_home(err=str(exc))
    names = "_".join(t for _, t in tables[:5])
    return sql_download(data, f"{POSTGRES_DB}-{names}.sql")


@rt("/import", methods=["POST"])
async def import_sql(request, session):
    form = await request.form()
    upload = form.get("file")
    if not isinstance(upload, UploadFile) or not upload.filename:
        return redirect_home(err="Choose a .sql file")
    data = await upload.read()
    if not data:
        return redirect_home(err="File is empty")
    if len(data) > MAX_IMPORT_BYTES:
        return redirect_home(err="File is too large (50MB max)")
    result = subprocess.run(
        ["psql", "-v", "ON_ERROR_STOP=1"],
        input=data,
        env=pg_env(),
        capture_output=True,
    )
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace")
        return redirect_home(err=err)
    return redirect_home(msg="Import finished")


if __name__ == "__main__":
    init_db()
    serve(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), reload=False)
