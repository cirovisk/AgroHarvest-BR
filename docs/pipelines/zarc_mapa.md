# Pipeline ZARC (MAPA)

O pipeline carrega a Tábua de Risco do Zoneamento Agrícola de Risco Climático em blocos, sem manter o arquivo consolidado inteiro na memória. A safra padrão é **2025-2026**, escolhida por conter a revisão da cana-de-açúcar publicada pelo MAPA em 2026.

## Fonte e configuração

- Órgão: Ministério da Agricultura e Pecuária (MAPA).
- Conjunto: [Tábua de Risco do ZARC](https://dados.agricultura.gov.br/dataset/tabua-de-risco-zoneamento-agricola-de-risco-climatico).
- `ZARC_SAFRA`: safra explícita no formato `AAAA-AAAA`; padrão `2025-2026`.
- `ZARC_RESOURCE_ID`: identificador CKAN do recurso. É opcional para as safras conhecidas pelo código.
- `ZARC_RESOURCE_URL`: URL completa do CSV oficial. Quando definida, prevalece sobre a URL construída pelo `resource_id`.

O código conhece os recursos oficiais de 2025-2026 e 2026-2027. Para outra safra, informe `ZARC_RESOURCE_ID` ou `ZARC_RESOURCE_URL`; o pipeline não reutiliza silenciosamente um arquivo de outra safra.

O portal pode responder HTTP 403 para downloads automatizados. Nesse caso, baixe o CSV no navegador, salve-o como `data/zarc/zarc_raw_AAAA-AAAA.csv` e execute novamente. O arquivo deve ser o recurso oficial do MAPA, sem renomear a safra.

## Cache e rastreabilidade

Os arquivos derivados têm a safra no nome:

```text
data/zarc/zarc_raw_2025-2026.csv
data/zarc/zarc_2025-2026_soja.csv
data/zarc/zarc_2025-2026_cana-de-acucar.csv
data/zarc/zarc_2025-2026.manifest.json
```

O manifesto registra safra, `resource_id`, URL e SHA-256 do consolidado. Antes de reutilizar o cache, o pipeline confere a safra e o hash. Um cache de 2025-2026, portanto, não satisfaz uma execução de 2026-2027.

O argumento global `--refresh` força um novo download e recria todos os arquivos derivados daquela safra.

## Culturas e cobertura

São esperadas soja, milho, trigo, algodão e cana-de-açúcar. Para a cana, o reconhecimento prioriza os códigos oficiais, não apenas o nome:

| Código ZARC | Finalidade persistida |
|---|---|
| `12011840021011` | `acucar-e-alcool` |
| `12011840000011` | `outros-fins` |

As demais culturas recebem `finalidade = nao-se-aplica`. Se qualquer cultura-alvo tiver zero linhas, a execução retorna `status = partial`, com `coverage_expected`, `coverage_observed` e uma advertência por ausência. Uma resposta parcial não deve ser registrada como sucesso integral pelo orquestrador.

## Processamento e armazenamento

O CSV consolidado é separado por cultura em blocos de 200 mil linhas. Cada arquivo derivado é lido em blocos de 50 mil linhas por padrão. As colunas `dec1` a `dec36` são convertidas do formato largo para uma linha por decêndio.

A fato `fato_risco_zarc` armazena:

- cultura e município;
- tipo de solo, período de plantio e risco climático;
- `safra`;
- `finalidade`;
- `cod_cultura_zarc`.

A chave de unicidade precisa incluir `safra` e `finalidade`, além de cultura, município, tipo de solo e período. Isso impede que outra safra ou outra finalidade da cana sobrescreva a observação existente.

## Verificações de aceite

Depois da carga, confira a cobertura por safra, cultura e finalidade:

```sql
SELECT z.safra, c.cultura, z.finalidade, COUNT(*) AS registros
FROM fato_risco_zarc AS z
JOIN dim_cultura AS c ON c.id_cultura = z.id_cultura
GROUP BY z.safra, c.cultura, z.finalidade
ORDER BY z.safra, c.cultura, z.finalidade;
```

As cinco culturas devem aparecer. Para cana-de-açúcar, as duas finalidades devem permanecer distinguíveis quando ambas existirem no recurso oficial.
