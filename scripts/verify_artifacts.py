"""Check counts, reference integrity, font embedding, PDF text, and diagram pixels."""

import json
import re
from pathlib import Path

from PIL import Image, ImageStat
from pypdf import PdfReader

from build_artifacts import prose_statistics, read_sources

ROOT = Path(__file__).resolve().parents[1]


def main():
    source, references = read_sources()
    stats = prose_statistics(source)
    assert 2500 <= stats["total_words"] <= 3000
    assert len(references) >= 5 and len({r["doi"].lower() for r in references}) == len(references)
    assert stats["cited_reference_ids"] == [r["id"] for r in references]
    plan = json.loads((ROOT / "data/collection-plan.json").read_text(encoding="utf-8"))
    n_originals = len(plan["content_types"]) * plan["originals_per_type"]
    n_scenes = n_originals * len(plan["devices"]) * len(plan["lighting_conditions"])
    n_refs = n_originals * len(plan["devices"])
    assert (n_originals, n_scenes, n_refs) == (24, 240, 48)
    assert n_scenes + n_refs == plan["target_counted_rgb_images"] == 288
    for split, per_class in plan["split_originals_per_type"].items():
        originals = per_class * len(plan["content_types"])
        assert plan["split_scene_images"][split] == originals * 2 * 5
        assert plan["split_reference_images"][split] == originals * 2
    assert sum(plan["split_originals_per_type"].values()) == plan["originals_per_type"]
    template = json.loads((ROOT / "data/annotation-template.json").read_text(encoding="utf-8"))
    assert template["record_status"] == "template_not_an_observation"
    assert template["rights"]["public_release_approved"] is False
    assert template["scene_image_path"] is None
    reader = PdfReader(ROOT / "output/pdf/p1-review.pdf")
    text = "\n".join(page.extract_text() for page in reader.pages)
    for needle in ["摘要", "引言", "方法脉络", "对比讨论与质量评估", "视觉数据收集方案", "结论", "参考文献", "288", "LoDoPaB-CT"]:
        assert needle in text, f"Missing PDF text: {needle}"
    assert "\ufffd" not in text and "TODO" not in text
    compact_text = re.sub(r"\s+", "", text).lower()
    uri_links = set()
    for page in reader.pages:
        for annotation in page.get("/Annots", []):
            action = annotation.get_object().get("/A")
            if action:
                uri = action.get_object().get("/URI")
                if uri:
                    uri_links.add(str(uri).lower())
    for ref in references:
        assert ref["doi"].lower() in compact_text, ref["doi"]
        assert "https://doi.org/" + ref["doi"].lower() in uri_links, ref["doi"]
    for char in set(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", source.split("## 参考文献")[0])):
        assert char in text, f"Chinese character missing from PDF: {char}"
    fonts = {}
    for page in reader.pages:
        for resource in page["/Resources"].get("/Font", {}).values():
            font = resource.get_object()
            candidates = [font] + [item.get_object() for item in font.get("/DescendantFonts", [])]
            for candidate in candidates:
                descriptor = candidate.get("/FontDescriptor")
                if descriptor:
                    descriptor = descriptor.get_object()
                    fonts[str(candidate["/BaseFont"])] = any(key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3"))
    assert len(fonts) >= 2 and all(fonts.values()), fonts
    tex = (ROOT / "paper/p1-review.tex").read_text(encoding="utf-8")
    assert tex.count(r"\begin{equation}") == 3
    assert r"\frac" in tex and r"\int" in tex and r"\log_{10}" in tex
    assert "tectonic" in str(reader.metadata.producer).lower() or "xdvipdfmx" in str(reader.metadata.producer).lower()
    for symbol in ("∫", "λ"):
        assert symbol in text, f"Missing mathematical symbol: {symbol}"
    # Computer Modern maps capital delta to U+2206 in some PDF text maps.
    assert "Δ" in text or "∆" in text
    with Image.open(ROOT / "figures/collection-plan.png") as figure:
        assert figure.size == (2880, 2280), figure.size
        variance = ImageStat.Stat(figure.convert("RGB")).var
        assert min(variance) > 50, "Diagram appears blank"
    result = {"checks": "passed", "pages": len(reader.pages), "words": stats["total_words"],
              "references": len(references), "planned_scene_images": n_scenes,
              "planned_reference_images": n_refs, "embedded_fonts": fonts}
    (ROOT / "output/verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
