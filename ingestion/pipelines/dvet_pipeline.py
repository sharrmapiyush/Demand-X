import json
import hashlib
from datetime import datetime
from sqlalchemy.orm import Session
from core.models.source import Source
from core.models.dvet import DVETInstitute, DVETTrade


def register_dvet_source(db: Session) -> Source:
    source = db.query(Source).filter(Source.source_id == "dvet-pune-haveli-verified-snapshot").first()
    if not source:
        source = Source(
            source_id="dvet-pune-haveli-verified-snapshot",
            source_name="Directorate of Vocational Education and Training (DVET) Pune Region - Industrial Training Institute Haveli Verified Snapshot",
            organization="Directorate of Vocational Education and Training (DVET) Maharashtra",
            url="https://pune.dvet.gov.in/pune-institutes/",
            category="supply",
            access_method="PUBLIC_PAGE",
            freshness_class="PERIODIC",
            coverage="Pune District, Maharashtra (ITI Haveli)",
            reliability_notes="Strictly verified snapshot containing only ITI Haveli detail page values observed on official public portal.",
            enabled=True
        )
        db.add(source)
        db.commit()
        db.refresh(source)
    return source


def ingest_dvet_snapshot(db: Session, snapshot_path: str = "data/raw/dvet_pune/dvet_pune_haveli_verified_snapshot.json"):
    register_dvet_source(db)

    with open(snapshot_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    institutes_data = data.get("institutes", [])
    institutes_processed = 0
    trades_processed = 0
    errors = 0

    for inst in institutes_data:
        try:
            institute_name = inst["institute_name"]
            institute_code = inst.get("institute_code", institute_name)
            district = inst.get("district", "Pune")
            state = inst.get("state", "Maharashtra")

            if district != "Pune":
                errors += 1
                continue

            # Compute deterministic record identity hash for institute
            inst_identity_string = f"{institute_code}:{institute_name}:{district}"
            inst_hash = hashlib.sha256(inst_identity_string.encode("utf-8")).hexdigest()

            # Upsert Institute
            existing_inst = db.query(DVETInstitute).filter(DVETInstitute.record_identity_hash == inst_hash).first()
            if not existing_inst:
                dvet_inst = DVETInstitute(
                    institute_id=inst_hash[:32],
                    institute_code=institute_code,
                    ncvt_mis_code=inst.get("ncvt_mis_code"),
                    institute_name=institute_name,
                    institute_category=inst.get("institute_category"),
                    district=district,
                    state=state,
                    address=inst.get("address"),
                    establishment_year=inst.get("establishment_year"),
                    establishment_gr=inst.get("establishment_gr"),
                    hostel_capacity=inst.get("hostel_capacity"),
                    source_id="dvet-pune-haveli-verified-snapshot",
                    raw_json=inst,
                    record_identity_hash=inst_hash
                )
                db.add(dvet_inst)
                institutes_processed += 1

            # Process Trades
            trades = inst.get("trades", [])
            for idx, trade in enumerate(trades):
                trade_name = trade["trade_name"]
                unit_category = trade.get("unit_category", "")
                intake = trade.get("intake", "")
                trade_identity_string = f"{institute_code}:{trade_name}:{unit_category}:{intake}:{idx}"
                trade_hash = hashlib.sha256(trade_identity_string.encode("utf-8")).hexdigest()

                existing_trade = db.query(DVETTrade).filter(DVETTrade.trade_identity_hash == trade_hash).first()
                if not existing_trade:
                    dvet_trade = DVETTrade(
                        trade_id=trade_hash[:32],
                        institute_code=institute_code,
                        institute_name=institute_name,
                        trade_name=trade_name,
                        unit_category=trade.get("unit_category"),
                        intake=str(trade.get("intake")),
                        district=district,
                        state=state,
                        source_id="dvet-pune-haveli-verified-snapshot",
                        raw_json=trade,
                        trade_identity_hash=trade_hash
                    )
                    db.add(dvet_trade)
                    trades_processed += 1

            db.commit()
        except Exception as e:
            db.rollback()
            errors += 1
            print(f"Error processing institute {inst.get('institute_name')}: {e}")

    return {
        "status": "success" if errors == 0 else "completed_with_errors",
        "institutes_processed": institutes_processed,
        "trades_processed": trades_processed,
        "errors": errors,
        "source_id": "dvet-pune-haveli-verified-snapshot"
    }
