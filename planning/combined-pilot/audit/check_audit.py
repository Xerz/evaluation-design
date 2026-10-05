"""Check that the audit keeps every historical scientific link and honest states."""
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DB = ROOT / "outputs/01a05c37-c522-7563-8846-1ea43a7a49d5/База пилота автоматизации критериев ТюмГУ.sqlite"


def read(name):
    return json.loads((HERE / name).read_text())


def check():
    provenance = read("provenance.json")
    assert hashlib.sha256(DB.read_bytes()).hexdigest() == provenance["historical_database_sha256"]
    assert provenance["real_bot_calls"] == 0 and provenance["operational_data_included"] is False
    matrix = read("criteria-matrix.json")
    assert [c["code"] for c in matrix["criteria"]] == [f"C{i:02}" for i in range(1, 27)]
    assert sum(c["mgpu_potential"] for c in matrix["criteria"]) == 13
    assert all(c["status"] == "candidate" for c in matrix["criteria"])
    mappings = matrix["mappings"]
    assert len(mappings) == len({r["mapping_code"] for r in mappings}) == 36
    assert all(r["evidence_status"] == "not_validated" for r in mappings)
    bibliography = {s["code"]: s for s in read("bibliography-checks.json")}
    assert set(bibliography) == {f"S{i:02}" for i in range(1, 48)}
    assert bibliography["S28"]["publication_status"] == "withdrawn"
    assert bibliography["S05"]["canonical_doi"] == "10.1187/cbe.14-06-0095"
    links = read("link-review.json")["links"]
    assert len(links) == len({r["link_code"] for r in links}) == 135
    assert all(r["verified_paper_locator"] is None for r in links)
    assert all(r["review_status"] == "excluded_withdrawn" for r in links if r["source_code"] == "S28")
    with closing(sqlite3.connect(DB.resolve().as_uri() + "?mode=ro", uri=True)) as con:
        old = set(con.execute(
            "SELECT c.code,s.code,l.relation_role,l.relevance_status,l.supported_claim,l.source_locator,l.notes "
            "FROM criterion_research_sources l JOIN criteria c ON c.id=l.criterion_id "
            "JOIN research_sources s ON s.id=l.research_source_id"))
        new = {tuple(r[k] for k in ("criterion_code", "source_code", "relation_role", "relevance_status",
                                  "supported_claim", "source_locator", "notes"))
               for r in links if r["link_kind"] == "criterion_source"}
        assert len(old) == 111 and old == new
        old = set(con.execute(
            "SELECT m.code,s.code,l.relation_role,l.notes FROM verification_method_research_sources l "
            "JOIN verification_methods m ON m.id=l.verification_method_id "
            "JOIN research_sources s ON s.id=l.research_source_id"))
        new = {tuple(r[k] for k in ("method_code", "source_code", "relation_role", "notes"))
               for r in links if r["link_kind"] == "method_source"}
        assert len(old) == 24 and old == new
    assert len(read("mgpu-definitions.json")["metrics"]) == 41
    assert len(read("protocol-readiness.json")) == 9
    new_links = read("new-method-source-links.json")["links"]
    assert len(new_links) == len({r["link_code"] for r in new_links}) == 2
    assert all(r["source_code"] == "S27" and r["review_status"] == "partial_support"
               and r["verified_paper_locator"] for r in new_links)
    claims = read("claim-checks-v2.json")
    assert len(claims["claims"]) == len({r["link_code"] for r in claims["claims"]}) == 137
    assert set(r["link_code"] for r in claims["claims"]) == set(r["link_code"] for r in links + new_links)
    reviews = read("source-content-checks-v2.json")["reviews"]
    review_ids = {r["id"]:r for r in reviews}
    assert len(reviews) == len(review_ids) == 22
    assert len({r["source_code"] for r in reviews}) == 18
    assert all(not r["supported_claim"] or (r["verified_locator"] and r["source_review_id"] in review_ids)
               for r in claims["claims"])
    assert all(r["review_status"] == "excluded_withdrawn" and r["supported_claim"] is None
               for r in claims["claims"] if r["source_code"] == "S28")
    assert claims["criteria_validation_claimed"] is False
    local = read("local-verification.json")
    assert local["unit_tests"]["status"] == "passed"
    assert local["real_bot_calls"] == local["real_recordings_checked"] == 0
    return {"status": "passed", "criteria": 26, "candidate_mappings": 36,
            "bibliography": 47, "historical_links": 135, "new_partial_method_links": 2,
            "source_database": "unchanged", "claim_reviews":137, "sources_with_bounded_content_reviews":18}


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False))
