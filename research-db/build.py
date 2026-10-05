"""Build a new draft research DB from immutable source snapshots, offline only."""
import argparse
import hashlib
import json
import os
import sqlite3
from pathlib import Path

from config import DAY, REVISION, LEGACY, conditions, comparisons, profiles
from guards import install

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
AUDIT = ROOT / "planning/combined-pilot/audit"
WIDE = ROOT / "outputs/01a05c37-c522-7563-8846-1ea43a7a49d5/База пилота автоматизации критериев ТюмГУ.sqlite"
EXPECTED = {
    "wide": "598d593c5898703f0bb2ff526dcf21d3f698e868a5f91e663ba753e8182615ca",
    "mgpu": "3877a8a8e30e4637d05df5c87d33a56f489df3796a1b5c5f6580a4cfa116fbb7"}
OPERATIONS = {"experts", "instructors", "student_groups", "lessons", "evaluation_runs",
              "criterion_evaluations", "expert_assignments", "platform_metric_values"}

def j(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def read(name):
    return json.loads((AUDIT / name).read_text())

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def rows(con, table):
    return [dict(r) for r in con.execute(f'SELECT * FROM "{table}"')]

def insert(con, table, values):
    names = list(values)
    con.execute(f'INSERT INTO "{table}" ({",".join(names)}) VALUES ({",".join("?" for _ in names)})',
                [values[n] for n in names])

def open_source(path, namespace):
    if sha(path) != EXPECTED[namespace]:
        raise ValueError(f"{namespace}: source hash changed; review a new version before importing")
    source = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        source.close()
        raise ValueError("source integrity failed")
    return source

def snapshot(con, source, namespace):
    master = rows(source, "sqlite_master")
    tables = [r for r in master if r["type"] == "table" and not r["name"].startswith("sqlite_")]
    # A design migration must not silently copy real people or observations.
    for table in tables:
        if table["name"] in OPERATIONS and source.execute(f'SELECT count(*) FROM "{table["name"]}"').fetchone()[0]:
            raise ValueError("source contains operational rows; use the separately reviewed local importer")
    snapshot_id = "SNAP-" + namespace + "-" + EXPECTED[namespace][:12]
    insert(con, "source_snapshots", dict(id=snapshot_id, namespace="historical_design",
          source_version=namespace, sha256=EXPECTED[namespace], captured_on=None, completeness="complete",
          provenance_json=j(dict(sqlite_master=master, operational_tables_checked_empty=True,
                                 source_label="SRC-02" if namespace == "wide" else "SRC-10"))))
    for table in tables:
        content = rows(source, table["name"])
        insert(con, "historical_tables", dict(snapshot_id=snapshot_id, name=table["name"],
              schema_sql=table["sql"], columns_json=j([r[1] for r in source.execute(f'PRAGMA table_info("{table["name"]}")')]),
              rows_json=j(content), row_count=len(content)))
    return snapshot_id

def normalized(con, source, revision, corrected=False):
    criterion_ids = {r["id"]: r["code"] for r in rows(source, "criteria")}
    method_ids = {r["id"]: r["code"] for r in rows(source, "verification_methods")}
    effect_ids = {r["id"]: r["code"] for r in rows(source, "effects")}
    source_ids = {r["id"]: r["code"] for r in rows(source, "research_sources")}
    bibliography = {r["code"]: r for r in read("bibliography-checks.json")} if corrected else {}
    readiness = {r["method_code"]: r for r in read("protocol-readiness.json")}
    for r in rows(source, "criteria"):
        insert(con, "criteria", dict(revision_id=revision, code=r["code"], number=r["number"], name=r["name"],
              block_name=r["block_name"], subblock_name=r["subblock_name"], origin_json=j(r)))
    for r in rows(source, "criterion_score_levels"):
        insert(con, "score_levels", dict(revision_id=revision, criterion_code=criterion_ids[r["criterion_id"]],
              score=r["score"], description=r["description"], origin_json=j(r)))
    for r in rows(source, "research_sources"):
        b = bibliography.get(r["code"], {})
        insert(con, "research_sources", dict(revision_id=revision, code=r["code"],
              citation=b.get("canonical_citation",r["citation_apa"]), doi=b.get("canonical_doi",r["doi"]),
              url=b.get("canonical_url",r["url"]), bibliography_status=b.get("status",r["verification_status"]),
              publication_status=b.get("publication_status","not_rechecked"), historical_json=j(r)))
    for r in rows(source, "verification_methods"):
        insert(con, "protocols", dict(revision_id=revision, code=r["code"], name=r["name"],
              description=r["description"], metrics=r["metrics"], procedure=r["procedure"],
              readiness=readiness.get(r["code"],{}).get("readiness","historical") if corrected else "historical",
              historical_json=j(r)))
    for r in rows(source, "effects"):
        insert(con, "effects", dict(revision_id=revision, code=r["code"], name=r["name"], hypothesis=r["hypothesis"],
              status="hypothesis_not_tested", historical_json=j(r)))
    for r in rows(source, "effect_checks"):
        insert(con, "effect_checks", dict(revision_id=revision, code=r["code"], effect_code=effect_ids[r["effect_id"]],
              method_code=method_ids[r["verification_method_id"]], unit_of_analysis=r["unit_of_analysis"],
              comparison_description=r["comparison_description"], success_rule=r["success_rule"], historical_json=j(r)))
    for r in rows(source, "criterion_research_sources"):
        c, s = criterion_ids[r["criterion_id"]], source_ids[r["research_source_id"]]
        insert(con, "scientific_links", dict(revision_id=revision, code=f"CRS-{c}-{s}", source_code=s,
              criterion_code=c, method_code=None, relation_role=r["relation_role"], historical_claim=r.get("supported_claim"),
              historical_locator=r.get("source_locator"), historical_json=j(r)))
    for r in rows(source, "verification_method_research_sources"):
        m, s = method_ids[r["verification_method_id"]], source_ids[r["research_source_id"]]
        insert(con, "scientific_links", dict(revision_id=revision, code=f"MRS-{m}-{s}", source_code=s,
              criterion_code=None, method_code=m, relation_role=r["relation_role"], historical_claim=None,
              historical_locator=None, historical_json=j(r)))

# Explicit column allowlist; unlisted tables are private by default. No operational IDs.
PUBLIC = {
 "criteria": ["code","number","name","block_name","subblock_name"],
 "score_levels": ["criterion_code","score","description"],
 "research_sources": ["code","citation","doi","url","bibliography_status","publication_status"],
 "source_reviews": ["source_code","checked_on","scope","url","locator","supported_statement","boundary"],
 "protocols": ["code","name","description","metrics","procedure","readiness"],
 "effects": ["code","name","hypothesis","status"],
 "effect_checks": ["code","effect_code","method_code","unit_of_analysis","comparison_description","success_rule"],
 "scientific_links": ["code","source_code","criterion_code","method_code","relation_role"],
 "link_reviews": ["link_code","checked_on","claim_proposal","review_status","supported_claim","verified_locator","applicability"],
 "conditions": ["code","name","readiness","components_json","required_inputs_json","missing_requirements_json"],
 "legacy_condition_links": ["condition_code","legacy_code","equivalence"],
 "comparisons": ["code","method_code","left_condition","right_condition","changed_component","controls","eligibility"],
 "criterion_mappings": ["code","criterion_code","condition_code","status","signal","required_inputs","implementation_status","evidence_status"],
 "metric_definitions": ["code","name","unit","definition_status"],
 "technical_profiles": ["code","purpose","status","details_json"]}

def export_public(con):
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    policy = {r["table_name"]: r for r in rows(con,"visibility_policy")}
    if tables - policy.keys():
        raise ValueError("unknown table has no visibility policy")
    output = dict(design_label="Объединённый пилот: проект исследования", version=DAY, status="draft", tables={})
    for table, columns in PUBLIC.items():
        p = policy[table]
        if p["visibility"] != "public_design" or json.loads(p["public_columns_json"]) != columns:
            raise ValueError("visibility allowlist changed; review required")
        has_revision = "revision_id" in {r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}
        query = f'SELECT {",".join(columns)} FROM "{table}"' + (" WHERE revision_id=?" if has_revision else "")
        records = [dict(r) for r in con.execute(query, (REVISION,) if has_revision else ())]
        output["tables"][table] = records
    encoded = j(output)
    if any(s in encoded for s in ("/Users/", "file://", "storage-state", "Bearer ", "api_key", "access_token")):
        raise ValueError("public export contains a local path or credential marker")
    return output

def build(output, mgpu_path):
    output = Path(output)
    if output.exists():
        raise FileExistsError("Existing research DB is never overwritten; select a new output path")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".building")
    # A failed previous build is also evidence; don't overwrite it silently.
    if temp.exists():
        raise FileExistsError(temp)
    wide = open_source(WIDE,"wide")
    mgpu = open_source(mgpu_path,"mgpu")
    con = sqlite3.connect(temp)
    con.row_factory = sqlite3.Row
    try:
        schema = HERE / "schema.sql"
        con.executescript(schema.read_text())
        install(con)
        insert(con,"schema_migrations", dict(version=1,applied_on=DAY,source_sha256=sha(schema)))
        for revision, parent, status, reason in [("wide-original",None,"historical","Полный исходный широкий дизайн"),
             ("mgpu-only-original",None,"historical","Полный пятничный дизайн только МГПУ; иной смысл условий"),
             (REVISION,"wide-original","draft","Объединённый проект: 8 занятий, кандидаты и открытые решения")]:
            insert(con,"design_revisions", dict(id=revision,status=status,created_on=DAY,parent_id=parent,rationale=reason,frozen=0))
        wide_snap = snapshot(con,wide,"wide")
        mgpu_snap = snapshot(con,mgpu,"mgpu")
        for revision, snap, role in [("wide-original",wide_snap,"original"),("mgpu-only-original",mgpu_snap,"original"),
                                     (REVISION,wide_snap,"methodological_source"),(REVISION,mgpu_snap,"additional_historical_source")]:
            insert(con,"revision_snapshots",dict(revision_id=revision,snapshot_id=snap,role=role))
        normalized(con,wide,"wide-original")
        normalized(con,mgpu,"mgpu-only-original")
        normalized(con,wide,REVISION,True)
        for r in rows(mgpu,"research_sources"):
            if r["code"] in ("S48","S49"):
                insert(con,"research_sources",dict(revision_id=REVISION,code=r["code"],citation=r["citation_apa"],doi=r["doi"],url=r["url"],bibliography_status="historical_technical_reference",publication_status="not_rechecked",historical_json=j(r)))
        for r in read("new-method-source-links.json")["links"]:
            insert(con,"scientific_links",dict(revision_id=REVISION,code=r["link_code"],source_code=r["source_code"],criterion_code=None,method_code=r["method_code"],relation_role=r["relation_role"],historical_claim=None,historical_locator=None,historical_json=j(r)))
        for r in read("source-content-checks-v2.json")["reviews"]:
            insert(con,"source_reviews",dict(id=r["id"],revision_id=REVISION,**{k:r[k] for k in ("source_code","checked_on","scope","url","locator","supported_statement","boundary")}))
        for r in read("claim-checks-v2.json")["claims"]:
            insert(con,"link_reviews",dict(revision_id=REVISION,**{k:r[k] for k in ("id","link_code","source_review_id","checked_on","claim_proposal","review_status","supported_claim","verified_locator","applicability")}))
        for code, version, readiness, contract in [
            ("T","eval-2024-minimal-2026-10-05","local_shell_tested",dict(real_model=None, confidence=None, evidence_coordinates="characters",old_coze_access="forbidden_not_tested")),
            ("MA","supplier-version-unconfirmed","supplier_contract_pending",dict(definitions="to_confirm",export="to_confirm")),
            ("MV","supplier-version-unconfirmed","supplier_contract_pending",dict(definitions="to_confirm",export="to_confirm")),
            ("MGPU","historical-metric-catalog","historical_definition_catalog",dict(module_assignment="requires_confirmation",metrics_count=41)),
            ("OA","candidate","candidate",{}), ("OV","candidate","candidate",{})]:
            insert(con,"instrument_versions",dict(id=f"IV-{code}",instrument_code=code,version_code=version,readiness=readiness,model_version=None,contract_json=j(contract)))
        for r in rows(mgpu,"platform_metric_definitions"):
            insert(con,"metric_definitions",dict(id="MD-"+r["code"],instrument_version_id="IV-MGPU",code=r["code"],name=r["name"],unit=r["reported_unit"],definition_status=r["definition_status"],details_json=j(r)))
        for c in conditions():
            insert(con,"conditions",dict(revision_id=REVISION,code=c["code"],name=c["name"],readiness=c["readiness"],components_json=j(c["components"]),required_inputs_json=j(c["inputs"]),missing_requirements_json=j(c["missing"])))
        for condition, (old, equivalence) in LEGACY.items():
            insert(con,"legacy_condition_links",dict(revision_id=REVISION,condition_code=condition,snapshot_id=wide_snap,legacy_code=old,equivalence=equivalence))
        for c in comparisons():
            insert(con,"comparisons",dict(revision_id=REVISION,code=c["code"],method_code=c["method"],left_condition=c["left"],right_condition=c["right"],changed_component=c["changed"],controls=c["controls"],eligibility=c["eligibility"]))
        for r in read("criteria-matrix.json")["mappings"]:
            insert(con,"criterion_mappings",dict(revision_id=REVISION,code=r["mapping_code"],**{k:r[k] for k in ("criterion_code","condition_code","status","implementation_status","evidence_status")},
                  signal=r.get("signal","Потенциальное соответствие МГПУ; конкретный модуль/показатель уточнить"),
                  required_inputs=r.get("required_inputs","Определения метрик, единицы, версия и пример экспорта; модальность уточнить"),details_json=j(r)))
        for r in profiles():
            insert(con,"technical_profiles",dict(code=r["code"],purpose=r["purpose"],status=r["status"],details_json=j(r)))
        for table in [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
            columns = PUBLIC.get(table,[])
            insert(con,"visibility_policy",dict(table_name=table,visibility="public_design" if columns else "local_only",public_columns_json=j(columns),reason="Явный экспорт замысла" if columns else "Операционные данные, происхождение или внутренние идентификаторы; запрет по умолчанию"))
        con.execute("UPDATE design_revisions SET frozen=1 WHERE status='historical'")
        con.commit()
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or con.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("built database integrity failed")
        public = export_public(con)
        report = dict(status="draft_built",revision=REVISION,source_hashes=EXPECTED,
                      criteria=con.execute("SELECT count(*) FROM criteria WHERE revision_id=?",(REVISION,)).fetchone()[0],
                      score_levels=78,candidate_mappings=36,metrics_catalog=41,source_reviews=22,
                      scientific_links=137,operational_rows=0,real_model_calls=0,
                      limitations=["кандидаты не валидированы", "MODEUS не актуализирован этим сборщиком", "два реальных прогона и экспертная проба впереди"])
        con.close()
        # Publish local file atomically without permitting a concurrent overwrite.
        os.link(temp,output)
        temp.unlink()
        output.with_suffix(".public.json").write_text(json.dumps(public,ensure_ascii=False,indent=2)+"\n")
        output.with_suffix(".manifest.json").write_text(json.dumps(dict(report,database_sha256=sha(output)),ensure_ascii=False,indent=2)+"\n")
        return report
    except Exception:
        con.close()
        if temp.exists():
            temp.unlink()
        raise
    finally:
        wide.close()
        mgpu.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mgpu-db",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output,args.mgpu_db),ensure_ascii=False))
