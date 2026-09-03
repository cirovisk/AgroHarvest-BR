from unittest.mock import Mock, patch

import pandas as pd
import pytest

from src.pipeline.sources.sidra import SidraPipeline


def _response(year: str, with_rows: bool = True, returned_year: str | None = None):
    header = ["D1C", "D1N", "D2N", "D3N", "V"]
    data = [header]
    if with_rows:
        data.append(["1200013", "Município A", "Área plantada", returned_year or year, "10"])
    response = Mock(status_code=200, text="")
    response.json.return_value = data
    return response


def test_default_scope_is_explicit_2021_to_2024(monkeypatch, tmp_path):
    monkeypatch.delenv("SIDRA_ANOS", raising=False)
    monkeypatch.delenv("SIDRA_ANO_DEFAULT", raising=False)

    pipeline = SidraPipeline(data_dir=str(tmp_path), use_cache=False)

    assert pipeline.anos == ("2021", "2022", "2023", "2024")


def test_extracts_each_configured_year(monkeypatch, tmp_path):
    pipeline = SidraPipeline(ano=["2021", "2022", "2023", "2024"], data_dir=str(tmp_path), use_cache=False)
    monkeypatch.setattr(pipeline, "_map_culture_ids", lambda: {"soja": "40124"})

    with patch(
        "src.pipeline.sources.sidra.requests.get",
        side_effect=lambda url, timeout: _response(url.split("/p/")[1].split("/")[0]),
    ):
        result = pipeline.extract()

    assert set(result["D3N"]) == {"2021", "2022", "2023", "2024"}
    assert pipeline.missing_years == []


def test_header_only_response_marks_year_as_missing(monkeypatch, tmp_path):
    pipeline = SidraPipeline(ano="2025", data_dir=str(tmp_path), use_cache=False)
    monkeypatch.setattr(pipeline, "_map_culture_ids", lambda: {"soja": "40124"})

    with patch("src.pipeline.sources.sidra.requests.get", return_value=_response("2025", with_rows=False)):
        result = pipeline.extract()

    assert result.empty
    assert pipeline.missing_years == ["2025"]
    assert pipeline.missing_requests == [("soja", "2025")]


def test_unexpected_returned_year_is_rejected(monkeypatch, tmp_path):
    pipeline = SidraPipeline(ano="2024", data_dir=str(tmp_path), use_cache=False)
    monkeypatch.setattr(pipeline, "_map_culture_ids", lambda: {"soja": "40124"})

    with patch("src.pipeline.sources.sidra.requests.get", return_value=_response("2024", returned_year="2023")):
        result = pipeline.extract()

    assert result.empty
    assert pipeline.missing_years == ["2024"]
    assert pipeline.missing_requests == [("soja", "2024")]


def test_cache_is_scoped_by_complete_year_set(monkeypatch, tmp_path):
    pd.DataFrame({"D3N": ["2021"]}).to_csv(tmp_path / "pam_sidra_2021.csv", index=False)
    pipeline = SidraPipeline(ano=["2021", "2022"], data_dir=str(tmp_path), use_cache=True)
    monkeypatch.setattr(pipeline, "_map_culture_ids", lambda: {"soja": "40124"})

    with patch(
        "src.pipeline.sources.sidra.requests.get",
        side_effect=lambda url, timeout: _response(url.split("/p/")[1].split("/")[0]),
    ) as get:
        result = pipeline.extract()

    assert get.call_count == 2
    assert set(result["D3N"]) == {"2021", "2022"}
    assert (tmp_path / "pam_sidra_2021-2022.csv").exists()


@pytest.mark.parametrize("years", ["", "202", "20x4", ["2024", "latest"]])
def test_rejects_invalid_year_configuration(years, tmp_path):
    with pytest.raises(ValueError):
        SidraPipeline(ano=years, data_dir=str(tmp_path))


def test_empty_load_is_reported_as_partial(tmp_path):
    pipeline = SidraPipeline(ano="2025", data_dir=str(tmp_path), use_cache=False)

    result = pipeline.load(pd.DataFrame(), lookups={})

    assert result["status"] == "partial"
    assert result["rows_loaded"] == 0
    assert result["coverage_expected"] == ["2025"]
