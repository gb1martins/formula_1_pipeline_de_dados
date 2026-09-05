-- Gold: 1 piloto x 1 corrida x 1 volta.
-- Os atributos de origem são selecionados sem nova tipagem.
CREATE OR REPLACE VIEW gold_fct_voltas AS
SELECT
    r.race_key,
    d.driver_key,
    p.lap,
    p.lap_time_seconds,
    p.delta_ritmo_pct,
    p.pit_stop,
    p.evento_coletivo_extremo,
    p.volta_comparavel
FROM gold_tr_pace p
JOIN gold_dim_corrida r
  ON r.season = p.season
 AND r.round = p.round
JOIN gold_dim_piloto d
  ON d.driver_id = p.driver_id;
