import duckdb

con = duckdb.connect()

# ============================================================
# CONFIGURAÇÃO DUCKDB + MINIO
# ============================================================

con.execute("INSTALL httpfs")
con.execute("LOAD httpfs")

# Workaround para erro interno do DuckDB em JOINs com Parquet/S3
con.execute("SET disabled_optimizers='statistics_propagation'")

con.execute("SET s3_endpoint='localhost:9000'")
con.execute("SET s3_access_key_id='admin'")
con.execute("SET s3_secret_access_key='minioadmin123'")
con.execute("SET s3_use_ssl=false")
con.execute("SET s3_url_style='path'")


# ============================================================
# SILVER
# ============================================================

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
CREATE OR REPLACE VIEW silver_pit_stops AS
SELECT *
FROM read_parquet(
    's3://f1-data-lake/silver/consolidado/pit_stops.parquet',
    union_by_name=true
)
""")

con.execute("""
CREATE OR REPLACE VIEW silver_pneus AS
SELECT *
FROM read_parquet(
    's3://f1-data-lake/silver/consolidado/pneus.parquet',
    union_by_name=true
)
""")


# ============================================================
# DIMENSÃO CORRIDA
# ============================================================

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


# ============================================================
# GOLD
# ============================================================
con.execute("""
CREATE OR REPLACE VIEW gold_fct_voltas AS
SELECT *
FROM read_parquet(
    's3://f1-data-lake/gold/fct_voltas.parquet',
    union_by_name=true
)
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


# ============================================================
# 1. VALIDAÇÃO DO RITMO E COBERTURA
# ============================================================

print("\n" + "=" * 70)
print("1. RITMO E COBERTURA")
print("=" * 70)

resultado_ritmo = con.execute("""
SELECT
    COUNT(*) AS pilotos_corrida,

    COUNT(ritmo_representativo_pct)
        AS ritmo_preenchido,

    SUM(voltas_analisadas)
        AS total_voltas_analisadas,

    SUM(voltas_disponiveis)
        AS total_voltas_disponiveis,

    MEDIAN(cobertura_ritmo_pct)
        AS cobertura_mediana,

    MIN(cobertura_ritmo_pct)
        AS cobertura_minima,

    MAX(cobertura_ritmo_pct)
        AS cobertura_maxima,

    SUM(
        CASE
            WHEN amostra_reduzida THEN 1
            ELSE 0
        END
    ) AS amostras_reduzidas

FROM gold_fct_piloto_corrida
""").fetchdf()

print(resultado_ritmo)

print("\nReferências da EDA:")
print("• Voltas totais: 12.589")
print("• Voltas comparáveis: 12.008")
print("• Percentual comparável: 95,38%")
print("• Cobertura mediana: 95,71%")
print("• Amostra reduzida: < 20 voltas comparáveis")


# ============================================================
# 2. DISTRIBUIÇÃO DO RITMO
# ============================================================

print("\n" + "=" * 70)
print("2. DISTRIBUIÇÃO DO RITMO REPRESENTATIVO")
print("=" * 70)

distribuicao_ritmo = con.execute("""
SELECT
    MIN(ritmo_representativo_pct) AS minimo,

    MEDIAN(ritmo_representativo_pct)
        AS mediana,

    MAX(ritmo_representativo_pct) AS maximo,

    COUNT(*) AS registros

FROM gold_fct_piloto_corrida

WHERE ritmo_representativo_pct IS NOT NULL
""").fetchdf()

print(distribuicao_ritmo)

print("\nReferência metodológica:")
print("• Negativo = ritmo melhor que a referência")
print("• Positivo = ritmo pior que a referência")
print("• Métrica = mediana do delta de ritmo por piloto-corrida")


# ============================================================
# 3. VALIDAÇÃO DOS PIT STOPS
# ============================================================

print("\n" + "=" * 70)
print("3. PIT STOPS")
print("=" * 70)

resultado_pit = con.execute("""
SELECT
    COUNT(*) AS qtd_pit_stops,

    MEDIAN(duration_seconds)
        AS mediana_duracao,

    SUM(
        CASE
            WHEN duration_seconds > 60 THEN 1
            ELSE 0
        END
    ) AS pit_stops_extremos,

    SUM(
        CASE
            WHEN duration_seconds <= 60 THEN 1
            ELSE 0
        END
    ) AS pit_stops_convencionais

FROM gold_fct_pit_stops
""").fetchdf()

print(resultado_pit)

print("\nReferências da EDA:")
print("• Total: 512 pit stops")
print("• Mediana global: aproximadamente 23,61 segundos")
print("• Stops > 60 segundos: 70")
print("• Stops extremos NÃO devem ser removidos")


# ------------------------------------------------------------
# Classificação dos pit stops
# ------------------------------------------------------------

print("\nClassificação dos pit stops:")

classificacao_pit = con.execute("""
SELECT
    pit_stop_extremo,
    COUNT(*) AS quantidade,
    MIN(duration_seconds) AS menor_duracao,
    MAX(duration_seconds) AS maior_duracao
FROM gold_fct_pit_stops
GROUP BY pit_stop_extremo
ORDER BY pit_stop_extremo
""").fetchdf()

print(classificacao_pit)


# ============================================================
# 4. VALIDAÇÃO DOS STINTS
# ============================================================

print("\n" + "=" * 70)
print("4. STINTS")
print("=" * 70)

resultado_stints = con.execute("""
SELECT
    COUNT(*) AS qtd_stints,

    COUNT(
        DISTINCT (race_key, driver_key, stint_number)
    ) AS chaves_unicas,

    SUM(
        CASE
            WHEN voltas_observadas IS NULL THEN 1
            ELSE 0
        END
    ) AS sem_voltas_observadas,

    SUM(
        CASE
            WHEN voltas_observadas <= 0 THEN 1
            ELSE 0
        END
    ) AS voltas_observadas_invalidas

FROM gold_fct_stints
""").fetchdf()

print(resultado_stints)

print("\nReferências metodológicas:")
print("• Stint = piloto × corrida × stint")
print("• Duração baseada em voltas_observadas")
print("• tyre_life NÃO é equivalente às voltas observadas")
print("• Ordem dos stints deve ser preservada")


# ============================================================
# 5. RECONCILIAÇÃO DO FATO CENTRAL
# ============================================================

print("\n" + "=" * 70)
print("5. RECONCILIAÇÃO DO FATO CENTRAL")
print("=" * 70)


# ------------------------------------------------------------
# 5.1 Pit stops → fato piloto-corrida
# ------------------------------------------------------------

reconciliacao_pit = con.execute("""
SELECT
    COUNT(*) AS registros_fato,
    SUM(qtd_pit_stops) AS total_pit_stops_gold
FROM gold_fct_piloto_corrida
""").fetchdf()

print("\nPit stops agregados no fato central:")
print(reconciliacao_pit)

print("\nEsperado:")
print("• SUM(qtd_pit_stops) = 512")


# ------------------------------------------------------------
# 5.2 Stints → fato piloto-corrida
# ------------------------------------------------------------

reconciliacao_stints = con.execute("""
SELECT
    COUNT(*) AS registros_fato,
    SUM(qtd_stints) AS total_stints_gold,
    SUM(qtd_compostos_distintos) AS total_diversidade_compostos
FROM gold_fct_piloto_corrida
""").fetchdf()

print("\nStints agregados no fato central:")
print(reconciliacao_stints)

print("\nEsperado:")
print("• SUM(qtd_stints) = 468")


# ------------------------------------------------------------
# 5.3 Voltas → fato piloto-corrida
# ------------------------------------------------------------

reconciliacao_voltas = con.execute("""
SELECT
    COUNT(*) AS registros_fato,

    SUM(voltas_disponiveis)
        AS total_voltas_disponiveis,

    SUM(voltas_analisadas)
        AS total_voltas_analisadas

FROM gold_fct_piloto_corrida
""").fetchdf()

print("\nVoltas agregadas no fato central:")
print(reconciliacao_voltas)

print("\nReferências:")
print("• Voltas disponíveis devem ser baseadas nos registros de voltas")
print("• Não utilizar resultados.laps como denominador")


# ------------------------------------------------------------
# 5.4 Verificação de duplicidade do fato central
# ------------------------------------------------------------

duplicidades = con.execute("""
SELECT
    race_key,
    driver_key,
    COUNT(*) AS quantidade
FROM gold_fct_piloto_corrida
GROUP BY
    race_key,
    driver_key
HAVING COUNT(*) > 1
ORDER BY quantidade DESC
""").fetchdf()

print("\nDuplicidades piloto × corrida:")

if duplicidades.empty:
    print("Nenhuma duplicidade encontrada.")
else:
    print(duplicidades)


# ------------------------------------------------------------
# 5.5 Verificação de valores impossíveis
# ------------------------------------------------------------

print("\nValores potencialmente inválidos:")

invalidos = con.execute("""
SELECT
    COUNT(*) AS registros_invalidos
FROM gold_fct_piloto_corrida
WHERE
       cobertura_ritmo_pct < 0
    OR cobertura_ritmo_pct > 100
    OR voltas_analisadas < 0
    OR voltas_disponiveis < 0
    OR voltas_analisadas > voltas_disponiveis
    OR qtd_pit_stops < 0
    OR qtd_stints < 0
    OR qtd_compostos_distintos < 0
""").fetchdf()

print(invalidos)


# ============================================================
# 6. VALIDAÇÃO LINHA A LINHA DO RITMO
# ============================================================

print("\n" + "=" * 70)
print("6. VALIDAÇÃO LINHA A LINHA DO RITMO")
print("=" * 70)


# ------------------------------------------------------------
# Recalcula as métricas diretamente a partir do fct_voltas
# ------------------------------------------------------------

ritmo_recalculado = con.execute("""
WITH recalculado AS (

    SELECT
        race_key,
        driver_key,

        MEDIAN(delta_ritmo_pct)
            FILTER (
                WHERE volta_comparavel
                  AND delta_ritmo_pct IS NOT NULL
            ) AS ritmo_recalculado,

        COUNT(*)
            FILTER (
                WHERE volta_comparavel
            ) AS voltas_analisadas_recalculadas,

        COUNT(*) AS voltas_disponiveis_recalculadas

    FROM gold_fct_voltas

    GROUP BY
        race_key,
        driver_key
)

SELECT
    f.race_key,
    f.driver_key,

    f.ritmo_representativo_pct,
    r.ritmo_recalculado,

    f.voltas_analisadas,
    r.voltas_analisadas_recalculadas,

    f.voltas_disponiveis,
    r.voltas_disponiveis_recalculadas

FROM gold_fct_piloto_corrida f

JOIN recalculado r
    ON f.race_key = r.race_key
   AND f.driver_key = r.driver_key
""").fetchdf()


print(f"\nRegistros comparados: {len(ritmo_recalculado)}")


# ------------------------------------------------------------
# Diferenças de ritmo
# ------------------------------------------------------------

divergencias_ritmo = ritmo_recalculado[
    (
        ritmo_recalculado["ritmo_representativo_pct"].isna()
        & ritmo_recalculado["ritmo_recalculado"].notna()
    )
    |
    (
        ritmo_recalculado["ritmo_representativo_pct"].notna()
        & ritmo_recalculado["ritmo_recalculado"].isna()
    )
    |
    (
        ritmo_recalculado["ritmo_representativo_pct"].notna()
        & ritmo_recalculado["ritmo_recalculado"].notna()
        & (
            abs(
                ritmo_recalculado["ritmo_representativo_pct"]
                - ritmo_recalculado["ritmo_recalculado"]
            ) > 0.000000001
        )
    )
]


print(f"Divergências de ritmo: {len(divergencias_ritmo)}")


# ------------------------------------------------------------
# Diferenças nas voltas analisadas
# ------------------------------------------------------------

divergencias_analisadas = ritmo_recalculado[
    ritmo_recalculado["voltas_analisadas"]
    != ritmo_recalculado["voltas_analisadas_recalculadas"]
]

print(
    "Divergências em voltas_analisadas: "
    f"{len(divergencias_analisadas)}"
)


# ------------------------------------------------------------
# Diferenças nas voltas disponíveis
# ------------------------------------------------------------

divergencias_disponiveis = ritmo_recalculado[
    ritmo_recalculado["voltas_disponiveis"]
    != ritmo_recalculado["voltas_disponiveis_recalculadas"]
]

print(
    "Divergências em voltas_disponiveis: "
    f"{len(divergencias_disponiveis)}"
)


# ------------------------------------------------------------
# Mostrar exemplos de divergência
# ------------------------------------------------------------

if len(divergencias_ritmo) > 0:

    print("\nExemplos de divergências de ritmo:")

    print(
        divergencias_ritmo[
            [
                "race_key",
                "driver_key",
                "ritmo_representativo_pct",
                "ritmo_recalculado",
            ]
        ].head(10)
    )

else:

    print("\nNenhuma divergência encontrada no ritmo.")


if len(divergencias_analisadas) > 0:

    print("\nExemplos de divergências em voltas_analisadas:")

    print(
        divergencias_analisadas[
            [
                "race_key",
                "driver_key",
                "voltas_analisadas",
                "voltas_analisadas_recalculadas",
            ]
        ].head(10)
    )

else:

    print("Nenhuma divergência em voltas_analisadas.")


if len(divergencias_disponiveis) > 0:

    print("\nExemplos de divergências em voltas_disponiveis:")

    print(
        divergencias_disponiveis[
            [
                "race_key",
                "driver_key",
                "voltas_disponiveis",
                "voltas_disponiveis_recalculadas",
            ]
        ].head(10)
    )

else:

    print("Nenhuma divergência em voltas_disponiveis.")


# ============================================================
# FINAL
# ============================================================

print("\n" + "=" * 70)
print("VALIDAÇÃO ANALÍTICA CONCLUÍDA")
print("=" * 70)