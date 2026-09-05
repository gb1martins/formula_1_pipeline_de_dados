import duckdb
import os

con = duckdb.connect()

con.execute("INSTALL httpfs")
con.execute("LOAD httpfs")
con.execute("SET disabled_optimizers='statistics_propagation'")

con.execute("SET s3_endpoint='localhost:9000'")
con.execute("SET s3_access_key_id='admin'")
con.execute("SET s3_secret_access_key='minioadmin123'")
con.execute("SET s3_use_ssl=false")
con.execute("SET s3_url_style='path'")

con.execute("""
CREATE OR REPLACE VIEW silver_pneus AS
SELECT *
FROM read_parquet(
    's3://f1-data-lake/silver/consolidado/pneus.parquet',
    union_by_name=true
)
""")

con.execute("""
CREATE OR REPLACE VIEW silver_driver_mapping AS
SELECT *
FROM read_parquet(
    's3://f1-data-lake/silver/driver_mapping/driver_mapping.parquet',
    union_by_name=true
)
""")

con.execute("""
CREATE OR REPLACE VIEW silver_calendario AS
SELECT *
FROM read_parquet(
    's3://f1-data-lake/silver/calendario/**/*.parquet',
    hive_partitioning=true,
    union_by_name=true
)
""")

con.execute("""
CREATE OR REPLACE VIEW gold_dim_corrida AS
SELECT
    ROW_NUMBER() OVER (ORDER BY season, round) AS race_key,
    season,
    round,
    race_name,
    race_date,
    race_time,
    race_url,
    circuit_id,
    circuit_name,
    circuit_url,
    circuit_lat,
    circuit_long,
    circuit_locality,
    circuit_country,
    first_practice_date,
    second_practice_date,
    third_practice_date,
    qualifying_date
FROM silver_calendario
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY season, round
    ORDER BY race_date NULLS LAST, race_name
) = 1
""")

con.execute("""
CREATE OR REPLACE VIEW gold_fct_piloto_corrida AS
SELECT *
FROM read_parquet(
    's3://f1-data-lake/gold/fct_piloto_corrida.parquet',
    union_by_name=true
)
""")

con.execute("""
CREATE OR REPLACE VIEW gold_fct_pit_stops AS
SELECT *
FROM read_parquet(
    's3://f1-data-lake/gold/fct_pit_stops.parquet',
    union_by_name=true
)
""")

con.execute("""
CREATE OR REPLACE VIEW gold_fct_stints AS
SELECT *
FROM read_parquet(
    's3://f1-data-lake/gold/fct_stints.parquet',
    union_by_name=true
)
""")


resultado = con.execute("""
SELECT
    COUNT(*) AS pilotos_corrida,
    COUNT(ritmo_representativo_pct) AS ritmo_preenchido,
    SUM(voltas_analisadas) AS voltas_analisadas,
    SUM(voltas_disponiveis) AS voltas_disponiveis,
    MEDIAN(cobertura_ritmo_pct) AS cobertura_mediana,
    SUM(CASE WHEN amostra_reduzida THEN 1 ELSE 0 END) AS amostras_reduzidas
FROM gold_fct_piloto_corrida
""").fetchdf()

print(resultado)