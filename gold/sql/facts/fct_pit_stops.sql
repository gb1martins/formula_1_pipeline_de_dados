-- Gold: 1 pit stop.
-- Todos os registros Silver permanecem; somente são classificados pela regra analítica.
CREATE OR REPLACE VIEW gold_fct_pit_stops AS
SELECT
    r.race_key,
    d.driver_key,
    p.stop,
    p.lap,
    p.duration AS duration_seconds,
    CASE WHEN p.duration IS NULL THEN NULL ELSE p.duration <= 60 END AS pit_stop_convencional,
    CASE WHEN p.duration IS NULL THEN NULL ELSE p.duration > 60 END AS pit_stop_extremo
FROM silver_pit_stops p
JOIN gold_dim_corrida r
  ON r.season = p.season
 AND r.round = p.round
JOIN gold_dim_piloto d
  ON d.driver_id = p.driver_id;
