-- Gold: dimensão equipe/construtor (Type 1)
-- Os atributos são consumidos diretamente da Silver.
CREATE OR REPLACE VIEW gold_dim_equipe AS
SELECT
    ROW_NUMBER() OVER (ORDER BY constructor_id) AS team_key,
    constructor_id,
    MAX(constructor_name) AS constructor_name,
    MAX(constructor_nationality) AS constructor_nationality
FROM silver_resultados
WHERE constructor_id IS NOT NULL
GROUP BY constructor_id;
