from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MODELS = [
    *ROOT.glob('sql/dimensions/*.sql'),
    *ROOT.glob('sql/facts/*.sql'),
]


def test_no_indiscriminate_source_casts():
    forbidden = (
        'c.air_temp::', 'c.track_temp::', 'c.humidity::',
        'c.pressure::', 'c.wind_speed::', 'c.rainfall::',
        'c.wind_direction::', 'c.session::', 'c.session_name::',
        'c.weather_time_seconds::', 'p.lap_time_seconds::',
        'p.duration::', 's.compound::',
    )

    for path in MODELS:
        sql = path.read_text(encoding='utf-8')

        for token in forbidden:
            assert token not in sql, (
                f'CAST de origem indevido em {path}: {token}'
            )


def test_final_architecture_has_exactly_three_dimensions_and_five_facts():
    assert {p.stem for p in (ROOT / 'sql/dimensions').glob('*.sql')} == {
        'dim_corrida',
        'dim_piloto',
        'dim_equipe'
    }

    assert {p.stem for p in (ROOT / 'sql/facts').glob('*.sql')} == {
        'fct_piloto_corrida',
        'fct_voltas',
        'fct_pit_stops',
        'fct_stints',
        'fct_clima'
    }


def test_climate_has_no_lap_relationship():
    sql = (
        ROOT / 'sql/facts/fct_clima.sql'
    ).read_text(encoding='utf-8').lower()

    assert 'lap' not in sql
    assert 'driver_key' not in sql


def test_pit_stops_preserve_extremes():
    sql = (
        ROOT / 'sql/facts/fct_pit_stops.sql'
    ).read_text(encoding='utf-8')

    assert 'p.duration > 60' in sql
    assert 'p.duration <= 60' in sql
    assert 'where p.duration' not in sql.lower()