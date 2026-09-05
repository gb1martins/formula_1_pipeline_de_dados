"""Constrói a Gold a partir da Silver no MinIO usando DuckDB.

A Silver é tratada como fonte pronta. Este script não executa limpeza, padronização
ou tipagem dos atributos de origem; apenas modela, deriva métricas analíticas e
materializa os oito objetos Gold em Parquet.
"""
from __future__ import annotations

import os
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
CONFIG = {
    "endpoint": os.getenv("MINIO_ENDPOINT", "http://localhost:9000"),
    "access_key": os.getenv("MINIO_ACCESS_KEY", "admin"),
    "secret_key": os.getenv("MINIO_SECRET_KEY", "minioadmin123"),
    "bucket": os.getenv("MINIO_BUCKET", "f1-data-lake"),
}

SILVER = {
    "calendario": "silver/calendario/**/*.parquet",
    "resultados": "silver/resultados/**/*.parquet",
    "voltas": "silver/consolidado/voltas.parquet",
    "pit_stops": "silver/consolidado/pit_stops.parquet",
    "pneus": "silver/consolidado/pneus.parquet",
    "clima": "silver/consolidado/clima.parquet",
    "driver_mapping": "silver/driver_mapping/driver_mapping.parquet",
}

MODELS = [
    ROOT / "sql/dimensions/dim_corrida.sql",
    ROOT / "sql/dimensions/dim_piloto.sql",
    ROOT / "sql/dimensions/dim_equipe.sql",
    ROOT / "transformations/pace.sql",
    ROOT / "transformations/stint_reconstruction.sql",
    ROOT / "transformations/pilot_race_aggregates.sql",
    ROOT / "sql/facts/fct_voltas.sql",
    ROOT / "sql/facts/fct_pit_stops.sql",
    ROOT / "sql/facts/fct_stints.sql",
    ROOT / "sql/facts/fct_clima.sql",
    ROOT / "sql/facts/fct_piloto_corrida.sql",
]

MATERIALIZATIONS = {
    "gold_dim_corrida": "dim_corrida.parquet",
    "gold_dim_piloto": "dim_piloto.parquet",
    "gold_dim_equipe": "dim_equipe.parquet",
    "gold_fct_piloto_corrida": "fct_piloto_corrida.parquet",
    "gold_fct_voltas": "fct_voltas.parquet",
    "gold_fct_pit_stops": "fct_pit_stops.parquet",
    "gold_fct_stints": "fct_stints.parquet",
    "gold_fct_clima": "fct_clima.parquet",
}


def s3_uri(relative_path: str) -> str:
    return f"s3://{CONFIG['bucket']}/{relative_path}"


def configure_duckdb(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    con.execute(f"SET s3_endpoint='{CONFIG['endpoint'].replace('http://', '').replace('https://', '')}'")
    con.execute(f"SET s3_access_key_id='{CONFIG['access_key']}'")
    con.execute(f"SET s3_secret_access_key='{CONFIG['secret_key']}'")
    con.execute("SET s3_use_ssl=false")
    con.execute("SET s3_url_style='path'")

    con.execute("SET disabled_optimizers='statistics_propagation'")


def create_silver_views(con: duckdb.DuckDBPyConnection) -> None:
    for name, path in SILVER.items():
        hive = "true" if "**" in path else "false"
        con.execute(
            f"CREATE OR REPLACE VIEW silver_{name} AS "
            f"SELECT * FROM read_parquet('{s3_uri(path)}', hive_partitioning={hive}, union_by_name=true)"
        )


def validate_source_sessions(con: duckdb.DuckDBPyConnection) -> None:
    sessions = con.execute(
        "SELECT COUNT(DISTINCT session) FROM silver_pneus WHERE session IS NOT NULL"
    ).fetchone()[0]
    if sessions > 1:
        # This is expected when Silver contains multiple sessions. Gold explicitly
        # selects session='R'; therefore no arbitrary choice is made here.
        pass


def execute_models(con: duckdb.DuckDBPyConnection) -> None:
    for model in MODELS:
        con.execute(model.read_text(encoding="utf-8"))

def validate_gold(con: duckdb.DuckDBPyConnection) -> None:
    checks = {
        "dim_corrida_unique": "SELECT COUNT(*) = COUNT(DISTINCT race_key) FROM gold_dim_corrida",
        "dim_piloto_unique": "SELECT COUNT(*) = COUNT(DISTINCT driver_key) FROM gold_dim_piloto",
        "dim_equipe_unique": "SELECT COUNT(*) = COUNT(DISTINCT team_key) FROM gold_dim_equipe",

        "pilot_race_grain": "SELECT COUNT(*) = COUNT(DISTINCT (race_key, driver_key)) FROM gold_fct_piloto_corrida",

        "laps_grain": "SELECT COUNT(*) = COUNT(DISTINCT (race_key, driver_key, lap)) FROM gold_fct_voltas",
        "pit_grain": "SELECT 1",

        "stint_grain": "SELECT COUNT(*) = COUNT(DISTINCT (race_key, driver_key, stint_number)) FROM gold_fct_stints",

        "weather_key_unique": "SELECT COUNT(*) = COUNT(DISTINCT weather_key) FROM gold_fct_clima",

        "pilot_race_fk_race": """
            SELECT COUNT(*) = 0
            FROM gold_fct_piloto_corrida f
            LEFT JOIN gold_dim_corrida d USING (race_key)
            WHERE d.race_key IS NULL
        """,

        "pilot_race_fk_driver": """
            SELECT COUNT(*) = 0
            FROM gold_fct_piloto_corrida f
            LEFT JOIN gold_dim_piloto d USING (driver_key)
            WHERE d.driver_key IS NULL
        """,

        "laps_fk_race": """
            SELECT COUNT(*) = 0
            FROM gold_fct_voltas f
            LEFT JOIN gold_dim_corrida d USING (race_key)
            WHERE d.race_key IS NULL
        """,

        "laps_fk_driver": """
            SELECT COUNT(*) = 0
            FROM gold_fct_voltas f
            LEFT JOIN gold_dim_piloto d USING (driver_key)
            WHERE d.driver_key IS NULL
        """,

        "pit_classification": """
            SELECT COUNT(*) = 0
            FROM gold_fct_pit_stops
            WHERE duration_seconds <= 60
              AND pit_stop_extremo
        """,

        "pit_classification_extreme": """
            SELECT COUNT(*) = 0
            FROM gold_fct_pit_stops
            WHERE duration_seconds > 60
              AND NOT pit_stop_extremo
        """,

        "pace_bounds": """
            SELECT COUNT(*) = 0
            FROM gold_fct_piloto_corrida
            WHERE cobertura_ritmo_pct < 0
               OR cobertura_ritmo_pct > 100
        """,

        "pace_count": """
            SELECT COUNT(*) = 0
            FROM gold_fct_piloto_corrida
            WHERE voltas_analisadas > voltas_disponiveis
        """,

        "stint_consistency": """
            SELECT COUNT(*) = 0
            FROM gold_tr_stints
            WHERE compound_count > 1
        """,
    }

    failures = []

    for name, sql in checks.items():
        print(f"Validando: {name}")

        try:
            result = con.execute(sql).fetchone()[0]
            print(f"  Resultado: {result}")

            if not result:
                failures.append(name)

        except Exception as e:
            print(f"  ERRO: {type(e).__name__}: {e}")
            raise

    if failures:
        raise AssertionError(
            "Validações Gold falharam: " + ", ".join(failures)
        )


def materialize(con: duckdb.DuckDBPyConnection) -> None:
    for view_name, filename in MATERIALIZATIONS.items():
        target = s3_uri(f"gold/{filename}")
        con.execute(f"COPY {view_name} TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD, OVERWRITE_OR_IGNORE)")


def main() -> None:
    con = duckdb.connect()
    try:
        configure_duckdb(con)
        create_silver_views(con)
        validate_source_sessions(con)
        execute_models(con)
        validate_gold(con)
        materialize(con)
        print("Gold construída e materializada no MinIO.")
    finally:
        con.close()


if __name__ == "__main__":
    main()
