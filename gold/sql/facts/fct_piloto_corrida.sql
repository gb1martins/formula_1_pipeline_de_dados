-- Gold: fato central, 1 piloto x 1 corrida.
-- As agregações de voltas, pit stops e stints são calculadas antes dos joins finais.
CREATE OR REPLACE VIEW gold_fct_piloto_corrida AS
SELECT
    ROW_NUMBER() OVER (ORDER BY x.race_key, x.driver_key) AS pilot_race_key,
    x.race_key,
    x.driver_key,
    x.team_key,
    x.grid,
    x.position,
    x.status,
    x.points,
    x.laps,
    x.race_time,
    x.race_time_millis,
    x.posicoes_ganhas,
    x.ritmo_representativo_pct,
    x.voltas_analisadas,
    x.voltas_disponiveis,
    x.cobertura_ritmo_pct,
    x.amostra_reduzida,
    x.qtd_pit_stops,
    x.duracao_mediana_pit_convencional,
    x.qtd_stints,
    x.qtd_compostos_distintos
FROM gold_tr_pilot_race x;
