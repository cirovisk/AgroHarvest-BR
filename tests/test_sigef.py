import pytest
import pandas as pd

from src.pipeline.sources.sigef import SigefPipeline


@pytest.fixture
def mock_sigef_producao_raw():
    return pd.DataFrame(
        [
            {
                "DS_SAFRA": "2023/2023",
                "DS_ESPECIE": "SOJA",
                "DS_CATEGORIA": "C1",
                "DS_CULTIVAR": "BRS 100",
                "DS_MUNICIPIO": "SORRISO",
                "DS_UF": "MT",
                "DS_STATUS": "ATIVO",
                "DT_PLANTIO": "01/10/2023",
                "DT_COLHEITA": "01/02/2024",
                "NR_AREA": "100,5",
                "NR_PRODUCAO_BRUTA": "300,0",
                "NR_PRODUCAO_EST": "280,0",
            }
        ]
    )


@pytest.fixture
def mock_sigef_uso_proprio_raw():
    return pd.DataFrame(
        [
            {
                "TIPOPERIODO": "ANO",
                "PERIODO": "2023",
                "AREATOTAL": "50,0",
                "MUNICIPIO": "SORRISO",
                "UF": "MT",
                "ESPECIE": "MILHO",
                "CULTIVAR": "DKB 255",
                "AREAPLANTADA": "40,0",
                "AREAESTIMADA": "45,0",
            }
        ]
    )


def test_sigef_transform_producao(mock_sigef_producao_raw):
    pipeline = SigefPipeline()
    df_clean = pipeline._clean_producao(mock_sigef_producao_raw)

    assert not df_clean.empty
    row = df_clean.iloc[0]
    assert row["safra"] == "2023/2023"
    assert row["cultura"] == "soja"
    assert row["area_ha"] == 100.5
    assert row["producao_bruta_t"] == 300.0
    assert row["data_plantio"].year == 2023


def test_sigef_transform_uso_proprio(mock_sigef_uso_proprio_raw):
    pipeline = SigefPipeline()
    df_clean = pipeline._clean_reserva_semente(mock_sigef_uso_proprio_raw)

    assert not df_clean.empty
    row = df_clean.iloc[0]
    assert row["periodo"] == "2023"
    assert row["cultura"] == "milho"
    assert row["area_total_ha"] == 50.0
    assert row["area_plantada_ha"] == 40.0


def production_row(**overrides):
    row = {
        "DS_SAFRA": "2013/2013",
        "DS_ESPECIE": "SOJA",
        "DS_CATEGORIA": "C1",
        "DS_CULTIVAR": "BRS 100",
        "DS_MUNICIPIO": "SORRISO",
        "DS_UF": "MT",
        "DS_STATUS": "ATIVO",
        "DT_PLANTIO": "01/10/2013",
        "DT_COLHEITA": "01/02/2014",
        "NR_AREA": "100,5",
        "NR_PRODUCAO_BRUTA": "300,0",
        "NR_PRODUCAO_EST": "280,0",
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize("corrupted_year", ["0013", "0213", "1013"])
def test_sigef_corrects_unambiguous_year_suffix(tmp_path, corrupted_year):
    pipeline = SigefPipeline(data_dir=tmp_path)
    cleaned = pipeline._clean_producao(pd.DataFrame([production_row(DT_PLANTIO=f"01/10/{corrupted_year}")]))

    assert cleaned.iloc[0]["data_plantio"] == pd.Timestamp("2013-10-01")
    assert pipeline.quality_metrics["dates_corrected"] == 1
    audit = pd.read_csv(pipeline.quarantine_path, dtype=str)
    assert audit.iloc[0]["regra_aplicada"] == "year_suffix_corrected"
    assert audit.iloc[0]["valor_corrigido"] == "01/10/2013"


@pytest.mark.parametrize("bad_year", ["1605", "8201"])
def test_sigef_quarantines_year_without_unique_correction(tmp_path, bad_year):
    pipeline = SigefPipeline(data_dir=tmp_path)
    cleaned = pipeline._clean_producao(pd.DataFrame([production_row(DT_PLANTIO=f"01/10/{bad_year}")]))

    assert pd.isna(cleaned.iloc[0]["data_plantio"])
    audit = pd.read_csv(pipeline.quarantine_path, dtype=str)
    rejected = audit[audit["campo"] == "data_plantio"].iloc[0]
    assert rejected["valor_original"] == f"01/10/{bad_year}"
    assert rejected["motivo_rejeicao"] == "ano_fora_janela_sem_correcao_univoca"


def test_sigef_validates_leap_day_after_year_correction(tmp_path):
    pipeline = SigefPipeline(data_dir=tmp_path)
    valid = pipeline._clean_producao(pd.DataFrame([production_row(DS_SAFRA="2012/2012", DT_PLANTIO="29/02/0012")]))
    invalid = pipeline._clean_producao(pd.DataFrame([production_row(DS_SAFRA="2013/2013", DT_PLANTIO="29/02/0013")]))

    assert valid.iloc[0]["data_plantio"] == pd.Timestamp("2012-02-29")
    assert pd.isna(invalid.iloc[0]["data_plantio"])


def test_sigef_accepts_next_year_for_cross_year_crop(tmp_path):
    pipeline = SigefPipeline(data_dir=tmp_path)
    cleaned = pipeline._clean_producao(
        pd.DataFrame([production_row(DS_SAFRA="2026/2027", DT_PLANTIO="01/10/2026", DT_COLHEITA="01/02/2027")])
    )

    assert cleaned.iloc[0]["data_colheita"] == pd.Timestamp("2027-02-01")
    assert pipeline.quality_metrics["dates_rejected"] == 0


def test_sigef_rejects_dates_when_crop_year_is_missing(tmp_path):
    pipeline = SigefPipeline(data_dir=tmp_path)
    cleaned = pipeline._clean_producao(pd.DataFrame([production_row(DS_SAFRA=None)]))

    assert pd.isna(cleaned.iloc[0]["data_plantio"])
    assert pd.isna(cleaned.iloc[0]["data_colheita"])
    assert pipeline.quality_metrics["dates_rejected"] == 2


def test_sigef_quarantines_harvest_before_planting(tmp_path):
    pipeline = SigefPipeline(data_dir=tmp_path)
    cleaned = pipeline._clean_producao(
        pd.DataFrame([production_row(DT_PLANTIO="01/10/2013", DT_COLHEITA="01/09/2013")])
    )

    assert pd.isna(cleaned.iloc[0]["data_plantio"])
    assert pd.isna(cleaned.iloc[0]["data_colheita"])
    assert pipeline.quality_metrics["chronology_rejected"] == 1
    audit = pd.read_csv(pipeline.quarantine_path, dtype=str)
    assert "data_colheita_anterior_data_plantio" in audit["motivo_rejeicao"].tolist()


def test_sigef_deduplication_prefers_quality_and_is_order_independent(tmp_path):
    good = production_row(DT_PLANTIO="01/10/2013", DT_COLHEITA="01/02/2014", NR_AREA="100")
    bad = production_row(DT_PLANTIO="01/10/8201", DT_COLHEITA="01/02/8201", NR_AREA="999")

    first = SigefPipeline(data_dir=tmp_path / "first")._clean_producao(pd.DataFrame([good, bad]))
    second_pipeline = SigefPipeline(data_dir=tmp_path / "second")
    second = second_pipeline._clean_producao(pd.DataFrame([bad, good]))

    assert len(first) == len(second) == 1
    assert first.iloc[0]["area_ha"] == second.iloc[0]["area_ha"] == 100
    assert second_pipeline.quality_metrics["duplicate_rows_consolidated"] == 1
    assert second_pipeline.quality_metrics["duplicate_groups_with_date_conflicts"] == 1


def test_sigef_quarantine_is_stable_on_reexecution(tmp_path):
    pipeline = SigefPipeline(data_dir=tmp_path)
    raw = pd.DataFrame([production_row(DT_PLANTIO="01/10/8201")])
    pipeline._clean_producao(raw)
    first = (tmp_path / "campos_producao_quarentena.csv").read_bytes()
    pipeline._clean_producao(raw)

    assert (tmp_path / "campos_producao_quarentena.csv").read_bytes() == first


def test_sigef_preserves_new_reservation_fields(tmp_path):
    pipeline = SigefPipeline(data_dir=tmp_path)
    raw = pd.DataFrame(
        [
            {
                "TIPOPERIODO": "ANO",
                "PERIODO": "2023",
                "AREATOTAL": "50,0",
                "MUNICIPIO": "SORRISO",
                "UF": "MT",
                "ESPECIE": "MILHO",
                "CULTIVAR": "DKB 255",
                "AREAPLANTADA": "40,0",
                "AREAESTIMADA": "45,0",
                "QUANTRESERVADA": "12,5",
                "DATAPLANTIO": "01/10/2023",
            }
        ]
    )
    cleaned = pipeline._clean_reserva_semente(raw)

    assert cleaned.iloc[0]["quantidade_reservada_t"] == 12.5
    assert cleaned.iloc[0]["data_plantio"] == pd.Timestamp("2023-10-01")
