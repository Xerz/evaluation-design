"""Import local candidate events from a provenance-checked selection. Never confirms recording."""
import argparse
import json
import sqlite3
import uuid
from pathlib import Path

from build import REVISION, insert, j, sha
from sampling import prepare

def entity_id(snapshot, kind, external):
    return str(uuid.uuid5(uuid.NAMESPACE_URL,f"research/{REVISION}/{snapshot}/{kind}/{external}"))

def load(con, analysis_path, selection_path, historical_preview=False):
    con.execute("PRAGMA foreign_keys=ON")
    con.row_factory=sqlite3.Row
    analysis=json.loads(Path(analysis_path).read_text())
    selection=json.loads(Path(selection_path).read_text())
    digest=sha(analysis_path)
    if selection["source_sha256"] != digest:
        raise ValueError("Selection and MODEUS snapshot hashes differ")
    recalculated=prepare(analysis,selection["source_captured_at"],selection["selection_as_of"],historical_preview)
    if any(recalculated[k] != selection[k] for k in ("primary","reserve","stale","assumptions")):
        raise ValueError("Selection changed; review and rebuild instead of trusting edited IDs")
    if not selection["eight_available_in_snapshot"]:
        raise ValueError("Eight-slot draft has not been completed")
    snapshot="MODEUS-"+digest[:24]
    exists=con.execute("SELECT id FROM source_snapshots WHERE id=?",(snapshot,)).fetchone()
    if exists:
        return dict(status="already_imported",snapshot=snapshot,inserted_lessons=0)
    with con:
        insert(con,"source_snapshots",dict(id=snapshot,namespace="modeus",source_version=f"run-{analysis['run_id']}",sha256=digest,
              captured_on=selection["source_captured_at"],completeness="complete",
              provenance_json=j(dict(selection_as_of=selection["selection_as_of"],stale=selection["stale"],
                                     external_system="utmn.modeus.org",config=analysis["config"],source_updated_at=analysis["updated_at"],
                                     scope="candidate events only; no students or credentials"))))
        insert(con,"revision_snapshots",dict(revision_id=REVISION,snapshot_id=snapshot,role="candidate_frame"))
        def entity(kind,external,external_kind):
            internal=entity_id(snapshot,kind,external)
            con.execute("INSERT OR IGNORE INTO entities VALUES (?,?,?)",(internal,REVISION,kind))
            con.execute("INSERT OR IGNORE INTO external_links VALUES (?,?,?,?,?,?)",(snapshot,"modeus",external_kind,external,internal,"proposed"))
            return internal
        all_items=selection["primary"]+selection["reserve"]
        for item in all_items:
            e=item["event"]
            teacher=entity("teacher",e["teacher_ids"][0],"teacher")
            group=entity("group",e["team_id"],"team")
            lesson=entity("lesson",e["id"],"event")
            insert(con,"lessons",dict(id=lesson,revision_id=REVISION,discipline_id=e["mup_id"],teacher_entity_id=teacher,group_entity_id=group,
                  starts_at=e["start"],timezone="Asia/Yekaterinburg",lesson_type=e["typeId"],slot_role=item["role"],state="candidate",profile_code="TP-AUDIO",
                  metadata_json=j(dict(external_event=e,slot=item["slot"],discipline_stratum=item["discipline_stratum"],
                                       source_snapshot=snapshot,stale=selection["stale"],proposal_status=item["proposal_status"],
                                       replacement_for=item.get("replacement_for"),recording_confirmed=False))))
        if con.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("MODEUS import FK check failed")
    return dict(status="historical_preview_imported" if selection["stale"] else "candidates_imported",snapshot=snapshot,inserted_lessons=len(all_items),recording_confirmed=False)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--database",type=Path,required=True)
    p.add_argument("--analysis",type=Path,required=True)
    p.add_argument("--selection",type=Path,required=True)
    p.add_argument("--historical-preview",action="store_true")
    a=p.parse_args()
    if not a.database.is_file():raise ValueError("Database must already exist")
    with sqlite3.connect(a.database) as con:
        print(json.dumps(load(con,a.analysis,a.selection,a.historical_preview),ensure_ascii=False))
