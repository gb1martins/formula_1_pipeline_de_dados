-- Gold: 1 medição climática.
-- Nenhuma coluna climática é re-tipificada; os tipos são os definidos na Silver.
CREATE OR REPLACE VIEW gold_fct_clima AS
SELECT
    ROW_NUMBER() OVER (
        ORDER BY c.season, c.weather_time_seconds, c.event_date, c.session
    ) AS weather_key,
    r.race_key,
    c.weather_time_seconds,
    c.air_temp,
    c.track_temp,
    c.humidity,
    c.pressure,
    c.wind_speed,
    c.rainfall,
    c.wind_direction,
    c.event_date,
    c.session,
    c.session_name
FROM silver_clima c

JOIN gold_dim_corrida r
    ON r.season = c.season
    AND r.circuit_name = 'Autódromo José Carlos Pace'
    AND c.circuit = 'Interlagos'
