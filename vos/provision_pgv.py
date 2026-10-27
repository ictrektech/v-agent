"""Root-side PGV provisioning. Never executed inside an agent jail."""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
from pathlib import Path

import psycopg
from psycopg import sql


def main():
    namespace, uid = sys.argv[1], int(sys.argv[2])
    if not re.fullmatch("[0-9a-f]{40}", namespace) or uid < 20000:
        raise ValueError("Invalid tenant")
    root = Path(os.environ.get("DATA_ROOT", "/data"))
    private = root / "pgv-identities"
    private.mkdir(mode=0o700, exist_ok=True)
    path = private / (namespace + ".json")
    if path.exists():
        identity = json.loads(path.read_text())
    else:
        identity = {
            "user": "va_" + namespace[:24],
            "password": secrets.token_urlsafe(40),
            "database": "vagent_" + namespace,
            "schema": "public",
        }
        path.write_text(json.dumps(identity))
        path.chmod(0o600)
    host = os.environ.get("PGV_HOST", "shared-pgv")
    port = int(os.environ.get("PGV_PORT", "5432"))
    with psycopg.connect(
        host=host,
        port=port,
        user="postgres",
        dbname="postgres",
        password=os.environ["PGV_BOOTSTRAP_PASSWORD"],
        connect_timeout=5,
        autocommit=True,
    ) as connection:
        role = sql.Identifier(identity["user"])
        database = sql.Identifier(identity["database"])
        exists = connection.execute(
            "SELECT 1 FROM pg_roles WHERE rolname=%s", (identity["user"],)
        ).fetchone()
        if not exists:
            connection.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION"
                ).format(role, sql.Literal(identity["password"]))
            )
        else:
            connection.execute(
                sql.SQL(
                    "ALTER ROLE {} PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION"
                ).format(role, sql.Literal(identity["password"]))
            )
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s", (identity["database"],)
        ).fetchone()
        if not exists:
            connection.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(database, role))
        connection.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(database))
        connection.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(database, role))
    # Connect only with the tenant's ordinary role from this point onward.
    with psycopg.connect(
        host=host,
        port=port,
        user=identity["user"],
        dbname=identity["database"],
        password=identity["password"],
        connect_timeout=5,
        autocommit=True,
    ) as connection:
        connection.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        connection.execute("SELECT 1")
    target = root / "users" / namespace / ".vagent" / "pgv.json"
    target.write_text(json.dumps(dict(identity, host=host, port=port)))
    target.chmod(0o600)
    os.chown(target, uid, uid)
    print("PGV user database provisioned")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Database errors can contain connection details; do not print them.
        print("PGV provisioning unavailable: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None
