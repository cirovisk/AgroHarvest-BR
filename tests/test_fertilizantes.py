import os
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest
from src.pipeline.sources.fertilizantes import FertilizantesPipeline
from db.manager import FatoFertilizante, DimMunicipio


@pytest.fixture
def mock_fertilizantes_csv():
    # Return CSV content simulating SIPEAGRO
    lines = [
        "UNIDADE_DA_FEDERACAO;MUNICIPIO;NUMERO_REGISTRO_ESTABELECIMENTO;STATUS_DO_REGISTRO;CNPJ;RAZAO_SOCIAL;NOME_FANTASIA;AREA_ATUACAO;ATIVIDADE;CLASSIFICACAO",
        "MT;Sorriso ;MT-000123-4;Ativo;12.345.678/0001-90;AGRO LTDA ;Agro Fantasia;Fertilizantes;Produtor;Comerciante",
        "SP;Campinas;SP-000567-8;Ativo;98.765.432/0001-00;FUNDO SA;Fundo;Fertilizantes;Produtor;Importador"
    ]
    return "\n".join(lines)


def test_fertilizantes_extract(tmp_path, mock_fertilizantes_csv):
    data_dir = tmp_path / "fertilizantes"
    pipeline = FertilizantesPipeline(data_dir=str(data_dir))
    
    # Mockando request HTTP do requests
    mock_response = MagicMock()
    mock_response.content = mock_fertilizantes_csv.encode("latin1")
    
    with patch("requests.get", return_value=mock_response) as mock_get:
        df = pipeline.extract()
        
        assert mock_get.call_count == 1
        assert not df.empty
        assert len(df) == 2
        assert "MUNICIPIO" in df.columns
        assert df.iloc[0]["MUNICIPIO"] == "Sorriso "


def test_fertilizantes_clean():
    pipeline = FertilizantesPipeline()
    # Use astype(object) to ensure the internal column type is exactly
    # 'object' across Pandas versions, allowing cleaning to run.
    raw_df = pd.DataFrame({
        "UNIDADE_DA_FEDERACAO": ["MT ", " SP"],
        "MUNICIPIO": ["Sorriso", "Campinas "],
        "NUMERO_REGISTRO_ESTABELECIMENTO": ["MT-000123-4", "SP-000567-8"],
        "STATUS_DO_REGISTRO": ["Ativo", "Ativo"],
        "CNPJ": ["12.345.678/0001-90", "98.765.432/0001-00"],
        "RAZAO_SOCIAL": ["AGRO LTDA", "FUNDO SA"],
        "NOME_FANTASIA": ["Agro Fantasia", "Fundo"],
        "AREA_ATUACAO": ["Fertilizantes", "Fertilizantes"],
        "ATIVIDADE": ["Produtor", "Produtor"],
        "CLASSIFICACAO": ["Comerciante", "Importador"]
    }).astype(object)
    
    clean_df = pipeline.clean(raw_df)
    
    assert "uf" in clean_df.columns
    assert "nr_registro_estabelecimento" in clean_df.columns
    assert clean_df.iloc[0]["uf"] == "MT"
    assert clean_df.iloc[1]["municipio"] == "Campinas"


@patch("src.pipeline.sources.fertilizantes.upsert_data")
def test_fertilizantes_load(mock_upsert):
    pipeline = FertilizantesPipeline()
    
    # Prepara o dataframe limpo
    clean_df = pd.DataFrame({
        "uf": ["MT"],
        "municipio": ["Sorriso"],
        "nr_registro_estabelecimento": ["MT-000123-4"],
        "status_registro": ["Ativo"],
        "cnpj": ["12.345.678/0001-90"],
        "razao_social": ["AGRO LTDA"],
        "nome_fantasia": ["Agro Fantasia"],
        "area_atuacao": ["Fertilizantes"],
        "atividade": ["Produtor"],
        "classificacao": ["Comerciante"]
    })
    
    lookups = {
        "municipios_nome": {("sorriso", "MT"): 10}
    }
    
    # Load data while mocking insertion into the production database
    res = pipeline.load(clean_df, lookups)
    
    assert "1 estabelecimentos upserted" in res
    assert mock_upsert.call_count == 1
    
    # Unpack matching the positional and keyword call
    args, kwargs = mock_upsert.call_args
    called_model = args[0]
    called_df = args[1]
    called_index_elements = kwargs["index_elements"]
    
    assert called_model == FatoFertilizante
    assert called_index_elements == ["nr_registro_estabelecimento"]
    assert called_df.iloc[0]["id_municipio"] == 10
    assert called_df.iloc[0]["razao_social"] == "AGRO LTDA"
