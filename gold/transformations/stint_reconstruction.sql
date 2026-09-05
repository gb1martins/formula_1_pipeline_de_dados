-- Reconstrução Gold dos stints a partir da Silver.pneus.
-- A sessão Race é a única compatível com o grão aprovado piloto-corrida-stint.
CREATE OR REPLACE VIEW gold_tr_stints AS
WITH race_session AS (
    SELECT
        season,
        session,
        driver_id,
        stint,
        compound,
        lap_number,
        tyre_life
    FROM silver_pneus
    WHERE session = 'R'
),
canonical AS (
    SELECT
        p.season,
        m.jolpica_driver_id AS driver_id,
        p.stint AS stint_number,
        p.compound,
        p.lap_number,
        p.tyre_life
    FROM race_session p
    JOIN silver_driver_mapping m
      ON m.season = p.season
     AND m.fastf1_driver_id = p.driver_id
     AND m.match_status = 'MATCH_OK'
),
agrupado AS (
    SELECT
        season,
        driver_id,
        stint_number,
        MAX(compound) AS compound,
        COUNT(DISTINCT lap_number)::INTEGER AS voltas_observadas,
        MIN(tyre_life) AS tyre_life_inicial,
        MAX(tyre_life) AS tyre_life_final,
        COUNT(DISTINCT compound) AS compound_count
    FROM canonical
    WHERE driver_id IS NOT NULL
      AND stint_number IS NOT NULL
    GROUP BY season, driver_id, stint_number
)
SELECT
    season,
    driver_id,
    stint_number,
    compound,
    voltas_observadas,
    tyre_life_inicial,
    tyre_life_final,
    compound_count
FROM agrupado;
