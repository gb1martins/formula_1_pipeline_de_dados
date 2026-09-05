-- Transformações analíticas de ritmo exigidas pelo EDA.
-- Esta etapa não retrata a Silver: somente calcula métricas derivadas para a Gold.
CREATE OR REPLACE VIEW gold_tr_pace AS
WITH contexto AS (
    SELECT
        v.season,
        v.round,
        v.driver_id,
        v.lap,
        v.lap_time_seconds,
        MEDIAN(v.lap_time_seconds) OVER (PARTITION BY v.season, v.round) AS mediana_corrida,
        MEDIAN(v.lap_time_seconds) OVER (PARTITION BY v.season, v.round, v.lap) AS mediana_volta_corrida,
        CASE WHEN p.driver_id IS NULL THEN FALSE ELSE TRUE END AS pit_stop
    FROM silver_voltas v
    LEFT JOIN (
        SELECT DISTINCT season, round, driver_id, lap
        FROM silver_pit_stops
        WHERE lap IS NOT NULL
    ) p
      ON p.season = v.season
     AND p.round = v.round
     AND p.driver_id = v.driver_id
     AND p.lap = v.lap
),
classificacao AS (
    SELECT
        *,
        ((mediana_volta_corrida / NULLIF(mediana_corrida, 0)) - 1) * 100 AS delta_contexto_volta_pct
    FROM contexto
),
comparabilidade AS (
    SELECT
        *,
        delta_contexto_volta_pct > 100 AS evento_coletivo_extremo,
        NOT pit_stop AND NOT (delta_contexto_volta_pct > 100) AS volta_comparavel
    FROM classificacao
),
referencia AS (
    SELECT
        season,
        round,
        lap,
        MEDIAN(lap_time_seconds) AS mediana_volta_comparavel
    FROM comparabilidade
    WHERE volta_comparavel
    GROUP BY season, round, lap
)
SELECT
    c.season,
    c.round,
    c.driver_id,
    c.lap,
    c.lap_time_seconds,
    CASE
        WHEN c.volta_comparavel AND r.mediana_volta_comparavel IS NOT NULL
        THEN ((c.lap_time_seconds / NULLIF(r.mediana_volta_comparavel, 0)) - 1) * 100
        ELSE NULL
    END AS delta_ritmo_pct,
    c.pit_stop,
    c.evento_coletivo_extremo,
    c.volta_comparavel
FROM comparabilidade c
LEFT JOIN referencia r
  ON r.season = c.season
 AND r.round = c.round
 AND r.lap = c.lap;

CREATE OR REPLACE VIEW gold_tr_pace_pilot_race AS
SELECT
    season,
    round,
    driver_id,
    MEDIAN(delta_ritmo_pct) FILTER (
        WHERE volta_comparavel AND delta_ritmo_pct IS NOT NULL
    ) AS ritmo_representativo_pct,
    COUNT(*) FILTER (
        WHERE volta_comparavel AND delta_ritmo_pct IS NOT NULL
    )::INTEGER AS voltas_analisadas,
    COUNT(*)::INTEGER AS voltas_disponiveis
FROM gold_tr_pace
GROUP BY season, round, driver_id;
