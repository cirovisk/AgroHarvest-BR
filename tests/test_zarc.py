import json

import pandas as pd

from src.pipeline.sources.zarc import ZarcPipeline


def _zarc_rows(cultures):
    rows = []
    codes = {
        "Cana-de-Açúcar (açúcar e álcool)": "12011840021011",
        "Cana-de-Açúcar (outros fins)": "12011840000011",
    }
    for position, culture in enumerate(cultures, start=1):
        rows.append(
            {
                "Nome_cultura": culture,
                "SafraIni": "2025",
                "SafraFin": "2026",
                "Cod_Cultura": codes.get(culture, str(position)),
                "Cod_Solo": "1",
                "geocodigo": f"500000{position}",
                "UF": "MS",
                "municipio": f"Município {position}",
                "dec1": "20",
            }
        )
    return pd.DataFrame(rows)


def test_reconhece_codigos_e_finalidades_oficiais_da_cana(tmp_path):
    pipeline = ZarcPipeline(data_dir=tmp_path)
    clean = pipeline.clean(_zarc_rows(["Cana-de-Açúcar (açúcar e álcool)", "Cana-de-Açúcar (outros fins)"]))

    assert clean["cultura"].tolist() == ["cana-de-acucar", "cana-de-acucar"]
    assert clean["finalidade"].tolist() == ["acucar-e-alcool", "outros-fins"]
    assert clean["safra"].tolist() == ["2025-2026", "2025-2026"]


def test_separacao_usa_codigo_da_cana_mesmo_sem_nome_reconhecivel(tmp_path):
    pipeline = ZarcPipeline(data_dir=tmp_path)
    source = _zarc_rows(["Descrição alterada pelo MAPA"])
    source["Cod_Cultura"] = "12011840021011"

    mask = pipeline._crop_masks(source)["cana-de-acucar"]

    assert mask.tolist() == [True]


def test_cache_e_manifesto_sao_isolados_por_safra(tmp_path):
    first = ZarcPipeline(data_dir=tmp_path, safra="2025-2026")
    second = ZarcPipeline(
        data_dir=tmp_path,
        safra="2026-2027",
        resource_id="139e5a60-1f43-4cc8-aeab-a35dbbf816c0",
    )
    first.raw_file.write_text("conteudo-2025", encoding="utf-8")
    first._write_manifest()

    assert first._cache_is_valid()
    assert not second._cache_is_valid()
    assert first.raw_file != second.raw_file
    assert json.loads(first.manifest_file.read_text(encoding="utf-8"))["safra"] == "2025-2026"


def test_hash_invalido_rejeita_cache(tmp_path):
    pipeline = ZarcPipeline(data_dir=tmp_path)
    pipeline.raw_file.write_text("original", encoding="utf-8")
    pipeline._write_manifest()
    pipeline.raw_file.write_text("alterado", encoding="utf-8")

    assert not pipeline._cache_is_valid()


def test_cultura_ausente_retorna_status_partial(tmp_path, monkeypatch):
    pipeline = ZarcPipeline(data_dir=tmp_path, chunksize=2)
    source = _zarc_rows(["Soja", "Milho", "Trigo", "Algodão"])
    source.to_csv(pipeline.raw_file, sep=";", index=False)
    pipeline._write_manifest()
    monkeypatch.setattr(pipeline, "load", lambda frame, lookups: len(frame))

    result = pipeline.run(lookups={})

    assert result["status"] == "partial"
    assert result["coverage_observed"] == ["soja", "milho", "trigo", "algodao"]
    assert result["warnings"] == ["Cultura sem registros na safra 2025-2026: cana-de-acucar"]


def test_safra_precisa_ter_anos_consecutivos(tmp_path):
    try:
        ZarcPipeline(data_dir=tmp_path, safra="2023-2025")
    except ValueError as error:
        assert "anos consecutivos" in str(error)
    else:
        raise AssertionError("Safra inválida deveria ter sido rejeitada")
