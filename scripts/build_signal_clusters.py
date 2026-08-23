"""Thin loader/writer for closed-registry signal clusters."""
from psx_data import STATE, load_json, save_json
from signal_clusters import build_signal_state

OUT = STATE / "company_intel" / "signal_clusters.json"


def build():
    profiles = load_json(STATE / "company_profiles.json", {})
    pilot = (profiles.get("pilot") or {}).get("symbols") or []
    operating_events = load_json(STATE / "company_intel" / "operating_events.json", {"companies": {}})
    documents = load_json(STATE / "company_documents.json", {"documents": {}}).get("documents") or {}
    # Only retain evidence that exactly matches a ready durable document.
    for sym, row in (operating_events.get("companies") or {}).items():
        kept=[]
        for event in row.get("events") or []:
            valid=[]
            for evidence in event.get("evidence") or []:
                doc=documents.get(evidence.get("document_id")) or {}
                if doc.get("status") != "ready" or doc.get("content_sha256") != evidence.get("content_sha256"): continue
                if not isinstance(evidence.get("content_sha256"),str) or len(evidence.get("content_sha256"))!=64: continue
                if not isinstance(evidence.get("page"),int) or not evidence.get("text"): continue
                valid.append(evidence)
            if valid:
                event=dict(event); event["evidence"]=valid
                doc=documents.get(valid[0].get("document_id")) or {}
                event["document_title"]=doc.get("title")
                kept.append(event)
        row["events"]=kept
    result = build_signal_state(operating_events, list(pilot), document_index=documents)
    save_json(OUT, result)
    total = sum(len(row.get("clusters") or []) for row in result["companies"].values())
    print(f"signal_clusters: {len(result['companies'])} companies, {total} clusters")
    return result


if __name__ == "__main__":
    build()
