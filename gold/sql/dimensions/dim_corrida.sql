-- Gold: dimensão corrida
-- Silver já tipada; nenhum CAST é aplicado aos atributos de origem.
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
) = 1;
