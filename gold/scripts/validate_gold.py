"""Validação da Gold já materializada no MinIO."""
from __future__ import annotations

import os
import duckdb

BUCKET = os.getenv("MINIO_BUCKET", "f1-data-lake")
ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
ACCESS = os.getenv("MINIO_ACCESS_KEY", "admin")
SECRET = os.getenv("MINIO_SECRET_KEY", "minioadmin123")

TABLES = [
    "dim_corrida", "dim_piloto", "dim_equipe",
    "fct_piloto_corrida", "fct_voltas", "fct_pit_stops", "fct_stints", "fct_clima",
]


def main() -> None:
    con = duckdb.connect()
    try:
        con.execute("INSTALL httpfs")
        con.execute("LOAD httpfs")
        con.execute(f"SET s3_endpoint='{ENDPOINT.replace('http://', '').replace('https://', '')}'")
        con.execute(f"SET s3_access_key_id='{ACCESS}'")
        con.execute(f"SET s3_secret_access_key='{SECRET}'")
        con.execute("SET s3_use_ssl=false")
        con.execute("SET s3_url_style='path'")
        for table in TABLES:
            path = f"s3://{BUCKET}/gold/{table}.parquet"
            rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{path}')").fetchone()[0]
            print(f"{table}: {rows} registros")
    finally:
        con.close()


if __name__ == "__main__":
    main()
