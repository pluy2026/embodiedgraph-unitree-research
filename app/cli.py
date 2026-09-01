"""Offline, JSON-first command-line access to the EmbodiedGraph snapshot.

The CLI deliberately reads the same SQLite snapshot as the HTTP API.  It is
useful in environments where starting a web server is inconvenient and gives
reviewers a reproducible, scriptable entry point to the research data.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date
from typing import Any

from app.db import connect, ensure_loaded


RELATIONSHIP_TYPES = ("supplier", "customer", "partner", "investor_or_investee", "peer")
STATUSES = ("confirmed", "probable", "unverified", "unknown")


def _company(connection: sqlite3.Connection, company_id: str) -> dict[str, Any]:
    row = connection.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
    if not row:
        raise LookupError(f"Company not found: {company_id}")
    result = dict(row)
    result["aliases"] = json.loads(result["aliases"])
    return result


def _evidence(connection: sqlite3.Connection, relationship_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT e.* FROM evidence e
        JOIN relationship_evidence re ON e.id=re.evidence_id
        WHERE re.relationship_id=? ORDER BY e.published_at DESC""",
        (relationship_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _relationship(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["from"] = _company(connection, result.pop("from_company_id"))
    result["to"] = _company(connection, result.pop("to_company_id"))
    result["confidence"] = max(
        0,
        result.pop("source_authority")
        + result.pop("directness")
        + result.pop("cross_validation")
        + result.pop("recency")
        + result.pop("entity_accuracy")
        - result.pop("conflict_penalty"),
    )
    result["evidence"] = _evidence(connection, result["id"])
    return result


def _page(items: list[dict[str, Any]], page: int, page_size: int) -> dict[str, Any]:
    return {
        "items": items[(page - 1) * page_size : page * page_size],
        "page": page,
        "page_size": page_size,
        "total": len(items),
        "total_pages": (len(items) + page_size - 1) // page_size,
    }


def _date_argument(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise argparse.ArgumentTypeError("Expected ISO date: YYYY-MM-DD") from error


def _pagination(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--page", type=int, default=1, help="1-based page number (default: 1)")
    parser.add_argument("--page-size", type=int, default=20, help="items per page, 1-100 (default: 20)")


def _validate_pagination(args: argparse.Namespace) -> None:
    if args.page < 1:
        raise ValueError("page must be at least 1")
    if not 1 <= args.page_size <= 100:
        raise ValueError("page-size must be between 1 and 100")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Query the local EmbodiedGraph SQLite research snapshot as JSON.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    companies = subcommands.add_parser("companies", help="List companies or institutions")
    companies.add_argument("--query", help="search name or alias")
    _pagination(companies)

    company = subcommands.add_parser("company", help="Get one company and its relationships")
    company.add_argument("company_id")

    relationships = subcommands.add_parser("relationships", help="List relationships with filters")
    relationships.add_argument("--company", help="company ID, e.g. unitree or hesai")
    relationships.add_argument("--relationship-type", choices=RELATIONSHIP_TYPES)
    relationships.add_argument("--status", choices=STATUSES)
    relationships.add_argument("--min-confidence", type=int, choices=range(0, 101), metavar="0..100")
    relationships.add_argument("--start-date", type=_date_argument, help="ISO date YYYY-MM-DD")
    relationships.add_argument("--end-date", type=_date_argument, help="ISO date YYYY-MM-DD")
    _pagination(relationships)

    relationship = subcommands.add_parser("relationship", help="Get one relationship and its evidence")
    relationship.add_argument("relationship_id")

    evidence = subcommands.add_parser("evidence", help="List evidence records")
    evidence.add_argument("--relationship-id", help="only evidence attached to this relationship")
    _pagination(evidence)

    graph = subcommands.add_parser("graph", help="Return graph nodes and edges")
    graph.add_argument("--relationship-type", choices=RELATIONSHIP_TYPES)
    graph.add_argument("--min-confidence", type=int, choices=range(0, 101), metavar="0..100")

    subcommands.add_parser("snapshot-info", help="Return the active local snapshot metadata")
    return parser


def execute(args: argparse.Namespace) -> dict[str, Any]:
    """Execute one CLI query and return data suitable for JSON serialization."""
    ensure_loaded()
    if hasattr(args, "page"):
        _validate_pagination(args)

    with connect() as connection:
        if args.command == "snapshot-info":
            return dict(connection.execute("SELECT * FROM snapshots LIMIT 1").fetchone())

        if args.command == "companies":
            query = (args.query or "").lower()
            rows = connection.execute(
                """SELECT * FROM companies
                WHERE ?='' OR lower(name) LIKE ? OR lower(aliases) LIKE ?
                ORDER BY name""",
                (query, f"%{query}%", f"%{query}%"),
            ).fetchall()
            return _page([
                {**dict(row), "aliases": json.loads(row["aliases"])} for row in rows
            ], args.page, args.page_size)

        if args.command == "company":
            entity = _company(connection, args.company_id)
            rows = connection.execute(
                """SELECT * FROM relationships
                WHERE from_company_id=? OR to_company_id=? ORDER BY updated_at DESC""",
                (args.company_id, args.company_id),
            ).fetchall()
            return {**entity, "relationships": [_relationship(connection, row) for row in rows]}

        if args.command in {"relationships", "graph"}:
            clauses: list[str] = []
            values: list[Any] = []
            if getattr(args, "company", None):
                clauses.append("(r.from_company_id=? OR r.to_company_id=?)")
                values.extend([args.company, args.company])
            if args.relationship_type:
                clauses.append("r.relationship_type=?")
                values.append(args.relationship_type)
            if getattr(args, "status", None):
                clauses.append("r.status=?")
                values.append(args.status)
            if args.min_confidence is not None:
                clauses.append("(r.source_authority+r.directness+r.cross_validation+r.recency+r.entity_accuracy-r.conflict_penalty)>=?")
                values.append(args.min_confidence)
            if getattr(args, "start_date", None):
                clauses.append("(r.start_date IS NULL OR r.start_date>=?)")
                values.append(args.start_date)
            if getattr(args, "end_date", None):
                clauses.append("(r.end_date IS NULL OR r.end_date<=?)")
                values.append(args.end_date)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = connection.execute(
                f"SELECT r.* FROM relationships r {where} ORDER BY r.updated_at DESC", values
            ).fetchall()
            relationships = [_relationship(connection, row) for row in rows]
            if args.command == "graph":
                nodes = {
                    item["from"]["id"]: item["from"] for item in relationships
                } | {item["to"]["id"]: item["to"] for item in relationships}
                return {
                    "nodes": list(nodes.values()),
                    "edges": [
                        {"id": item["id"], "source": item["from"]["id"], "target": item["to"]["id"],
                         "type": item["relationship_type"], "status": item["status"], "confidence": item["confidence"]}
                        for item in relationships
                    ],
                }
            return _page(relationships, args.page, args.page_size)

        if args.command == "relationship":
            row = connection.execute("SELECT * FROM relationships WHERE id=?", (args.relationship_id,)).fetchone()
            if not row:
                raise LookupError(f"Relationship not found: {args.relationship_id}")
            return _relationship(connection, row)

        if args.command == "evidence":
            if args.relationship_id:
                relationship_row = connection.execute("SELECT 1 FROM relationships WHERE id=?", (args.relationship_id,)).fetchone()
                if not relationship_row:
                    raise LookupError(f"Relationship not found: {args.relationship_id}")
                records = _evidence(connection, args.relationship_id)
            else:
                records = [dict(row) for row in connection.execute("SELECT * FROM evidence ORDER BY published_at DESC").fetchall()]
            return _page(records, args.page, args.page_size)

    raise ValueError(f"Unsupported command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        print(json.dumps(execute(args), ensure_ascii=False, indent=2))
    except (LookupError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
