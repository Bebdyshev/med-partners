from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.dto import SearchOut
from app.services.search import search_partners, search_services

router = APIRouter()


@router.get("/search", response_model=SearchOut, summary="Поиск по услугам и партнёрам",
            description="Гибридный поиск: FTS + расширение аббревиатур → семантика → триграммы (опечатки).")
def search(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    return SearchOut(
        services=search_services(db, q),
        partners=search_partners(db, q),
    )
