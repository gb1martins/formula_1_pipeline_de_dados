# Modelagem da Camada Gold — Formula 1 / Interlagos

## 1. Objetivo

A Gold transforma a Silver já tratada em um modelo analítico dimensional e reutilizável. A Silver permanece como fonte de dados preparada; a Gold não repete limpeza, padronização ou tipagem.

A arquitetura final é **3 dimensões + 5 fatos**, com `fct_piloto_corrida` como fato central. Essa decisão é definitiva na revisão arquitetural.

## 2. Fontes

Datasets Silver utilizados:

- `calendario`
- `resultados`
- `voltas`
- `pit_stops`
- `pneus`
- `clima`
- `driver_mapping`

A especificação define o EDA como fonte de requisitos da Gold e lista essas fontes Silver como os datasets do projeto.

## 3. Arquitetura

```text
                         ┌─────────────────┐
                         │  dim_corrida    │
                         │ PK race_key     │
                         └────────┬────────┘
                                  │
              ┌───────────────────┼─────────────────────┐
              │                   │                     │
              ▼                   ▼                     ▼
┌────────────────────┐ ┌────────────────────┐ ┌──────────────────┐
│ fct_piloto_corrida │ │    fct_voltas      │ │  fct_pit_stops   │
│ PK pilot_race_key  │ │ race_key,driver_key│ │ race_key,driver_key│
└─────────┬──────────┘ └────────────────────┘ └──────────────────┘
          │
          │
          ▼
┌────────────────────┐       ┌────────────────────┐
│    fct_stints      │       │    fct_clima       │
└────────────────────┘       └────────────────────┘

 dim_piloto ───────► fatos de piloto
 dim_equipe ───────► fct_piloto_corrida
```

A revisão definitiva mantém `dim_corrida`, `dim_piloto`, `dim_equipe` e os cinco fatos, removendo estruturas paralelas como `fct_resultados` e `fct_pneus`.

## 4. Granularidades

| Tabela | Granularidade |
|---|---|
| `dim_corrida` | 1 corrida |
| `dim_piloto` | 1 piloto |
| `dim_equipe` | 1 equipe/construtor |
| `fct_piloto_corrida` | 1 piloto × 1 corrida |
| `fct_voltas` | 1 piloto × 1 corrida × 1 volta |
| `fct_pit_stops` | 1 pit stop |
| `fct_stints` | 1 piloto × 1 corrida × 1 stint |
| `fct_clima` | 1 medição climática |

A especificação exige que cada tabela tenha granularidade explícita e que diferentes granularidades não sejam misturadas sem justificativa.

## 5. Regra de consumo da Silver

### O que permanece igual

Os atributos Silver são selecionados diretamente quando não há transformação analítica necessária. Não são feitos `TRIM`, `CAST`, conversões de datas/horários ou novas padronizações na Gold.

Exemplo em `fct_clima`:

```sql
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
```

### CASTs realmente utilizados

Os modelos não fazem CAST dos atributos de origem. Os únicos CASTs presentes são de **contagens derivadas**:

- `COUNT(*)::INTEGER`
- `COUNT(DISTINCT ...)::INTEGER`

Isso ocorre porque `COUNT` em DuckDB produz uma contagem inteira própria do agregado, enquanto a especificação Gold define essas medidas como `INTEGER`. Não é uma re-tipagem de coluna Silver.

As chaves técnicas criadas com `ROW_NUMBER()` não precisam de CAST: o próprio resultado do window function já fornece o identificador inteiro adequado ao papel de chave.

## 6. Dimensões

### 6.1 dim_corrida

**Origem:** `silver_calendario`.

**PK:** `race_key`.

**Natural key:** `season + round`.

A dimensão contém os atributos de corrida e circuito necessários para contextualização. `season` permanece como atributo de `dim_corrida`; não existe `dim_temporada`. A revisão final confirma essa decisão.

A única operação adicional é garantir uma linha por `season + round`, requisito de modelagem da dimensão. Não há limpeza ou re-tipagem.

### 6.2 dim_piloto

**Origem:** `silver_resultados`.

**PK:** `driver_key`.

**Natural key:** `driver_id`.

É Type 1. A agregação por `driver_id` consolida a entidade em uma única linha, usando os atributos disponíveis na Silver. Isso é modelagem da dimensão, não uma nova etapa de limpeza.

### 6.3 dim_equipe

**Origem:** `silver_resultados`.

**PK:** `team_key`.

**Natural key:** `constructor_id`.

É Type 1 e representa a entidade equipe/construtor. Não há dimensão adicional de circuito, temporada ou status.

## 7. fct_piloto_corrida

**Grão:** 1 piloto em 1 corrida.

**PK técnica:** `pilot_race_key`.

**FKs:** `race_key`, `driver_key`, `team_key`.

**Origem:** `silver_resultados` + agregações de `voltas`, `pit_stops` e `pneus`.

Campos finais:

```text
pilot_race_key
race_key
driver_key
team_key
grid
position
status
points
laps
race_time
race_time_millis
posicoes_ganhas
ritmo_representativo_pct
voltas_analisadas
voltas_disponiveis
cobertura_ritmo_pct
amostra_reduzida
qtd_pit_stops
duracao_mediana_pit_convencional
qtd_stints
qtd_compostos_distintos
```

A arquitetura final escolheu esse fato em vez de um `fct_resultados` separado porque ambos teriam o mesmo grão piloto-corrida; o fato central incorpora resultado e desempenho.

### Prevenção de fan-out

As fontes de detalhes são agregadas separadamente:

```text
resultados → piloto-corrida
voltas     → piloto-corrida
pit_stops  → piloto-corrida
stints     → piloto-corrida
                      ↓
               joins 1:1 por piloto-corrida
```

Não é feito `resultados JOIN voltas JOIN pit_stops JOIN stints` no detalhe.

## 8. fct_voltas

**Grão:** 1 piloto × 1 corrida × 1 volta.

**FKs:** `race_key`, `driver_key`.

Campos finais:

```text
race_key
driver_key
lap
lap_time_seconds
delta_ritmo_pct
pit_stop
evento_coletivo_extremo
volta_comparavel
```

Os intermediários metodológicos não são persistidos:

```text
delta_mediana_pct
delta_volta_pct
delta_contexto_volta_pct
```

Eles existem apenas durante o cálculo do ritmo.

## 9. Metodologia de ritmo do EDA

A implementação preserva a sequência analítica definida:

1. mediana do tempo de volta da corrida;
2. mediana por volta dentro da corrida;
3. identificação de voltas com pit stop;
4. identificação de eventos coletivos extremos quando `delta_contexto_volta_pct > 100`;
5. definição de `volta_comparavel` como volta sem pit stop e sem evento coletivo extremo;
6. mediana de referência das voltas comparáveis por corrida e volta;
7. `delta_ritmo_pct = lap_time_seconds / mediana_volta_comparavel - 1`, em percentual;
8. mediana do delta por piloto-corrida como `ritmo_representativo_pct`;
9. `voltas_analisadas` = quantidade de voltas comparáveis analisadas;
10. `voltas_disponiveis` = quantidade de registros reais de `silver_voltas`;
11. `cobertura_ritmo_pct = voltas_analisadas / voltas_disponiveis × 100`;
12. `amostra_reduzida = voltas_analisadas < 20`.

O cálculo é analítico e, portanto, pertence à Gold; não é uma nova limpeza da Silver.

## 10. fct_pit_stops

**Grão:** 1 pit stop.

**PK natural:** `season + round + driver_id + stop`.

**FKs:** `race_key`, `driver_key`.

Campos:

```text
race_key
driver_key
stop
lap
duration_seconds
pit_stop_convencional
pit_stop_extremo
```

A duração `duration` da Silver é consumida diretamente como `duration_seconds`, pois a Silver já fez a conversão para segundos. A especificação define `duration_seconds <= 60` como convencional e `> 60` como extremo, sem remover os extremos.

## 11. fct_stints

**Grão:** 1 piloto × 1 corrida × 1 stint.

**PK natural:** `season + round + driver_id + stint_number`.

**FKs:** `race_key`, `driver_key`.

Campos:

```text
race_key
driver_key
stint_number
compound
voltas_observadas
tyre_life_inicial
tyre_life_final
```

A Silver `pneus` contém registros por volta e sessão. Como o grão aprovado é corrida, a transformação seleciona explicitamente `session = 'R'` (Race), depois usa `driver_mapping` para compatibilizar o identificador FastF1 com o identificador Jolpica usado nas demais fontes.

A reconstrução agrupa por piloto e stint. `voltas_observadas` é `COUNT(DISTINCT lap_number)`; não é calculada por diferença de `tyre_life`. A especificação destaca explicitamente essa distinção.

Se um mesmo stint apresentar mais de um composto, isso é tratado como inconsistência de modelagem e deve reprovar a validação, em vez de escolher arbitrariamente um valor.

## 12. fct_clima

**Grão:** 1 medição climática em um instante da sessão.

**PK técnica:** `weather_key`.

**FK:** `race_key`.

Campos principais:

```text
weather_key
race_key
weather_time_seconds
air_temp
track_temp
humidity
pressure
wind_speed
rainfall
wind_direction
event_date
session
session_name
```

Todos os atributos climáticos são selecionados diretamente da Silver.

Não existe relação volta → clima. O EDA informa que `weather_time_seconds` é relativo à sessão e não há alinhamento temporal direto com as voltas.

Também não existe join direto de `fct_piloto_corrida` com `fct_clima`, pois isso multiplicaria uma linha piloto-corrida por todas as medições climáticas. Para gerar contexto climático de uma corrida, primeiro deve-se agregar `fct_clima` por `race_key`.

## 13. PKs e FKs

| Tabela | PK | FKs |
|---|---|---|
| `dim_corrida` | `race_key` | — |
| `dim_piloto` | `driver_key` | — |
| `dim_equipe` | `team_key` | — |
| `fct_piloto_corrida` | `pilot_race_key` | `race_key`, `driver_key`, `team_key` |
| `fct_voltas` | natural: `race_key + driver_key + lap` | `race_key`, `driver_key` |
| `fct_pit_stops` | natural: `race_key + driver_key + stop` | `race_key`, `driver_key` |
| `fct_stints` | natural: `race_key + driver_key + stint_number` | `race_key`, `driver_key` |
| `fct_clima` | `weather_key` | `race_key` |

## 14. Rastreabilidade EDA → Gold

| Regra/requisito do EDA | Implementação | Gold | Resultado |
|---|---|---|---|
| Grão piloto-corrida | agregação antes dos joins | `fct_piloto_corrida` | 1 linha por piloto-corrida |
| Ganho/perda de posições | `grid - position` | `fct_piloto_corrida` | `posicoes_ganhas` |
| Mediana de contexto da corrida | window por corrida | `fct_voltas` / transformação | intermediário |
| Evento coletivo extremo | `delta_contexto_volta_pct > 100` | `fct_voltas` | `evento_coletivo_extremo` |
| Volta comparável | sem pit stop e sem evento extremo | `fct_voltas` | `volta_comparavel` |
| Delta de ritmo | comparação com mediana da volta comparável | `fct_voltas` | `delta_ritmo_pct` |
| Ritmo representativo | mediana do delta por piloto-corrida | `fct_piloto_corrida` | `ritmo_representativo_pct` |
| Cobertura de ritmo | analisadas / disponíveis × 100 | `fct_piloto_corrida` | `cobertura_ritmo_pct` |
| Amostra reduzida | analisadas < 20 | `fct_piloto_corrida` | `amostra_reduzida` |
| Voltas disponíveis | COUNT de registros Silver.voltas | `fct_piloto_corrida` | `voltas_disponiveis` |
| Pit stop convencional | duração <= 60 | `fct_pit_stops` | `pit_stop_convencional` |
| Pit stop extremo | duração > 60 | `fct_pit_stops` | `pit_stop_extremo` |
| Preservação dos extremos | nenhuma remoção | `fct_pit_stops` | todos os stops permanecem |
| Reconstrução de stint | agrupamento por stint na sessão Race | `fct_stints` | 1 piloto-corrida-stint |
| Voltas observadas do stint | COUNT DISTINCT lap_number | `fct_stints` | `voltas_observadas` |
| Vida inicial/final | MIN/MAX tyre_life | `fct_stints` | campos separados |
| Clima independente de voltas | sem join por lap | `fct_clima` | medição climática preservada |
| Clima como contexto de corrida | FK para corrida | `fct_clima` | `race_key` |

A especificação reforça que o EDA deve ser usado como fonte de requisitos e que as métricas precisam ser mapeadas para a Gold.

## 15. Prevenção de fan-out

As regras principais são:

- `fct_piloto_corrida` nunca recebe join direto com `silver_voltas`, `silver_pit_stops` ou `silver_pneus` no detalhe;
- cada fonte detalhada é agregada independentemente para piloto-corrida;
- `fct_clima` permanece independente;
- `fct_stints` já chega ao grão piloto-corrida-stint antes de ser associado ao fato central;
- joins finais do fato central ocorrem em chaves de granularidade 1:1.

## 16. Valores ausentes

A Gold não faz imputação genérica. Valores nulos válidos da Silver são preservados quando não impedem a métrica específica. Essa postura evita transformar ausência real em informação inventada.

## 17. Qualidade e validações

O `build_gold.py` valida:

- unicidade das chaves das dimensões;
- unicidade do grão piloto-corrida;
- unicidade do grão piloto-volta;
- unicidade do grão pit stop;
- unicidade do grão stint;
- unicidade da chave climática;
- FKs de corrida e piloto;
- classificação correta dos pit stops;
- limites de cobertura de ritmo;
- `voltas_analisadas <= voltas_disponiveis`;
- consistência dos stints;
- ausência de múltiplos compostos dentro de um mesmo stint.

Os testes estáticos também verificam que os modelos não introduzem CASTs nos atributos climáticos, de voltas, pit stops ou stints e que a arquitetura contém exatamente 3 dimensões e 5 fatos.

## 18. Materialização

DuckDB é usado como motor de leitura, transformação e validação. Depois das validações, cada view Gold é materializada como Parquet no MinIO, diretamente sob:

```text
s3://f1-data-lake/gold/
```

Não é criada uma segunda Silver nem são sobrescritos os Parquets Silver.

## 19. Limitações de validação deste pacote

Os códigos foram revisados contra a especificação arquitetural, documentação de modelagem e código Silver disponível nos arquivos fornecidos. A execução integrada contra o MinIO local do usuário não foi realizada neste ambiente, pois não há acesso ao workspace/endpoint local do usuário. Portanto, este pacote não declara contagens ou resultados locais como se tivessem sido executados.

A validação definitiva dos dados reais deve ser feita no ambiente do projeto com:

```bash
python gold/scripts/build_gold.py
pytest -q gold/tests
```

Se a Silver real tiver um nome/tipo de coluna diferente do código-fonte fornecido, a execução deve falhar e o schema real deve ser inspecionado antes de qualquer ajuste arbitrário.
