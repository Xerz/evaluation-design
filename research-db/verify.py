"""Verify a real built DB, complete historical rows, privacy and SQL roundtrip."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from build import REVISION, EXPECTED, PUBLIC, export_public, j, open_source, rows, sha

def logical_digest(con):
    contents={}
    for name, in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        contents[name]=sorted(j(r) for r in rows(con,name))
    return hashlib.sha256(j(contents).encode()).hexdigest()

def verify(database,mgpu_path):
    c=sqlite3.connect(Path(database).resolve().as_uri()+"?mode=ro",uri=True);c.row_factory=sqlite3.Row
    result={}
    try:
        assert c.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
        assert not c.execute("PRAGMA foreign_key_check").fetchall()
        for namespace,source_path in (("wide",Path(__file__).resolve().parent.parent/"outputs/01a05c37-c522-7563-8846-1ea43a7a49d5/База пилота автоматизации критериев ТюмГУ.sqlite"),("mgpu",mgpu_path)):
            source=open_source(source_path,namespace)
            try:
                snapshot=c.execute("SELECT id FROM source_snapshots WHERE namespace='historical_design' AND source_version=?",(namespace,)).fetchone()[0]
                tables=[r for r in c.execute("SELECT * FROM historical_tables WHERE snapshot_id=?",(snapshot,))]
                names={r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
                assert {r["name"] for r in tables}==names
                for r in tables:
                    original=rows(source,r["name"])
                    assert json.loads(r["rows_json"])==original
                    assert r["row_count"]==len(original)
                result[namespace+"_historical_tables"]=len(tables)
            finally:source.close()
        result["criteria"]=c.execute("SELECT count(*) FROM criteria WHERE revision_id=?",(REVISION,)).fetchone()[0]
        assert result["criteria"]==26
        assert c.execute("SELECT count(*) FROM score_levels WHERE revision_id=?",(REVISION,)).fetchone()[0]==78
        assert {r[0] for r in c.execute("SELECT code FROM protocols WHERE revision_id=?",(REVISION,))}=={f"T{i}" for i in range(1,10)}
        assert {r[0] for r in c.execute("SELECT code FROM effects WHERE revision_id=?",(REVISION,))}=={f"E{i}" for i in range(1,10)}
        assert c.execute("SELECT count(*) FROM criterion_mappings WHERE revision_id=?",(REVISION,)).fetchone()[0]==36
        assert c.execute("SELECT count(*) FROM criterion_mappings WHERE status='validated'").fetchone()[0]==0
        assert c.execute("SELECT count(*) FROM scientific_links WHERE revision_id=?",(REVISION,)).fetchone()[0]==137
        assert c.execute("SELECT count(*) FROM metric_definitions").fetchone()[0]==41
        # Check full method text, not just codes/counts.
        for old,new in zip(c.execute("SELECT code,description,metrics,procedure FROM protocols WHERE revision_id='wide-original' ORDER BY code"),c.execute("SELECT code,description,metrics,procedure FROM protocols WHERE revision_id=? ORDER BY code",(REVISION,))):
            assert tuple(old)==tuple(new)
        for table in ("artifacts","assignments","runs","results","evidence","metric_values","time_logs","student_observations"):
            assert c.execute(f"SELECT count(*) FROM {table}").fetchone()[0]==0
        public=export_public(c)
        assert not (set(public["tables"]) & {"entities","lessons","external_links","artifacts","runs","results","source_snapshots","historical_tables"})
        dump="\n".join(c.iterdump())+"\n"
        restored=sqlite3.connect(":memory:");restored.row_factory=sqlite3.Row
        try:
            restored.executescript(dump)
            restored.execute("PRAGMA foreign_keys=ON")
            assert not restored.execute("PRAGMA foreign_key_check").fetchall()
            assert restored.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
            assert logical_digest(c)==logical_digest(restored)
            assert export_public(restored)==public
        finally:restored.close()
        output=Path(database).parent
        Path(database).with_suffix(".sql").write_text(dump)
        Path(database).with_suffix(".public.json").write_text(json.dumps(public,ensure_ascii=False,indent=2)+"\n")
        dictionary=["# Словарь черновой исследовательской БД", "", "БД и полный SQL — локальные артефакты. Для публикации используется отдельный экспорт с явным разрешением таблиц и столбцов.", ""]
        for name, in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            p=c.execute("SELECT visibility FROM visibility_policy WHERE table_name=?",(name,)).fetchone()
            dictionary += [f"## {name}","",f"Видимость: `{p[0]}`.","","| Поле | Тип | Обязательно | Ключ |","| --- | --- | --- | --- |"]
            for field in c.execute(f'PRAGMA table_info("{name}")'):
                dictionary.append(f"| {field[1]} | {field[2]} | {bool(field[3])} | {field[5] or '—'} |")
            dictionary += [""]
        (output/"data-dictionary.md").write_text("\n".join(dictionary))
        result.update(status="passed",database_sha256=sha(database),sql_roundtrip="identical_logical_rows",public_export="design_only",historical_source_databases="unchanged",
                      operational_candidate_lessons=c.execute("SELECT count(*) FROM lessons").fetchone()[0],real_model_calls=0,real_recordings=0,
                      schema_tables=c.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0])
        (output/"verification.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
        return result
    finally:c.close()

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--database",type=Path,required=True);p.add_argument("--mgpu-db",type=Path,required=True)
    a=p.parse_args();print(json.dumps(verify(a.database,a.mgpu_db),ensure_ascii=False))
