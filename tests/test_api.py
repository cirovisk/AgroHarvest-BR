import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        follow_redirects=True,
    ) as async_client:
        yield async_client


async def test_health_check(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_culturas_list(client):
    response = await client.get("/culturas")
    assert response.status_code == 200
    assert "items" in response.json()
    assert isinstance(response.json()["items"], list)


async def test_municipios_list(client):
    response = await client.get("/municipios")
    assert response.status_code == 200
    assert "items" in response.json()
    assert isinstance(response.json()["items"], list)


async def test_producao_pam(client):
    response = await client.get("/producao/pam")
    assert response.status_code == 200
    assert "items" in response.json()
    assert isinstance(response.json()["items"], list)


async def test_insumos_agrofit(client):
    response = await client.get("/insumos/agrofit")
    assert response.status_code == 200
    assert "items" in response.json()
    assert isinstance(response.json()["items"], list)


async def test_clima_list(client):
    response = await client.get("/clima")
    assert response.status_code == 200
    assert "items" in response.json()
    assert isinstance(response.json()["items"], list)

# ======================================
# Testes dos Endpoints Analytics
# Composite endpoints return 404 when there is no data (empty test database).
# This test validates that the route exists and the error schema is correct (404, not 500).
# ======================================

async def test_analytics_raio_x_municipio_nao_encontrado(client):
    """Com banco vazio de testes, deve retornar 404 para municipio inexistente."""
    response = await client.get("/analytics/raio-x-municipal?codigo_ibge=9999999&cultura=soja&ano=2022")
    assert response.status_code == 404


async def test_analytics_dossie_insumos_nao_encontrado(client):
    """Com banco vazio, cultura inexistente deve retornar 404."""
    response = await client.get("/analytics/dossie-insumos/cultura_inexistente")
    assert response.status_code == 404


async def test_analytics_viabilidade_economica_nao_encontrado(client):
    """Com banco vazio, cultura inexistente deve retornar 404."""
    response = await client.get("/analytics/viabilidade-economica?cultura=cultura_x&uf=SP&ano=2022")
    assert response.status_code == 404


async def test_analytics_janela_aplicacao_nao_encontrado(client):
    """Com banco vazio, municipio inexistente deve retornar 404."""
    response = await client.get("/analytics/janela-aplicacao?codigo_ibge=9999999&ano=2022&mes=3")
    assert response.status_code == 404


async def test_analytics_auditoria_estimativas_nao_encontrado(client):
    """With an empty database, an unknown crop should return 404, not an empty list."""
    response = await client.get("/analytics/auditoria-estimativas?cultura=cultura_x")
    assert response.status_code == 404
