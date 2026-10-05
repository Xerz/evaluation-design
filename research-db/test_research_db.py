import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from build import PUBLIC, REVISION, build, export_public, insert, j, sha
from config import profiles
from guards import install
from import_modeus import load
from sampling import prepare

HERE=Path(__file__).resolve().parent

class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:"); self.c.row_factory=sqlite3.Row
        self.c.executescript((HERE/"schema.sql").read_text());install(self.c)
        for r in (REVISION,"other"):
            insert(self.c,"design_revisions",dict(id=r,status="draft",created_on="2026-10-06",parent_id=None,rationale="test",frozen=0))
            insert(self.c,"criteria",dict(revision_id=r,code="C01",number=1,name="test",block_name=None,subblock_name=None,origin_json="{}"))
            for code in ("T","REF-REC","EXP-AI"):
                insert(self.c,"conditions",dict(revision_id=r,code=code,name=code,readiness="test",components_json="[]",required_inputs_json="[]",missing_requirements_json="[]"))
        p=profiles()[0]
        insert(self.c,"technical_profiles",dict(code=p["code"],purpose=p["purpose"],status=p["status"],details_json=j(p)))
        insert(self.c,"instrument_versions",dict(id="iv",instrument_code="T",version_code="test",readiness="test",model_version=None,contract_json="{}"))
        for id,kind in (("teacher","teacher"),("group","group"),("expert","expert"),("lesson","lesson"),("artifact","artifact"),("run","run"),("assignment","assignment"),("result","result")):
            insert(self.c,"entities",dict(id=id,revision_id=REVISION,kind=kind))
        insert(self.c,"lessons",dict(id="lesson",revision_id=REVISION,discipline_id="mup",teacher_entity_id="teacher",group_entity_id="group",starts_at="2026-10-10T10:00:00+05:00",timezone="Asia/Yekaterinburg",lesson_type="SEMI",slot_role="trial",state="candidate",profile_code="TP-AUDIO",metadata_json="{}"))
        insert(self.c,"artifacts",dict(id="artifact",revision_id=REVISION,lesson_id="lesson",kind="transcript",version_code="1",sha256="a"*64,parent_artifact_id=None,duration_ms=None,character_count=100,qc_status="unchecked",provenance_json="{}"))
        insert(self.c,"runs",dict(id="run",revision_id=REVISION,lesson_id="lesson",condition_code="T",instrument_version_id="iv",prompt_version="1",model_version=None,config_sha256="b"*64,status="prepared",repeat_of=None))
        insert(self.c,"assignments",dict(id="assignment",revision_id=REVISION,lesson_id="lesson",expert_entity_id="expert",condition_code="REF-REC",codebook_version="1",status="prepared",pinned_ai_run_id=None))

    def tearDown(self):self.c.close()

    def result(self,**kwargs):
        r=dict(id="result",revision_id=REVISION,criterion_code="C01",run_id="run",assignment_id=None,result_status="scored",score=1,confidence=None,confidence_meaning=None,rationale=None,raw_json=None);r.update(kwargs)
        insert(self.c,"results",r)

    def evidence(self,**kwargs):
        self.result()
        r=dict(id="ev",result_id="result",artifact_id="artifact",locator_kind="characters",start_char=2,end_char=10,start_ms=None,end_ms=None,document_locator=None,quote="test",interpretation_status="unreviewed");r.update(kwargs)
        insert(self.c,"evidence",r)

    def test_error_cannot_be_zero(self):
        with self.assertRaises(sqlite3.IntegrityError):self.result(result_status="error",score=0)

    def test_missing_is_null(self):
        self.result(result_status="insufficient_data",score=None)
        self.assertIsNone(self.c.execute("SELECT score FROM results").fetchone()[0])

    def test_scored_requires_score(self):
        with self.assertRaises(sqlite3.IntegrityError):self.result(score=None)

    def test_confidence_requires_meaning(self):
        with self.assertRaises(sqlite3.IntegrityError):self.result(confidence=.8)

    def test_cross_revision_result(self):
        with self.assertRaises(sqlite3.IntegrityError):self.result(revision_id="other")

    def test_update_cross_revision_result(self):
        self.result()
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute("UPDATE results SET revision_id='other'")

    def test_characters_not_fake_time(self):
        with self.assertRaises(sqlite3.IntegrityError):self.evidence(locator_kind="milliseconds",start_char=None,end_char=None,start_ms=0,end_ms=10)

    def test_evidence_bounds(self):
        with self.assertRaises(sqlite3.IntegrityError):self.evidence(end_char=101)

    def test_update_evidence_bounds(self):
        self.evidence()
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute("UPDATE evidence SET end_char=101")

    def test_blind_assignment_cannot_pin_ai(self):
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute("UPDATE assignments SET pinned_ai_run_id='run'")

    def test_ai_assignment_requires_pin(self):
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute("UPDATE assignments SET condition_code='EXP-AI'")

    def test_ai_assignment_valid_pin(self):
        self.c.execute("UPDATE assignments SET condition_code='EXP-AI',pinned_ai_run_id='run'")

    def test_teacher_kind_cannot_be_expert(self):
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute("UPDATE lessons SET teacher_entity_id='expert'")

    def test_frozen_rows_cannot_update(self):
        self.c.execute("UPDATE design_revisions SET frozen=1 WHERE id=?",(REVISION,))
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute("UPDATE criteria SET name='changed' WHERE revision_id=?",(REVISION,))

    def test_frozen_revision_cannot_unfreeze(self):
        self.c.execute("UPDATE design_revisions SET frozen=1 WHERE id=?",(REVISION,))
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute("UPDATE design_revisions SET frozen=0 WHERE id=?",(REVISION,))

    def test_unknown_table_fails_public_export(self):
        for table, in self.c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
            insert(self.c,"visibility_policy",dict(table_name=table,visibility="public_design" if table in PUBLIC else "local_only",public_columns_json=j(PUBLIC.get(table,[])),reason="test"))
        self.c.execute("CREATE TABLE unreviewed_private_data(secret TEXT)")
        with self.assertRaises(ValueError):export_public(self.c)

    def test_public_export_has_no_operations(self):
        self.result()
        for table, in self.c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
            insert(self.c,"visibility_policy",dict(table_name=table,visibility="public_design" if table in PUBLIC else "local_only",public_columns_json=j(PUBLIC.get(table,[])),reason="test"))
        self.assertNotIn("results",export_public(self.c)["tables"])

    def test_public_export_rejects_local_path(self):
        for table, in self.c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
            insert(self.c,"visibility_policy",dict(table_name=table,visibility="public_design" if table in PUBLIC else "local_only",public_columns_json=j(PUBLIC.get(table,[])),reason="test"))
        self.c.execute("UPDATE criteria SET name='/Users/test/private'")
        with self.assertRaises(ValueError):export_public(self.c)

    def test_external_snapshot_key_is_unique(self):
        insert(self.c,"source_snapshots",dict(id="s",namespace="modeus",source_version="1",sha256="c"*64,captured_on=None,completeness="complete",provenance_json="{}"))
        data=dict(snapshot_id="s",namespace="modeus",external_kind="event",external_id="event1",internal_id="lesson",status="proposed")
        insert(self.c,"external_links",data)
        with self.assertRaises(sqlite3.IntegrityError):insert(self.c,"external_links",data)

    def test_split_keeps_teacher_together(self):
        self.c.execute("INSERT INTO split_memberships VALUES (?,?,?,?)",(REVISION,"1","teacher","calibration"))
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute("INSERT INTO split_memberships VALUES (?,?,?,?)",(REVISION,"1","teacher","test"))

    def test_snapshot_rows_immutable(self):
        insert(self.c,"source_snapshots",dict(id="s",namespace="history",source_version="1",sha256="c"*64,captured_on=None,completeness="complete",provenance_json="{}"))
        self.c.execute("INSERT INTO historical_tables VALUES ('s','test','CREATE TABLE test(x)','[\"x\"]','[]',0)")
        with self.assertRaises(sqlite3.IntegrityError):self.c.execute("UPDATE historical_tables SET rows_json='[1]'")

    def test_builder_never_overwrites_existing_database(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"existing.sqlite";path.write_bytes(b"preserve me")
            with self.assertRaises(FileExistsError):build(path,None)
            self.assertEqual(path.read_bytes(),b"preserve me")

    def import_files(self,d):
        a=SamplingTests().analysis();a["run_id"]=3;a["updated_at"]="2026-10-06T08:00:00+05:00"
        ap=Path(d)/"analysis.json";ap.write_text(j(a))
        selection=prepare(a,"2026-10-06T08:00:00+05:00","2026-10-06T09:00:00+05:00")
        selection["source_sha256"]=sha(ap)
        sp=Path(d)/"selection.json";sp.write_text(j(selection))
        return ap,sp

    def test_modeus_import_is_idempotent_and_stays_candidate(self):
        self.c.commit()
        with tempfile.TemporaryDirectory() as d:
            ap,sp=self.import_files(d)
            first=load(self.c,ap,sp);second=load(self.c,ap,sp)
            self.assertEqual((first["inserted_lessons"],second["inserted_lessons"]),(16,0))
            self.assertEqual(self.c.execute("SELECT count(*) FROM lessons WHERE state<>'candidate'").fetchone()[0],0)

    def test_modeus_tampered_selection_rejected(self):
        self.c.commit()
        with tempfile.TemporaryDirectory() as d:
            ap,sp=self.import_files(d)
            selected=json.loads(sp.read_text());selected["primary"][0]["event"]["id"]="other"
            sp.write_text(j(selected))
            with self.assertRaises(ValueError):load(self.c,ap,sp)
            self.assertEqual(self.c.execute("SELECT count(*) FROM source_snapshots").fetchone()[0],0)

class SamplingTests(unittest.TestCase):
    def analysis(self):
        candidates=[];meetings=[]
        for d in (1,2):
            teachers=[f"D{d}T1",f"D{d}T2"]
            candidates.append(dict(eligible=True,mup_id=str(d),period_id="p",type="SEMI",teacher_ids=teachers))
            for t in teachers:
                for g in (1,2):
                    for n in (1,2):
                        meetings.append(dict(id=f"{t}-{g}-{n}",mup_id=str(d),period_id="p",typeId="SEMI",teacher_ids=[t],team_id=f"{t}G{g}",start=f"2026-10-{10+n}T10:00:00+05:00",end=f"2026-10-{10+n}T11:30:00+05:00",status="PLANNED"))
        return dict(complete=True,candidates=candidates,meetings=meetings,config=dict(experiment_end="2026-12-01"))

    def test_eight_plus_reserve(self):
        r=prepare(self.analysis(),"2026-10-06T08:00:00+05:00","2026-10-06T09:00:00+05:00")
        self.assertEqual((len(r["primary"]),len(r["reserve"])),(8,8))

    def test_stale_needs_explicit_preview(self):
        with self.assertRaises(ValueError):prepare(self.analysis(),"2026-09-17T08:00:00+05:00","2026-10-06T09:00:00+05:00")

    def test_incomplete_cannot_sample(self):
        a=self.analysis();a["complete"]=False
        with self.assertRaises(ValueError):prepare(a,"2026-10-06T08:00:00+05:00","2026-10-06T09:00:00+05:00")

    def test_joint_event_not_multiple_lessons(self):
        a=self.analysis()
        for e in a["meetings"]:e["id"]=e["teacher_ids"][0]
        self.assertFalse(prepare(a,"2026-10-06T08:00:00+05:00","2026-10-06T09:00:00+05:00")["eight_available_in_snapshot"])

    def test_cancelled_event_not_selected(self):
        a=self.analysis()
        for e in a["meetings"]:e["status"]="NOT_HELD"
        self.assertFalse(prepare(a,"2026-10-06T08:00:00+05:00","2026-10-06T09:00:00+05:00")["eight_available_in_snapshot"])

if __name__=="__main__":unittest.main()
