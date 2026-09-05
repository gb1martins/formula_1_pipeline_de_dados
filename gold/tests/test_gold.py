"""Testes de integração: exigem Gold materializada no MinIO local."""
from __future__ import annotations

import os
import duckdb
import pytest

BUCKET = os.getenv('MINIO_BUCKET', 'f1-data-lake')
ENDPOINT = os.getenv('MINIO_ENDPOINT', 'http://localhost:9000')
ACCESS = os.getenv('MINIO_ACCESS_KEY', 'admin')
SECRET = os.getenv('MINIO_SECRET_KEY', 'minioadmin123')


def con_gold():
    con = duckdb.connect()
    con.execute('INSTALL httpfs')
    con.execute('LOAD httpfs')
    con.execute(f"SET s3_endpoint='{ENDPOINT.replace('http://', '').replace('https://', '')}'")
    con.execute(f"SET s3_access_key_id='{ACCESS}'")
    con.execute(f"SET s3_secret_access_key='{SECRET}'")
    con.execute('SET s3_use_ssl=false')
    con.execute("SET s3_url_style='path'")
    return con


def table(con, name):
    path = f"s3://{BUCKET}/gold/{name}.parquet"
    try:
        con.execute(f"SELECT 1 FROM read_parquet('{path}') LIMIT 1")
    except Exception as exc:
        pytest.skip(f'Gold não materializada/localmente acessível: {exc}')
    return path


def test_pilot_race_grain():
    con = con_gold()
    try:
        path = table(con, 'fct_piloto_corrida')
        assert con.execute(f"SELECT COUNT(*) = COUNT(DISTINCT (race_key, driver_key)) FROM read_parquet('{path}')").fetchone()[0]
    finally:
        con.close()


def test_pace_metrics():
    con = con_gold()
    try:
        path = table(con, 'fct_piloto_corrida')
        assert con.execute(f"SELECT COUNT(*) = 0 FROM read_parquet('{path}') WHERE cobertura_ritmo_pct < 0 OR cobertura_ritmo_pct > 100").fetchone()[0]
        assert con.execute(f"SELECT COUNT(*) = 0 FROM read_parquet('{path}') WHERE voltas_analisadas > voltas_disponiveis").fetchone()[0]
    finally:
        con.close()


def test_pit_extremes_are_kept_and_classified():
    con = con_gold()
    try:
        path = table(con, 'fct_pit_stops')
        assert con.execute(f"SELECT COUNT(*) = 0 FROM read_parquet('{path}') WHERE duration_seconds > 60 AND NOT pit_stop_extremo").fetchone()[0]
        assert con.execute(f"SELECT COUNT(*) = 0 FROM read_parquet('{path}') WHERE duration_seconds <= 60 AND NOT pit_stop_convencional").fetchone()[0]
    finally:
        con.close()


def test_stint_grain():
    con = con_gold()
    try:
        path = table(con, 'fct_stints')
        assert con.execute(f"SELECT COUNT(*) = COUNT(DISTINCT (race_key, driver_key, stint_number)) FROM read_parquet('{path}')").fetchone()[0]
    finally:
        con.close()
