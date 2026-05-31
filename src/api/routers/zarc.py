from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.dependencies import get_session
from api.utils import paginate_query
from db.manager import DimCultura, DimMunicipio, FatoRiscoZARC

router = APIRouter(prefix="/zarc", tags=["ZARC - Zoneamento Agrícola"])

# ==========================================
# RISCO CLIMÁTICO
# ==========================================


@router.get("/risco")
def listar_risco_zarc(
    codigo_ibge: Optional[str] = Query(None, description="Código IBGE do município"),
    cultura: Optional[str] = Query(None, description="Filtro por cultura"),
    id_solo: Optional[str] = Query(None, description="Tipo de solo (1, 2 ou 3)"),
    page: int = Query(1, ge=1, description="Número da página"),
    page_size: int = Query(20, ge=1, le=100, description="Itens por página (máximo: 100)"),
    db: Session = Depends(get_session),
) -> dict:
    """
    Lista dados de zoneamento de risco climático ZARC a partir do PostgreSQL.
    Permite filtrar por código IBGE do município, nome padronizado da cultura e tipo de solo.
    """
    query = (
        db.query(
            FatoRiscoZARC.periodo_plantio,
            FatoRiscoZARC.tipo_solo,
            FatoRiscoZARC.risco_climatico,
            DimCultura.nome_padronizado.label("cultura"),
            DimMunicipio.nome.label("municipio"),
            DimMunicipio.uf,
        )
        .join(DimCultura, FatoRiscoZARC.id_cultura == DimCultura.id_cultura)
        .join(DimMunicipio, FatoRiscoZARC.id_municipio == DimMunicipio.id_municipio)
    )

    if codigo_ibge:
        query = query.filter(DimMunicipio.codigo_ibge == codigo_ibge)
    if cultura:
        query = query.filter(DimCultura.nome_padronizado == cultura.lower())
    if id_solo:
        query = query.filter(FatoRiscoZARC.tipo_solo == str(id_solo))

    res = paginate_query(query, page, page_size)
    res["items"] = [dict(r._mapping) for r in res["items"]]
    return res
