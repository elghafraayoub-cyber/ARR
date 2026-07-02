from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_COLOR = {
    "SOIL_PHYSICAL_PROPERTY": "#4C9AFF", "SOIL_CHEMICAL_PROPERTY": "#00B8D9",
    "BIOLOGICAL_AGENT": "#36B37E", "SOIL_PROCESS": "#00875A",
    "MANAGEMENT_PRACTICE": "#FF8B00", "CROP_SPECIES": "#6554C0",
    "PLANT_RESPONSE": "#DE350B", "ENVIRONMENTAL_FACTOR": "#8993A4",
    "ECOSYSTEM_SERVICE": "#00A3BF", "QUANTITATIVE_OUTCOME": "#FFC400",
    "EXPERIMENTAL_CONTEXT": "#42526E", "OTHER": "#A5ADBA",
}


def build_html(kg_path: str | Path, out_path: str | Path) -> None:
    from pyvis.network import Network

    data = json.loads(Path(kg_path).read_text(encoding="utf-8"))
    entities = data.get("entities", {})
    findings = data.get("findings", {})

    net = Network(height="850px", width="100%", directed=True, notebook=False, bgcolor="#111318", font_color="#eee")
    net.barnes_hut()

    for eid, e in entities.items():
        net.add_node(
            eid, label=e.get("name", eid)[:40],
            title=f"{e.get('entity_type')}: {e.get('description', '')}",
            color=_COLOR.get(e.get("entity_type"), "#A5ADBA"), shape="dot", size=14,
        )

    for fid, f in findings.items():
        src, tgt = f.get("source_id"), f.get("target_id")
        if src not in entities or tgt not in entities:
            continue
        cond_txt = "; ".join(c.get("condition_text", "") for c in f.get("conditions", []))
        title = (
            f"{f.get('relation_type')}"
            f"{'  ' + f['effect_magnitude'] if f.get('effect_magnitude') else ''}"
            f"{'  (p=' + f['p_value'] + ')' if f.get('p_value') else ''}\n"
            f"conditions: {cond_txt or '(none)'}\n"
            f"quote: {f.get('evidence_quote', '')[:200]}"
        )
        net.add_edge(src, tgt, title=title, label=f.get("relation_type", ""), arrows="to")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    net.write_html(str(out_path), notebook=False)
    log.info("Visualization saved -> %s", out_path)
