from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.cli import build_parser, execute
from app.db import load_snapshot
from app.main import app
from app.scoring import RelationshipInput, ScoreInput, corroboration_points


def client():
    load_snapshot()
    return TestClient(app)


def test_companies_and_pagination():
    response = client().get("/companies?page=1&page_size=5")
    assert response.status_code == 200
    assert response.json()["total"] >= 15
    assert len(response.json()["items"]) == 5


def test_relationship_filters_and_graph():
    response = client().get("/relationships?relationship_type=partner&min_confidence=50")
    assert response.status_code == 200
    assert response.json()["total"] >= 3
    graph = client().get("/graph?relationship_type=peer")
    assert graph.status_code == 200
    assert len(graph.json()["edges"]) >= 3


def test_invalid_type_and_missing_record():
    assert client().get("/relationships?relationship_type=invalid").status_code == 422
    assert client().get("/companies/not-a-company").status_code == 404


def test_score_and_missing_evidence_boundary():
    score = ScoreInput(source_authority=35, directness=25, cross_validation=15, recency=15, entity_accuracy=10)
    assert score.score == 100 and score.status == "confirmed"
    try:
        RelationshipInput(status="confirmed", evidence_ids=[], score=score)
        assert False, "confirmed 应拒绝缺失证据"
    except ValidationError:
        pass


def test_shared_source_is_not_cross_validation():
    official_round_url = "https://www.unitree.com/operate/company/"
    assert corroboration_points([official_round_url]) == 0
    assert corroboration_points([official_round_url, official_round_url]) == 0
    assert corroboration_points([official_round_url, "https://example.com/corroborates"]) == 8


def test_shared_ap_article_has_no_cross_validation_bonus():
    items = client().get("/relationships?relationship_type=peer&page_size=100").json()["items"]
    shared = [item for item in items if any(evidence["id"] == "e6" for evidence in item["evidence"])]
    assert len(shared) == 3
    assert all(item["confidence"] == 55 for item in shared)


def test_missing_publication_date_gets_conservative_recency_score():
    items = client().get("/relationships?page_size=100").json()["items"]
    cmu = next(item for item in items if item["from"]["id"] == "cmu")
    assert cmu["confidence"] == 68

    investors = client().get("/relationships?relationship_type=investor_or_investee").json()["items"]
    jinghshi = next(item for item in investors if item["from"]["id"] == "jingshi")
    assert jinghshi["confidence"] == 76
    assert jinghshi["scope_class"] == "listed_group_affiliate"


def test_evidence_locators_use_one_chinese_ui_style():
    evidence = client().get("/evidence?page_size=100").json()["items"]
    assert all(item["locator"] for item in evidence)
    assert next(item for item in evidence if item["id"] == "e2")["locator"] == "开篇段落"
    assert next(item for item in evidence if item["id"] == "e23")["locator"] == "硬件设置章节"


def test_local_snapshot_contains_evidence_gap():
    response = client().get("/evidence?page_size=100")
    assert response.status_code == 200
    assert any(item["availability"] == "unavailable" for item in response.json()["items"])
    allowed = {"public", "login_required_excluded", "paywalled_excluded", "not_external_source"}
    assert all(item["access_status"] in allowed for item in response.json()["items"])
    public_no_login = next(item for item in response.json()["items"] if item["id"] == "e12")
    assert public_no_login["access_status"] == "public"


def test_mvp_excludes_research_gaps_from_relationship_count():
    items = client().get("/relationships?page_size=100").json()["items"]
    counts = {}
    for item in items:
        counts[item["relationship_type"]] = counts.get(item["relationship_type"], 0) + 1
    assert len(items) == 34
    assert counts == {"supplier": 7, "customer": 7, "partner": 7, "investor_or_investee": 7, "peer": 6}
    assert all(all(evidence["id"] != "e10" for evidence in item["evidence"]) for item in items)


def test_livox_is_explicitly_limited_to_a_third_party_usage_record():
    items = client().get("/relationships?relationship_type=supplier&page_size=100").json()["items"]
    livox = next(item for item in items if item["from"]["id"] == "livox")
    assert "第三方设备配置" in livox["summary"]
    assert "不是宇树或览沃的供货声明" in livox["uncertainty"]
    assert "not a supply statement" in livox["evidence"][0]["excerpt"]


def test_publishers_are_canonicalized():
    items = client().get("/evidence?page_size=100").json()["items"]
    nvidia_publishers = {item["publisher"] for item in items if "nvidia.com" in (item["url"] or "")}
    assert nvidia_publishers == {"NVIDIA"}


def test_investors_are_replaced_with_officially_disclosed_historical_round():
    response = client().get("/relationships?relationship_type=investor_or_investee&status=confirmed")
    investors = response.json()["items"]
    ids = {item["from"]["id"] for item in investors}
    assert {"meituan", "jingshi", "sourcecode", "scvc"}.issubset(ids)
    assert all(any(evidence["id"] == "e12" for evidence in item["evidence"]) for item in response.json()["items"])


def test_extra_articles_improve_traceability_without_false_corroboration():
    investors = client().get("/relationships?relationship_type=investor_or_investee&page_size=100").json()["items"]
    meituan = next(item for item in investors if item["from"]["id"] == "meituan")
    assert {"e12", "e29", "e30", "e34"}.issubset({evidence["id"] for evidence in meituan["evidence"]})
    assert meituan["confidence"] == 81
    assert meituan["scope_class"] == "listed_issuer_or_group"

    nonlisted = [item for item in investors if item["scope_class"] == "nonlisted_capital_record"]
    assert {item["from"]["id"] for item in nonlisted} == {"sourcecode", "scvc", "rongyi", "dunhong", "ciif"}

    peers = client().get("/relationships?relationship_type=peer&page_size=100").json()["items"]
    agibot = next(item for item in peers if item["to"]["id"] == "agibot")
    assert {"e6", "e31", "e32"}.issubset({evidence["id"] for evidence in agibot["evidence"]})
    assert agibot["confidence"] == 55


def test_cli_uses_the_same_snapshot_for_filtering_and_graph_queries():
    parser = build_parser()
    relationships = execute(parser.parse_args([
        "relationships", "--company", "unitree", "--relationship-type", "supplier",
        "--status", "confirmed", "--min-confidence", "70",
    ]))
    assert relationships["total"] == 2
    assert all(item["relationship_type"] == "supplier" for item in relationships["items"])

    graph = execute(parser.parse_args(["graph", "--relationship-type", "partner", "--min-confidence", "60"]))
    assert graph["edges"] and all(edge["type"] == "partner" for edge in graph["edges"])


def test_cli_rejects_invalid_pagination():
    parser = build_parser()
    try:
        execute(parser.parse_args(["relationships", "--page", "0"]))
        assert False, "CLI should reject page 0"
    except ValueError as error:
        assert "page must be" in str(error)
