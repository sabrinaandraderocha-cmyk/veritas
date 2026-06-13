from __future__ import annotations

from io import BytesIO
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak


def _pdf_bytes(title: str, subtitle: str, sections: list[tuple[str, list[str]]]) -> bytes:
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=1.8*cm, leftMargin=1.8*cm, topMargin=1.6*cm, bottomMargin=1.6*cm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8.5, leading=11))
    story = [Paragraph(title, styles["Title"]), Paragraph(subtitle, styles["Heading2"]), Spacer(1, 10)]
    for heading, paragraphs in sections:
        story.append(Paragraph(heading, styles["Heading2"]))
        for text in paragraphs:
            story.append(Paragraph(str(text).replace("\n", "<br/>"), styles["Small"]))
            story.append(Spacer(1, 6))
    doc.build(story)
    return output.getvalue()


def generate_local_report(name, similarity, matches, coverage, disclaimer) -> bytes:
    match_lines = []
    for i, m in enumerate(matches, 1):
        match_lines.append(
            f"<b>{i}. Fonte:</b> {m.source_doc}<br/>"
            f"<b>Correspondência:</b> {m.score*100:.1f}%<br/>"
            f"<b>Trecho analisado:</b> {m.query_chunk}<br/>"
            f"<b>Trecho da fonte:</b> {m.source_chunk}"
        )
    return _pdf_bytes(
        "Relatório Veritas — Comparação local",
        name,
        [
            ("Resumo", [f"Similaridade aproximada com a biblioteca: {similarity*100:.1f}%", coverage]),
            ("Correspondências", match_lines or ["Nenhuma correspondência acima do limiar selecionado."]),
            ("Limitações", [disclaimer]),
        ],
    )


def generate_web_report(name, hits, coverage, disclaimer) -> bytes:
    lines = []
    for i, h in enumerate(hits, 1):
        lines.append(
            f"<b>{i}. {h.title}</b><br/>URL: {h.link}<br/>"
            f"Proximidade com o snippet: {h.score*100:.1f}%<br/>Snippet: {h.snippet}"
        )
    return _pdf_bytes(
        "Relatório Veritas — Busca web",
        name,
        [("Cobertura", [coverage]), ("Resultados", lines or ["Nenhum resultado localizado."]), ("Limitações", [disclaimer])],
    )


def generate_linguistic_report(name, result, disclaimer) -> bytes:
    metrics = [f"{label}: {value}" for label, value in result["display_metrics"].items()]
    return _pdf_bytes(
        "Relatório Veritas — Padrões linguísticos",
        name,
        [
            ("Síntese", [result["summary"]]),
            ("Indicadores", metrics),
            ("Observações", result["observations"] or ["Nenhuma observação relevante para os indicadores avaliados."]),
            ("Limitações", [disclaimer]),
        ],
    )
