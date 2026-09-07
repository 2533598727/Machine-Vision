"""Build the P1 review, bibliography, and diagram from local sources."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET

from markdown_it import MarkdownIt
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "output/pdf/p1-review.pdf"
FIGURE_PATH = ROOT / "figures/collection-plan.png"


def read_sources():
    source = (ROOT / "paper/review.md").read_text(encoding="utf-8")
    references = json.loads((ROOT / "paper/references.json").read_text(encoding="utf-8"))
    return source, references


def prose_statistics(source):
    """Count Han characters plus Latin words/numbers, not Markdown syntax."""
    body = source.split("## 参考文献", 1)[0]
    tokens = MarkdownIt().parse(body)
    paragraphs = []
    for i, token in enumerate(tokens):
        if token.type != "inline" or tokens[i - 1].type != "paragraph_open":
            continue
        if token.content.startswith(("关键词：", "$$")):
            continue
        paragraphs.append(re.sub(r"\[\d+\]", "", token.content))
    prose = re.sub(r"\$[^$]+\$", "", "\n".join(paragraphs))
    han = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", prose))
    latin = len(re.findall(r"[A-Za-z0-9]+(?:[.\-][A-Za-z0-9]+)*", prose))
    cited = sorted({int(value) for value in re.findall(r"\[(\d+)\]", body)})
    return {
        "scope": "Abstract and section prose, including the collection plan; excludes title, headings, keywords, inline/display mathematics, citation numbers, figure text, and bibliography.",
        "counting_rule": "Each Han character counts as one; each Latin word or numeric token counts as one; punctuation and whitespace are excluded.",
        "han_characters": han,
        "latin_and_numeric_tokens": latin,
        "total_words": han + latin,
        "required_min": 2500,
        "required_max": 3000,
        "cited_reference_ids": cited,
    }


def render_diagram(channel):
    with sync_playwright() as playwright:
        kwargs = {"channel": channel} if channel else {}
        browser = playwright.chromium.launch(**kwargs)
        page = browser.new_page(viewport={"width": 960, "height": 760}, device_scale_factor=3)
        page.goto((ROOT / "figures/collection-plan.html").as_uri(), wait_until="load")
        page.evaluate("document.fonts.ready")
        # Test all text against its node and the SVG before freezing pixels.
        geometry = page.evaluate("""() => {
          const svg = document.querySelector('svg');
          const issues = [];
          const inside = (a, b) => a.x >= b.x - 0.5 && a.y >= b.y - 0.5 &&
            a.x + a.width <= b.x + b.width + 0.5 &&
            a.y + a.height <= b.y + b.height + 0.5;
          for (const t of svg.querySelectorAll('text')) {
            const b = t.getBBox();
            if (!inside(b, svg.viewBox.baseVal)) issues.push('canvas: ' + t.textContent);
            const node = t.closest('[data-node]');
            if (node && !inside(b, node.querySelector('rect,polygon').getBBox()))
              issues.push('node: ' + t.textContent);
          }
          return {issues, text_count: svg.querySelectorAll('text').length,
            node_count: svg.querySelectorAll('[data-node]').length,
            css_font: getComputedStyle(svg.querySelector('.name')).fontFamily,
            local_cjk_available: document.fonts.check('16px "Microsoft YaHei"')};
        }""")
        if geometry["issues"]:
            raise ValueError(f"Diagram geometry failed: {geometry['issues']}")
        page.locator("svg").screenshot(path=str(FIGURE_PATH), omit_background=True)
        svg_text = page.locator("svg").evaluate("element => element.outerHTML")
        css = page.locator("head style").inner_text()
        svg = ET.fromstring(svg_text)
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        defs = svg.find("{http://www.w3.org/2000/svg}defs")
        ET.SubElement(defs, "{http://www.w3.org/2000/svg}style").text = css
        ET.ElementTree(svg).write(ROOT / "figures/collection-plan.svg", encoding="utf-8", xml_declaration=True)
        page.set_viewport_size({"width": 390, "height": 844})
        mobile = page.evaluate("({width: innerWidth, scroll: document.documentElement.scrollWidth})")
        if mobile["scroll"] > mobile["width"]:
            raise ValueError("Diagram overflows mobile viewport")
        browser.close()
    return geometry


def reference_text(ref):
    kind = "J" if ref["type"] == "article" else "C"
    volume = f", {ref['volume']}({ref['issue']})" if "volume" in ref else ""
    return (f"[{ref['id']}] {ref['authors']}. {ref['title']}[{kind}]. "
            f"{ref['venue']}, {ref['year']}{volume}: {ref['pages']}. "
            f"DOI: {ref['doi']}.")


def bibliography_exports(source, references):
    bib = []
    for ref in references:
        field = "journal" if ref["type"] == "article" else "booktitle"
        fields = {
            "author": " and ".join(
                family + ", " + initials
                for family, initials in (name.split(" ", 1) for name in ref["authors"].split(", "))
            ),
            "title": "{" + ref["title"] + "}",
            field: ref["venue"],
            "year": str(ref["year"]),
            "pages": ref["pages"].replace("-", "--"),
            "doi": ref["doi"],
            "url": ref["url"],
        }
        if "volume" in ref:
            fields.update(volume=ref["volume"], number=ref["issue"])
        entries = [f"  {key} = {{{value}}}" for key, value in fields.items()]
        bib.append("@" + ref["type"] + "{" + ref["key"] + ",\n" + ",\n".join(entries) + "\n}")
    (ROOT / "paper/references.bib").write_text("\n\n".join(bib) + "\n", encoding="utf-8")
    full_markdown = source.split("## 参考文献", 1)[0]
    full_markdown += "## 参考文献\n\n"
    full_markdown += "\n\n".join(reference_text(ref) + f" [来源]({ref['url']})" for ref in references)
    full_markdown += "\n\n## 图1 视觉数据收集方案\n\n![视觉数据收集方案](../figures/collection-plan.png)\n"
    (ROOT / "output/review.md").write_text(full_markdown, encoding="utf-8")


def escape_latex(text):
    replacements = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
                    "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
                    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(replacements.get(char, char) for char in text)


def latex_inline(text, reference_keys):
    fragments = []
    for part in re.split(r"(\$[^$]+\$|\[\d+\])", text):
        if part.startswith("$") and part.endswith("$"):
            fragments.append(part)
        elif re.fullmatch(r"\[\d+\]", part):
            key = reference_keys[int(part[1:-1])]
            fragments.append(r"\textsuperscript{\cite{" + key + "}}")
        else:
            fragments.append(escape_latex(part).replace("图1", r"图~\ref{fig:collection}"))
    return "".join(fragments)


def build_pdf(source, references, engine_override):
    tex_path = ROOT / "paper/p1-review.tex"
    reference_keys = {ref["id"]: ref["key"] for ref in references}
    preamble = (ROOT / "paper/latex-preamble.tex").read_text(encoding="utf-8")
    document = [preamble, r"\begin{document}", r"\begin{center}",
                r"{\zihao{2}\bfseries 文档图像偏色与光照不均\par}",
                r"\vspace{0.3em}{\zihao{3}成因、建模与校正\par}",
                r"\vspace{0.6em}{\small\color{muted}Machine Vision / P1 技术综述与视觉数据收集方案\par}",
                r"\end{center}"]
    equation_count = 0
    tokens = MarkdownIt().parse(source.split("## 参考文献", 1)[0])
    for i, token in enumerate(tokens):
        if token.type != "inline":
            continue
        preceding = tokens[i - 1]
        if preceding.type == "heading_open":
            if preceding.tag == "h1":
                continue
            title = re.sub(r"^\d+(?:\.\d+)*\s+", "", token.content)
            command = "subsection" if preceding.tag == "h3" else "section"
            if title == "摘要":
                command += "*"
            document.append("\\" + command + "{" + escape_latex(title) + "}")
        elif preceding.type == "paragraph_open":
            if token.content.startswith("$$"):
                assert token.content.endswith("$$"), "Unclosed display equation"
                equation_count += 1
                document.append(r"\begin{equation}" + "\n" + token.content[2:-2].strip() +
                                "\n" + r"\label{eq:" + str(equation_count) + "}" + "\n" + r"\end{equation}")
            else:
                document.append(latex_inline(token.content, reference_keys) + "\n")
    document += [r"\clearpage", r"\begingroup\small\linespread{1.14}\selectfont", r"\begin{thebibliography}{99}"]
    for ref in references:
        text = re.sub(r"^\[\d+\]\s*", "", reference_text(ref)).split(" DOI: ", 1)[0]
        document.append(r"\bibitem{" + ref["key"] + "}" + escape_latex(text) + "\n" +
                        r"DOI: \href{https://doi.org/" + ref["doi"] + "}{" + escape_latex(ref["doi"]) + "}.")
    document += [r"\end{thebibliography}", r"\endgroup", r"\clearpage", r"\begin{figure}[H]",
                 r"\centering\includegraphics[width=\textwidth]{collection-plan.png}",
                 r"\caption{视觉数据收集方案}\label{fig:collection}", r"\end{figure}",
                 r"{\small\color{muted}本图为计划设计，尚未采集数据或开展性能实验。240张场景图与48张参考图采用同一原稿分组；灰板伴拍与RAW副本不计入规模。详细阈值及质检流程见第5节。}",
                 r"\end{document}"]
    tex_path.write_text("\n\n".join(document) + "\n", encoding="utf-8")
    portable = ROOT / "tmp/tooling/tectonic-0.17.0/tectonic.exe"
    engine = engine_override or os.environ.get("P1_TEX_ENGINE") or shutil.which("xelatex") or shutil.which("tectonic")
    if not engine and portable.is_file():
        engine = str(portable)
    if not engine:
        raise FileNotFoundError("Install XeLaTeX or Tectonic, or pass --tex-engine PATH. LaTeX source was generated.")
    work = ROOT / "tmp/tex"
    work.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    if os.name == "nt" and not environment.get("FONTCONFIG_FILE"):
        # Portable Tectonic has no installed Fontconfig; keep its cache project-local.
        font_cache = work / "fontconfig-cache"
        font_cache.mkdir(exist_ok=True)
        config = ET.Element("fontconfig")
        ET.SubElement(config, "dir").text = "C:/Windows/Fonts"
        ET.SubElement(config, "cachedir").text = font_cache.as_posix()
        config_path = work / "fonts.conf"
        ET.ElementTree(config).write(config_path, encoding="utf-8", xml_declaration=True)
        environment["FONTCONFIG_FILE"] = config_path.as_posix()
    if Path(engine).stem.lower() == "xelatex":
        command = [engine, "-interaction=nonstopmode", "-halt-on-error", "-output-directory", str(work), tex_path.name]
        passes = 2
    else:
        command = [engine, "--keep-logs", "--outdir", str(work), tex_path.name]
        passes = 1
    for _ in range(passes):
        subprocess.run(command, cwd=tex_path.parent, check=True, timeout=900, env=environment)
    log = (work / "p1-review.log").read_text(encoding="utf-8", errors="replace")
    if "Missing character:" in log:
        raise ValueError("LaTeX reported missing glyphs; inspect tmp/tex/p1-review.log")
    shutil.copyfile(work / "p1-review.pdf", PDF_PATH)
    version = subprocess.run([engine, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout.splitlines()[0]
    return {"engine": version, "display_equations": equation_count, "source": "paper/p1-review.tex"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser-channel", default=None, help="Use msedge or chrome when bundled Chromium is unavailable.")
    parser.add_argument("--skip-diagram", action="store_true", help="Reuse an already generated PNG.")
    parser.add_argument("--tex-engine", default=None, help="Path to xelatex or tectonic; also reads P1_TEX_ENGINE.")
    args = parser.parse_args()
    (ROOT / "output/pdf").mkdir(parents=True, exist_ok=True)
    source, references = read_sources()
    stats = prose_statistics(source)
    assert 2500 <= stats["total_words"] <= 3000, stats
    assert stats["cited_reference_ids"] == [ref["id"] for ref in references]
    geometry = None if args.skip_diagram else render_diagram(args.browser_channel)
    assert FIGURE_PATH.is_file(), "Generate the diagram before building the PDF."
    bibliography_exports(source, references)
    latex = build_pdf(source, references, args.tex_engine)
    audit = {"word_count": stats, "references": len(references), "data_status": "planned_not_collected", "diagram": geometry, "latex": latex}
    (ROOT / "output/build-audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, ensure_ascii=False))
    print(f"PDF: {PDF_PATH}")


if __name__ == "__main__":
    main()
