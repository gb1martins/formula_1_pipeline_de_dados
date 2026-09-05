-- Gold: dimensão piloto (Type 1)
-- Deduplicação é modelagem da entidade, não limpeza/retratamento da Silver.
CREATE OR REPLACE VIEW gold_dim_piloto AS
SELECT
    ROW_NUMBER() OVER (ORDER BY driver_id) AS driver_key,
    driver_id,
    MAX(driver_number) AS driver_number,
    MAX(driver_permanent_number) AS driver_permanent_number,
    MAX(driver_code) AS driver_code,
    MAX(driver_given_name || ' ' || driver_family_name) AS name,
    MAX(driver_given_name) AS given_name,
    MAX(driver_family_name) AS family_name,
    MAX(driver_nationality) AS nationality,
    MAX(driver_date_of_birth) AS date_of_birth
FROM silver_resultados
WHERE driver_id IS NOT NULL
GROUP BY driver_id;
