from __future__ import annotations

import json
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from app.db import connect, ensure_loaded

RELATIONSHIP_TYPES = {"supplier", "customer", "partner", "investor_or_investee", "peer"}
STATUSES = {"confirmed", "probable", "unverified", "unknown"}
ROOT = Path(__file__).resolve().parents[1]


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_loaded()
    yield


app = FastAPI(
    title="EmbodiedGraph API",
    version="0.2.0",
    description="以宇树科技为中心的、可追溯的具身智能产业关系研究快照。",
    lifespan=lifespan,
)


def company(row: sqlite3.Row) -> dict:
    result = dict(row)
    result["aliases"] = json.loads(result["aliases"])
    return result


def evidence_rows(connection: sqlite3.Connection, relationship_id: str) -> list[dict]:
    rows = connection.execute("""SELECT e.* FROM evidence e JOIN relationship_evidence re ON e.id=re.evidence_id WHERE re.relationship_id=? ORDER BY e.published_at DESC""", (relationship_id,)).fetchall()
    return [dict(row) for row in rows]


def relationship(connection: sqlite3.Connection, row: sqlite3.Row) -> dict:
    result = dict(row)
    result["from"] = company(connection.execute("SELECT * FROM companies WHERE id=?", (result.pop("from_company_id"),)).fetchone())
    result["to"] = company(connection.execute("SELECT * FROM companies WHERE id=?", (result.pop("to_company_id"),)).fetchone())
    result["confidence"] = max(0, result.pop("source_authority") + result.pop("directness") + result.pop("cross_validation") + result.pop("recency") + result.pop("entity_accuracy") - result.pop("conflict_penalty"))
    result["evidence"] = evidence_rows(connection, result["id"])
    return result


def paged(rows: list[dict], page: int, page_size: int) -> dict:
    return {"items": rows[(page - 1) * page_size:page * page_size], "page": page, "page_size": page_size, "total": len(rows), "total_pages": (len(rows) + page_size - 1) // page_size}


@app.get("/health")
def health() -> dict:
    with connect() as connection:
        return {"ok": True, "snapshot": dict(connection.execute("SELECT * FROM snapshots LIMIT 1").fetchone())}


@app.get("/companies")
def list_companies(q: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)) -> dict:
    with connect() as connection:
        rows = connection.execute("SELECT * FROM companies WHERE ? IS NULL OR lower(name) LIKE ? OR lower(aliases) LIKE ? ORDER BY name", (q, f"%{(q or '').lower()}%", f"%{(q or '').lower()}%")).fetchall()
        return paged([company(row) for row in rows], page, page_size)


@app.get("/companies/{company_id}")
def get_company(company_id: str) -> dict:
    with connect() as connection:
        row = connection.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
        if not row:
            raise HTTPException(404, "公司不存在")
        rels = connection.execute("SELECT * FROM relationships WHERE from_company_id=? OR to_company_id=? ORDER BY updated_at DESC", (company_id, company_id)).fetchall()
        return {**company(row), "relationships": [relationship(connection, rel) for rel in rels]}


@app.get("/relationships")
def list_relationships(
    company: str | None = None,
    relationship_type: Literal["supplier", "customer", "partner", "investor_or_investee", "peer"] | None = None,
    status: Literal["confirmed", "probable", "unverified", "unknown"] | None = None,
    min_confidence: int | None = Query(None, ge=0, le=100),
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
) -> dict:
    clauses, values = [], []
    if company:
        clauses.append("(r.from_company_id=? OR r.to_company_id=?)"); values += [company, company]
    if relationship_type:
        clauses.append("r.relationship_type=?"); values.append(relationship_type)
    if status:
        clauses.append("r.status=?"); values.append(status)
    if min_confidence is not None:
        clauses.append("(r.source_authority+r.directness+r.cross_validation+r.recency+r.entity_accuracy-r.conflict_penalty)>=?"); values.append(min_confidence)
    if start_date:
        clauses.append("(r.start_date IS NULL OR r.start_date>=?)"); values.append(start_date)
    if end_date:
        clauses.append("(r.end_date IS NULL OR r.end_date<=?)"); values.append(end_date)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as connection:
        rows = connection.execute(f"SELECT r.* FROM relationships r {where} ORDER BY r.updated_at DESC", values).fetchall()
        return paged([relationship(connection, row) for row in rows], page, page_size)


@app.get("/relationships/{relationship_id}")
def get_relationship(relationship_id: str) -> dict:
    with connect() as connection:
        row = connection.execute("SELECT * FROM relationships WHERE id=?", (relationship_id,)).fetchone()
        if not row:
            raise HTTPException(404, "关系不存在")
        return relationship(connection, row)


@app.get("/evidence")
def list_evidence(relationship_id: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)) -> dict:
    with connect() as connection:
        if relationship_id:
            rows = evidence_rows(connection, relationship_id)
        else:
            rows = [dict(row) for row in connection.execute("SELECT * FROM evidence ORDER BY published_at DESC").fetchall()]
        return paged(rows, page, page_size)


@app.get("/graph")
def graph(relationship_type: str | None = None, min_confidence: int | None = Query(None, ge=0, le=100)) -> dict:
    if relationship_type and relationship_type not in RELATIONSHIP_TYPES:
        raise HTTPException(422, "无效关系类型")
    result = list_relationships(relationship_type=relationship_type, min_confidence=min_confidence, page=1, page_size=100)
    nodes = {item["from"]["id"]: item["from"] for item in result["items"]} | {item["to"]["id"]: item["to"] for item in result["items"]}
    return {"nodes": list(nodes.values()), "edges": [{"id": item["id"], "source": item["from"]["id"], "target": item["to"]["id"], "type": item["relationship_type"], "status": item["status"], "confidence": item["confidence"]} for item in result["items"]]}


app.mount("/", StaticFiles(directory=ROOT / "public", html=True), name="web")
