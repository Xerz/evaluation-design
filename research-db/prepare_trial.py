"""Prepare empty trial forms and explicit storage/workload scenarios, without observations."""
import argparse
import csv
import json
from pathlib import Path

from config import DAY, profiles

def csv_file(path,columns,records):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(records)

def prepare(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/"technical-profiles.json").write_text(json.dumps(profiles(),ensure_ascii=False,indent=2)+"\n")
    csv_file(output/"recording-qc.csv",["trial_slot","profile","check","result","usable_start_ms","usable_end_ms","lost_seconds","notes"],
       [dict(trial_slot=f"TRIAL-{i}",profile=p["code"],check=c,result="",usable_start_ms="",usable_end_ms="",lost_seconds="",notes="")
        for i in (1,2) for p in profiles()[:4] for c in p["checks"]])
    csv_file(output/"annotation-time.csv",["trial_slot","expert_id","condition","activity","elapsed_seconds","notes"],
       [dict(trial_slot=f"TRIAL-{i}",expert_id="",condition="REF-REC",activity=a,elapsed_seconds="",notes="")
        for i in (1,2) for a in ("обучение/кодбук","просмотр/чтение","оценка 26 критериев","проверка цитат/локаторов","обсуждение расхождений","внесение/исправления","событийная разметка отдельно")])
    csv_file(output/"trial-criterion-form.csv",["trial_slot","expert_id","criterion_code","status","score","evidence_artifact_id","locator_kind","start","end","quote","reason","elapsed_seconds"],
       [dict(trial_slot=f"TRIAL-{i}",expert_id="",criterion_code=f"C{n:02}",status="",score="",evidence_artifact_id="",locator_kind="",start="",end="",quote="",reason="",elapsed_seconds="")
        for i in (1,2) for n in range(1,27)])
    csv_file(output/"eight-slot-confirmation.csv",["slot","discipline_stratum","teacher_stratum","group_stratum","modeus_event_id","starts_at","room","audio_ready","expert_video_ready","mgpu_video_ready","context_ready","recording_confirmed","notes"],
       [dict(slot=f"D{d}-T{t}-G{g}",discipline_stratum=f"D{d}",teacher_stratum=f"D{d}-T{t}",group_stratum=f"D{d}-T{t}-G{g}",modeus_event_id="",starts_at="",room="",audio_ready="",expert_video_ready="",mgpu_video_ready="",context_ready="",recording_confirmed="",notes="")
        for d in (1,2) for t in (1,2) for g in (1,2)])
    minutes=90
    storage=dict(example_duration_minutes=minutes,measured=False,
                 pcm_48kHz_16bit_mono_decimal_MB=48000*16/8*minutes*60/1_000_000,
                 pcm_48kHz_16bit_stereo_decimal_MB=48000*16/8*minutes*60*2/1_000_000,
                 video_1Mbps_decimal_MB=1_000_000/8*minutes*60/1_000_000,
                 total_bitrate_for_512_decimal_MB_Mbps=512*1_000_000*8/(minutes*60)/1_000_000,
                 note="Расчёт объёма, не рекомендация битрейта. 512 MB — исторический неподтверждённый лимит; если сервис подразумевает MiB, расчёт другой. 48 kHz/16 bit — инженерный пример, не утверждённое требование и не повод повышать частоту исходника.")
    (output/"storage-scenarios.json").write_text(json.dumps(storage,ensure_ascii=False,indent=2)+"\n")
    scenarios=[]
    for assessments in (8,12,16):
        scenarios.append(dict(assessments=assessments,criterion_fields=assessments*26,
                              labor_hours=None,formula="assessments × measured_minutes_per_assessment / 60 + training + adjudication + evidence/event work + import/QC",
                              independent_observations=8,notes="Поля и дополнительные оценки не увеличивают число независимых занятий; кластерная зависимость сохраняется."))
    (output/"annotation-scenarios.json").write_text(json.dumps(scenarios,ensure_ascii=False,indent=2)+"\n")
    text=f"""# Проба двух записей и техническая подготовка

Дата: {DAY}. Файлы являются пустыми рабочими формами; измерения и оценки не подставлены.

1. Подтвердить события/аудитории после свежего MODEUS. Проверить звук преподавателя и студентов, начало/конец, шум и пригодные участки в `recording-qc.csv`.
2. Сохранить исходники с SHA-256; транскрипт и перекодирование — отдельные версии. TXT получает символьные координаты; таймкоды только из реальной синхронизации.
3. Эксперт обучается рубрике и заполняет `trial-criterion-form.csv`. Статусы: scored/insufficient_data/not_applicable/error/invalid_output. 0 — только содержательная оценка, не пропуск. REF-REC не получает выводы ИИ.
4. Измерить этапы в `annotation-time.csv`, отдельно просмотр, критерии, доказательства, событийная разметка, обсуждение и внесение. Две записи не дают устойчивую оценку вариативности затрат; показывать оба измерения и диапазон.
5. Выбрать сценарий 8/12/16 оценок по измеренным минутам и бюджетам; подготовка, расхождения, данные студентов и EXP-AI учитываются отдельно.

Роли/согласие экспертов, очное наблюдение, прямые данные C24/C25 и численные QC-пороги остаются открытыми. C26 требует принципов и повторных наблюдений. Пробные записи относятся к калибровке, если по ним меняется кодбук; их нельзя затем выдать за независимый тест.

Минимум — пригодное аудио и полный транскрипт. Видео для эксперта и видеовход МГПУ имеют разные профили. Собственные OA/OV остаются кандидатами. Старый MP4/H.264/720p/90 min/512 MB сохраняется как неподтверждённое ограничение прежней платформы.

Облако: сначала определить действующую модель/ASR, размещение данных, ресурсы, версии, стоимость и поддержку. Self-host с поддержкой: разделить локальные запись/хранилище/БД и обработчики; отсутствие действующей локальной модели и подтверждённых модулей МГПУ пока не позволяет обещать полностью автономную поставку. Состав поддержки: установка, обновления, мониторинг, резервное восстановление, контроль качества и совместимости версий; SLA/стоимость ещё обсуждаются.

`storage-scenarios.json` содержит только арифметические примеры объёма. Цены, скорости обработки и нормы трудозатрат пока не измерены.
"""
    (output/"README.md").write_text(text)
    return dict(status="empty_forms_prepared",real_recordings=0,trial_slots=2,assessments=[8,12,16])

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",type=Path,required=True)
    print(json.dumps(prepare(p.parse_args().output),ensure_ascii=False))
