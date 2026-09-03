"""
Global settings and structural constants for the AgroHarvest project.
"""

# Unified target crop list in index-key format (without accents)
CULTURAS_ALVO = ["soja", "milho", "trigo", "algodao"]

# Official crop-key mapping to IBGE/SIDRA IDs (Table 5457)
CULTURAS_IBGE_IDS = {"soja": 40124, "milho": 40122, "trigo": 40127, "algodao": 40100}

# Human-readable version with accents for display when needed
CULTURAS_EXIBICAO = {
    "soja": "Soja",
    "milho": "Milho",
    "trigo": "Trigo",
    "algodao": "Algodão",
}
