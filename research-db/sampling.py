"""Read-only MODEUS selection: draft 2 disciplines × 2 teachers × 2 teams.

No automatic confirmation for recording. Historical previews are explicitly stale.
"""
import argparse
import csv
import hashlib
import itertools
import json
from datetime import datetime, timedelta
from pathlib import Path

def moment(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timezone offset required")
    return result

def prepare(analysis, source_captured_at, as_of, historical_preview=False):
    now, captured = moment(as_of), moment(source_captured_at)
    stale = now - captured > timedelta(days=1)
    if analysis.get("complete") is not True:
        raise ValueError("Incomplete snapshot cannot define the sampling frame")
    if stale and not historical_preview:
        raise ValueError("MODEUS snapshot is stale; refresh or explicitly request a historical preview")
    if captured > now:
        raise ValueError("snapshot captured after selection time")
    source = analysis["meetings"]
    future = []
    for event in source:
        status=(event.get("status","")+" "+event.get("status_name","")).lower()
        if any(word in status for word in ("cancel","отмен","не состоял","not_held","deleted")):
            continue
        start, end = moment(event["start"]), moment(event["end"])
        if end <= start:
            raise ValueError("invalid event interval")
        if start < now or start.date().isoformat() > analysis["config"]["experiment_end"]:
            continue
        if len(event.get("teacher_ids",[])) != 1 or not event.get("team_id"):
            continue
        if event.get("typeId") not in ("LECT", "SEMI"):
            continue
        future.append(event)
    alternatives = []
    for candidate in analysis["candidates"]:
        if not candidate.get("eligible"):
            continue
        eligible_ids = set(candidate.get("teacher_ids",[]))
        events = [e for e in future if e["mup_id"] == candidate["mup_id"]
                  and e["period_id"] == candidate["period_id"] and e["typeId"] == candidate["type"]
                  and e["teacher_ids"][0] in eligible_ids]
        by_teacher = {}
        for event in events:
            by_teacher.setdefault(event["teacher_ids"][0],{}).setdefault(event["team_id"],[]).append(event)
        for groups in by_teacher.values():
            for values in groups.values():
                values.sort(key=lambda e:(not e.get("main_building"),e["start"],e["id"]))
        teachers = sorted(t for t, groups in by_teacher.items() if len(groups) >= 2)
        found = None
        for t1, t2 in itertools.combinations(teachers,2):
            for g1 in itertools.combinations(sorted(by_teacher[t1]),2):
                for g2 in itertools.combinations(sorted(by_teacher[t2]),2):
                    if len(set(g1+g2)) != 4:
                        continue
                    selected = [by_teacher[t][g][0] for t, gs in ((t1,g1),(t2,g2)) for g in gs]
                    if len({e["id"] for e in selected}) != 4:
                        continue  # one joint event cannot become two independent lessons
                    found = dict(candidate=candidate,events=selected,teachers=[t1,t2],groups=by_teacher)
                    break
                if found: break
            if found: break
        if found: alternatives.append(found)
    alternatives.sort(key=lambda a:(-sum(bool(e.get("main_building")) for e in a["events"]),min(e["start"] for e in a["events"]),a["candidate"]["mup_id"],a["candidate"]["type"]))
    selected = []
    for a,b in itertools.combinations(alternatives,2):
        if a["candidate"]["mup_id"] == b["candidate"]["mup_id"]:
            continue
        if set(a["teachers"]) & set(b["teachers"]):
            continue
        if len({e["id"] for e in a["events"]+b["events"]}) == 8:
            selected = [a,b]; break
    output = []
    used = set()
    for d, block in enumerate(selected,1):
        for n,event in enumerate(block["events"],1):
            used.add(event["id"])
            output.append(dict(slot=f"D{d}-P{n}",role="primary",discipline_stratum=f"D{d}",
                               proposal_status="historical_preview_requires_refresh" if stale else "candidate_requires_confirmation",
                               event=event))
    reserve = []
    for d, block in enumerate(selected,1):
        for event in block["events"]:
            values = block["groups"][event["teacher_ids"][0]][event["team_id"]]
            replacement = next((e for e in values if e["id"] not in used),None)
            if replacement:
                used.add(replacement["id"])
                reserve.append(dict(slot=f"D{d}-R{len(reserve)+1}",role="reserve",discipline_stratum=f"D{d}",
                                    replacement_for=event["id"],proposal_status="requires_confirmation",event=replacement))
    return dict(source_captured_at=source_captured_at,selection_as_of=as_of,
                source_complete=True,stale=stale,visibility="local_only",
                selection_method="deterministic_feasibility_preview_not_random_sample",
                preference="Республики 9 как техническое предпочтение, не статистический признак",
                assumptions=["два различных МУП", "один тип занятия внутри МУП", "два разных преподавателя на МУП", "две различные команды на преподавателя", "четыре преподавателя и восемь различных событий"],
                qualifying_mup_type_blocks=len(alternatives),primary=output,reserve=reserve,
                trial_policy="Две записи для пробы; статус calibration/trial зафиксировать отдельно. Изменённый на пробе кодбук запрещает считать эти же записи независимым тестом.",
                missing_requirements=["свежий снимок" if stale else "подтверждение времени/преподавателя/группы", "готовность аудитории и разрешённый сбор", "две пробные записи", "проверка темы/состава групп", "решения Q-03/Q-08/Q-09"],
                eight_available_in_snapshot=len(output)==8)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--analysis",type=Path,required=True)
    p.add_argument("--source-captured-at",required=True)
    p.add_argument("--as-of",required=True)
    p.add_argument("--historical-preview",action="store_true")
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    data=json.loads(a.analysis.read_text())
    report=prepare(data,a.source_captured_at,a.as_of,a.historical_preview)
    report["source_sha256"]=hashlib.sha256(a.analysis.read_bytes()).hexdigest()
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/"selection.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    columns=["slot","role","proposal_status","mup","mup_id","period_id","typeId","event_id","teacher_id","teacher_name","team_id","team","start","end","rooms","main_building","url"]
    with (a.output/"eight-and-reserve.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
        for item in report["primary"]+report["reserve"]:
            e=item["event"]
            row={k:e.get(k,"") for k in columns if k in e}
            row.update(slot=item["slot"],role=item["role"],proposal_status=item["proposal_status"],event_id=e["id"],
                       teacher_id=e["teacher_ids"][0],teacher_name="; ".join(e.get("teacher_names",[])),rooms="; ".join(e.get("rooms",[])))
            writer.writerow(row)
    print(json.dumps({k:report[k] for k in ("stale","qualifying_mup_type_blocks","eight_available_in_snapshot")},ensure_ascii=False))

if __name__=="__main__":main()
