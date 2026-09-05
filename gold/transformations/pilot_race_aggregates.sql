-- Agregações independentes para o fato central.
-- Cada bloco já está no grão piloto-corrida antes de qualquer JOIN entre fatos.
CREATE OR REPLACE VIEW gold_tr_pilot_race AS
WITH resultado AS (
    SELECT
        r.race_key,
        d.driver_key,
        e.team_key,
        s.season,
        s.round,
        s.driver_id,
        s.grid,
        s.position,
        s.status,
        s.points,
        s.laps,
        s.race_time,
        s.race_time_millis,
        s.grid - s.position AS posicoes_ganhas
    FROM silver_resultados s
    JOIN gold_dim_corrida r
      ON r.season = s.season AND r.round = s.round
    JOIN gold_dim_piloto d
      ON d.driver_id = s.driver_id
    LEFT JOIN gold_dim_equipe e
      ON e.constructor_id = s.constructor_id
),
ritmo AS (
    SELECT
        r.race_key,
        r.driver_key,
        p.ritmo_representativo_pct,
        p.voltas_analisadas,
        p.voltas_disponiveis
    FROM resultado r
    LEFT JOIN gold_tr_pace_pilot_race p
      ON p.season = r.season
     AND p.round = r.round
     AND p.driver_id = r.driver_id
),
pits AS (
    SELECT
        r.race_key,
        d.driver_key,
        COUNT(*)::INTEGER AS qtd_pit_stops,
        MEDIAN(p.duration) FILTER (WHERE p.duration <= 60) AS duracao_mediana_pit_convencional
    FROM silver_pit_stops p
    JOIN gold_dim_corrida r
      ON r.season = p.season AND r.round = p.round
    JOIN gold_dim_piloto d
      ON d.driver_id = p.driver_id
    GROUP BY r.race_key, d.driver_key
),
stints AS (
    SELECT
        r.race_key,
        d.driver_key,
        COUNT(*)::INTEGER AS qtd_stints,
        COUNT(DISTINCT s.compound)::INTEGER AS qtd_compostos_distintos
    FROM gold_tr_stints s
    JOIN gold_dim_corrida r
      ON r.season = s.season
    JOIN gold_dim_piloto d
      ON d.driver_id = s.driver_id
    GROUP BY r.race_key, d.driver_key
)
SELECT
    resultado.race_key,
    resultado.driver_key,
    resultado.team_key,
    resultado.grid,
    resultado.position,
    resultado.status,
    resultado.points,
    resultado.laps,
    resultado.race_time,
    resultado.race_time_millis,
    resultado.posicoes_ganhas,
    ritmo.ritmo_representativo_pct,
    COALESCE(ritmo.voltas_analisadas, 0) AS voltas_analisadas,
    COALESCE(ritmo.voltas_disponiveis, 0) AS voltas_disponiveis,
    CASE
        WHEN COALESCE(ritmo.voltas_disponiveis, 0) > 0
        THEN ritmo.voltas_analisadas * 100.0 / ritmo.voltas_disponiveis
        ELSE NULL
    END AS cobertura_ritmo_pct,
    COALESCE(ritmo.voltas_analisadas, 0) < 20 AS amostra_reduzida,
    COALESCE(pits.qtd_pit_stops, 0) AS qtd_pit_stops,
    pits.duracao_mediana_pit_convencional,
    COALESCE(stints.qtd_stints, 0) AS qtd_stints,
    COALESCE(stints.qtd_compostos_distintos, 0) AS qtd_compostos_distintos
FROM resultado
LEFT JOIN ritmo
  ON ritmo.race_key = resultado.race_key
 AND ritmo.driver_key = resultado.driver_key
LEFT JOIN pits
  ON pits.race_key = resultado.race_key
 AND pits.driver_key = resultado.driver_key
LEFT JOIN stints
  ON stints.race_key = resultado.race_key
 AND stints.driver_key = resultado.driver_key;
