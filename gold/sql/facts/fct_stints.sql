-- Gold: 1 piloto x 1 corrida x 1 stint.
CREATE OR REPLACE VIEW gold_fct_stints AS
SELECT
    r.race_key,
    d.driver_key,
    s.stint_number,
    s.compound,
    s.voltas_observadas,
    s.tyre_life_inicial,
    s.tyre_life_final
FROM gold_tr_stints s
JOIN gold_dim_corrida r
  ON r.season = s.season
 AND r.circuit_name = 'Autódromo José Carlos Pace'
JOIN gold_dim_piloto d
  ON d.driver_id = s.driver_id;