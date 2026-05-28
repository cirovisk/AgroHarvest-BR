"""
Configurações globais e constantes estruturais do projeto AgroHarvest.
"""

# Lista unificada de culturas alvo no formato de chave de indexação (sem acentuação)
CULTURAS_ALVO = ["soja", "milho", "trigo", "algodao", "cana-de-acucar"]

# Mapeamento oficial de chaves de culturas para IDs do IBGE/SIDRA (Tabela 5457)
CULTURAS_IBGE_IDS = {
    "soja": 40124,
    "milho": 40122,
    "trigo": 40127,
    "algodao": 40100,
    "cana-de-acucar": 40111
}

# Versão legível com acentuação para fins de exibição se necessário
CULTURAS_EXIBICAO = {
    "soja": "Soja",
    "milho": "Milho",
    "trigo": "Trigo",
    "algodao": "Algodão",
    "cana-de-acucar": "Cana-de-açúcar"
}
