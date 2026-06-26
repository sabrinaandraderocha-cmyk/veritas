from __future__ import annotations

from io import BytesIO
import html
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer


def _safe(value: Any) -> str:
    """
    Escapa textos para evitar erro no PDF quando o conteúdo tiver caracteres
    como <, >, &, etc.
    """
    return html.escape(str(value or ""))


def _pdf_bytes(title: str, subtitle: str, sections: list[tuple[str, list[str]]]) -> bytes:
    output = BytesIO()

    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
    )

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="Small",
            parent=styles["BodyText"],
            fontSize=8.5,
            leading=11,
        )
    )

    styles.add(
        ParagraphStyle(
            name="TinyNote",
            parent=styles["BodyText"],
            fontSize=7.5,
            leading=9.5,
            textColor="#555555",
        )
    )

    story = [
        Paragraph(_safe(title), styles["Title"]),
        Paragraph(_safe(subtitle), styles["Heading2"]),
        Spacer(1, 10),
    ]

    for heading, paragraphs in sections:
        story.append(Paragraph(_safe(heading), styles["Heading2"]))

        for text in paragraphs:
            story.append(
                Paragraph(
                    str(text).replace("\n", "<br/>"),
                    styles["Small"],
                )
            )
            story.append(Spacer(1, 6))

    doc.build(story)
    return output.getvalue()


def _get_match_location_label(match) -> str:
    """
    Local aproximado no texto analisado.
    Funciona com a versão nova do veritas_utils.py, mas não quebra se os campos
    ainda não existirem.
    """
    start = getattr(match, "query_start_word", None)
    end = getattr(match, "query_end_word", None)
    chunk_index = getattr(match, "query_chunk_index", None)
    total_chunks = getattr(match, "total_query_chunks", None)

    if start and end:
        label = f"Palavras {start} a {end}"

        if chunk_index and total_chunks:
            label += f" — trecho {chunk_index} de {total_chunks}"
        elif chunk_index:
            label += f" — trecho {chunk_index}"

        return label

    return "Local aproximado não identificado"


def _get_source_location_label(match) -> str:
    """
    Local aproximado no documento-fonte/biblioteca.
    """
    start = getattr(match, "source_start_word", None)
    end = getattr(match, "source_end_word", None)
    chunk_index = getattr(match, "source_chunk_index", None)

    if start and end:
        label = f"Palavras {start} a {end}"

        if chunk_index:
            label += f" — trecho {chunk_index}"

        return label

    return "Local aproximado na fonte não identificado"


def generate_local_report(name, similarity, matches, coverage, disclaimer) -> bytes:
    match_lines = []

    for i, match in enumerate(matches, 1):
        match_lines.append(
            f"<b>{i}. Fonte:</b> {_safe(match.source_doc)}<br/>"
            f"<b>Correspondência:</b> {match.score * 100:.1f}%<br/>"
            f"<b>Local aproximado no texto analisado:</b> {_safe(_get_match_location_label(match))}<br/>"
            f"<b>Local aproximado na fonte:</b> {_safe(_get_source_location_label(match))}<br/><br/>"
            f"<b>Trecho analisado:</b><br/>{_safe(match.query_chunk)}<br/><br/>"
            f"<b>Trecho da fonte:</b><br/>{_safe(match.source_chunk)}"
        )

    return _pdf_bytes(
        "Relatório Veritas — Comparação local",
        name,
        [
            (
                "Resumo",
                [
                    f"Similaridade aproximada com a biblioteca: {similarity * 100:.1f}%",
                    _safe(coverage),
                ],
            ),
            (
                "Mapa de similaridade",
                match_lines or ["Nenhuma correspondência acima do limiar selecionado."],
            ),
            (
                "Observação sobre localização",
                [
                    "A localização é aproximada por contagem de palavras e trechos. "
                    "O Veritas ainda não identifica página ou linha exata em arquivos PDF, DOCX ou TXT."
                ],
            ),
            (
                "Limitações",
                [_safe(disclaimer)],
            ),
        ],
    )


def generate_web_report(name, hits, coverage, disclaimer) -> bytes:
    lines = []

    for i, hit in enumerate(hits, 1):
        lines.append(
            f"<b>{i}. {_safe(hit.title)}</b><br/>"
            f"<b>URL:</b> {_safe(hit.link)}<br/>"
            f"<b>Proximidade com o snippet:</b> {hit.score * 100:.1f}%<br/>"
            f"<b>Snippet:</b> {_safe(hit.snippet)}"
        )

    return _pdf_bytes(
        "Relatório Veritas — Busca web",
        name,
        [
            ("Cobertura", [_safe(coverage)]),
            ("Resultados", lines or ["Nenhum resultado localizado."]),
            ("Limitações", [_safe(disclaimer)]),
        ],
    )


def generate_linguistic_report(name, result, disclaimer) -> bytes:
    metrics = [
        f"{_safe(label)}: {_safe(value)}"
        for label, value in result["display_metrics"].items()
    ]

    observations = result["observations"] or [
        "Nenhuma observação relevante para os indicadores avaliados."
    ]

    observations = [_safe(item) for item in observations]

    return _pdf_bytes(
        "Relatório Veritas — Padrões linguísticos",
        name,
        [
            ("Síntese", [_safe(result["summary"])]),
            ("Indicadores", metrics),
            ("Observações", observations),
            ("Limitações", [_safe(disclaimer)]),
        ],
    )
