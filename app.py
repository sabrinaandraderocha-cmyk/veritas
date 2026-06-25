from __future__ import annotations

import difflib
import math
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests
import streamlit as st
from streamlit_option_menu import option_menu

try:
    from veritas_utils import (
        compute_matches,
        extract_text_from_docx_bytes,
        extract_text_from_pdf_bytes,
        extract_text_from_txt_bytes,
    )
    from veritas_report import generate_local_report, generate_web_report, generate_linguistic_report
    CORE_AVAILABLE = True
    CORE_ERROR = ""
except ImportError as exc:
    CORE_AVAILABLE = False
    CORE_ERROR = str(exc)

APP_TITLE = "Veritas"
APP_SUBTITLE = "Análise de Similaridade e Integridade Acadêmica"

LOCAL_DISCLAIMER = (
    "O resultado informa correspondências com a biblioteca selecionada. "
    "Não comprova originalidade nem determina plágio. A interpretação exige análise humana e contextual."
)

WEB_DISCLAIMER = (
    "A busca web compara trechos do texto com prévias de resultados fornecidas pelo mecanismo de busca. "
    "Os percentuais são preliminares, não representam comparação integral com as páginas e não constituem prova de plágio."
)

LINGUISTIC_DISCLAIMER = (
    "Os indicadores descrevem características linguísticas do texto. Eles não determinam autoria humana, "
    "uso de inteligência artificial ou fraude acadêmica."
)

PROFILES = {
    "Padrão (equilibrado)": {
        "chunk_words": 60,
        "stride_words": 30,
        "threshold": 0.75,
        "top_k_per_chunk": 1,
    },
    "Rigoroso (correspondência literal)": {
        "chunk_words": 80,
        "stride_words": 40,
        "threshold": 0.86,
        "top_k_per_chunk": 1,
    },
    "Sensível (correspondência aproximada)": {
        "chunk_words": 40,
        "stride_words": 20,
        "threshold": 0.64,
        "top_k_per_chunk": 1,
    },
}


@dataclass
class WebHit:
    title: str
    link: str
    snippet: str
    score: float
    chunk: str


def split_words(text: str) -> List[str]:
    return re.findall(r"[A-Za-zÀ-ÿ0-9]+", (text or "").lower())


def count_possible_chunks(text: str, chunk_words: int, stride_words: int) -> int:
    n = len(split_words(text))
    if n < max(12, chunk_words // 2):
        return 0
    return 1 + max(0, (n - chunk_words) // max(1, stride_words))


def build_chunks(text: str, chunk_words: int, stride_words: int, max_chunks: int) -> List[str]:
    words = split_words(text)
    chunks: List[str] = []

    for start in range(0, len(words), max(1, stride_words)):
        chunk = words[start:start + chunk_words]

        if len(chunk) < max(12, chunk_words // 2):
            break

        chunks.append(" ".join(chunk))

        if len(chunks) >= max_chunks:
            break

    return list(dict.fromkeys(chunks))


def read_uploaded_file(uploaded_file) -> str:
    if not uploaded_file:
        return ""

    if not CORE_AVAILABLE:
        raise RuntimeError(f"Módulos essenciais indisponíveis: {CORE_ERROR}")

    name = uploaded_file.name.lower()
    data = uploaded_file.getvalue()

    if name.endswith(".txt"):
        text = extract_text_from_txt_bytes(data)
    elif name.endswith(".docx"):
        text = extract_text_from_docx_bytes(data)
    elif name.endswith(".pdf"):
        text = extract_text_from_pdf_bytes(data)
    else:
        raise ValueError("Formato não suportado.")

    if not text.strip():
        raise ValueError("Não foi possível extrair texto do arquivo. PDFs digitalizados podem exigir OCR.")

    return text


def get_serpapi_key() -> Optional[str]:
    try:
        return st.secrets.get("SERPAPI_KEY") or os.getenv("SERPAPI_KEY")
    except Exception:
        return os.getenv("SERPAPI_KEY")


def serpapi_search_chunk(chunk: str, key: str, num_results: int) -> List[Dict]:
    query = f'"{chunk}"' if len(chunk) >= 80 else chunk

    response = requests.get(
        "https://serpapi.com/search.json",
        params={
            "engine": "google",
            "q": query,
            "api_key": key,
            "num": num_results,
            "hl": "pt",
            "gl": "br",
        },
        timeout=25,
    )

    response.raise_for_status()
    payload = response.json()

    if payload.get("error"):
        raise RuntimeError(payload["error"])

    return payload.get("organic_results", []) or []


def sequence_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(
        None,
        (a or "").lower(),
        (b or "").lower(),
        autojunk=False,
    ).ratio()


def web_similarity_scan(text: str, key: str, profile: Dict, num_chunks: int, num_results: int):
    chunks = build_chunks(text, profile["chunk_words"], profile["stride_words"], num_chunks)

    if not chunks:
        return [], 0

    progress = st.progress(0)
    raw_hits: List[WebHit] = []

    for index, chunk in enumerate(chunks):
        for item in serpapi_search_chunk(chunk, key, num_results):
            snippet = item.get("snippet", "") or ""
            score = sequence_similarity(chunk, snippet)

            if score >= 0.12:
                raw_hits.append(
                    WebHit(
                        item.get("title", "Resultado"),
                        item.get("link", ""),
                        snippet,
                        score,
                        chunk,
                    )
                )

        progress.progress((index + 1) / len(chunks))

    progress.empty()

    unique: Dict[str, WebHit] = {}

    for hit in sorted(raw_hits, key=lambda item: item.score, reverse=True):
        if hit.link and hit.link not in unique:
            unique[hit.link] = hit

    return list(unique.values())[:20], len(chunks)


def analyze_linguistic_patterns(text: str) -> Dict:
    words = split_words(text)
    sentences = [
        s.strip()
        for s in re.split(r"[.!?]+", text or "")
        if len(split_words(s)) >= 3
    ]
    paragraphs = [
        p.strip()
        for p in re.split(r"\n\s*\n", text or "")
        if p.strip()
    ]

    if len(words) < 80 or len(sentences) < 4:
        return {
            "sufficient": False,
            "summary": "Texto insuficiente para uma análise linguística minimamente estável.",
            "display_metrics": {
                "Palavras": len(words),
                "Frases": len(sentences),
            },
            "observations": [
                "Recomenda-se utilizar pelo menos 80 palavras e quatro frases."
            ],
        }

    unique_ratio = len(set(words)) / len(words)

    sentence_lengths = [len(split_words(sentence)) for sentence in sentences]
    mean_sentence = sum(sentence_lengths) / len(sentence_lengths)
    variance = sum((value - mean_sentence) ** 2 for value in sentence_lengths) / len(sentence_lengths)
    sentence_cv = math.sqrt(variance) / mean_sentence if mean_sentence else 0

    connectors = [
        "além disso",
        "em suma",
        "portanto",
        "todavia",
        "nesse sentido",
        "por outro lado",
        "vale ressaltar",
        "conclui-se",
    ]

    connector_count = sum((text or "").lower().count(item) for item in connectors)
    connector_density = connector_count / len(words) * 1000

    repeated_bigrams = {}

    for a, b in zip(words, words[1:]):
        pair = f"{a} {b}"
        repeated_bigrams[pair] = repeated_bigrams.get(pair, 0) + 1

    repeated_pairs = sum(1 for count in repeated_bigrams.values() if count >= 3)

    observations: List[str] = []

    if unique_ratio < 0.42:
        observations.append("Diversidade lexical relativamente baixa para o tamanho do texto.")

    if sentence_cv < 0.32:
        observations.append("Comprimento das frases pouco variável, indicando elevada uniformidade estrutural.")

    if connector_density > 8:
        observations.append("Concentração elevada dos conectores examinados.")

    if repeated_pairs >= 5:
        observations.append("Há repetição frequente de algumas sequências de duas palavras.")

    if len(paragraphs) >= 3:
        paragraph_lengths = [len(split_words(p)) for p in paragraphs]
        p_mean = sum(paragraph_lengths) / len(paragraph_lengths)
        p_var = sum((x - p_mean) ** 2 for x in paragraph_lengths) / len(paragraph_lengths)
        p_cv = math.sqrt(p_var) / p_mean if p_mean else 0

        if p_cv < 0.25:
            observations.append("Os parágrafos apresentam extensão bastante uniforme.")

    summary = (
        "Foram observadas algumas regularidades que merecem leitura contextual."
        if observations
        else "Os indicadores avaliados não apresentaram concentração incomum, mas isso não permite concluir autoria ou processo de produção."
    )

    return {
        "sufficient": True,
        "summary": summary,
        "display_metrics": {
            "Palavras": len(words),
            "Diversidade lexical": f"{unique_ratio * 100:.1f}%",
            "Média de palavras por frase": f"{mean_sentence:.1f}",
            "Variação do tamanho das frases": f"{sentence_cv:.2f}",
            "Conectores por mil palavras": f"{connector_density:.1f}",
        },
        "observations": observations,
    }


def inject_css():
    st.markdown(
        """
        <style>
          .header {
            padding: 1.25rem;
            background: #fff;
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            text-align: center;
            margin-bottom: 1rem;
          }

          .card {
            background: #fff;
            padding: 1.1rem;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            margin-bottom: .8rem;
          }

          .note {
            background: #f8fafc;
            padding: .85rem;
            border-left: 4px solid #64748b;
            border-radius: 8px;
            margin: .6rem 0 1rem;
          }

          .muted {
            color: #64748b;
            font-size: .9rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(page_title=APP_TITLE, page_icon="🔎", layout="wide")
inject_css()

for key, default in {
    "library": {},
    "local_result": None,
    "web_result": None,
    "ling_result": None,
    "profile": "Padrão (equilibrado)",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ==========================================================
# ONBOARDING INICIAL
# Esta etapa é segura: não usa banco de dados, não altera análises
# e aparece apenas na sessão atual do navegador.
# ==========================================================

if "onboarding_completed" not in st.session_state:
    st.session_state.onboarding_completed = False

if not st.session_state.onboarding_completed:
    st.markdown(
        f"<div class='header'><h1>🔎 {APP_TITLE}</h1><p>{APP_SUBTITLE}</p></div>",
        unsafe_allow_html=True,
    )

    st.markdown("## Antes de começar")

    onboarding_html = (
        "<div class='card'>"
        "<h3>Bem-vinda(o) ao Veritas</h3>"
        "<p>"
        "O Veritas é uma ferramenta de apoio à leitura acadêmica, "
        "à análise de similaridade textual e à observação de padrões linguísticos."
        "</p>"
        "<p>"
        "Ele <b>não determina plágio</b>, <b>não comprova originalidade</b> "
        "e <b>não afirma se um texto foi produzido por inteligência artificial</b>."
        "</p>"
        "<p>"
        "Os resultados devem sempre ser interpretados por uma pessoa, "
        "considerando o contexto, a finalidade do texto e os critérios acadêmicos aplicáveis."
        "</p>"
        "<p>"
        "Evite enviar documentos com dados pessoais, clínicos, sigilosos "
        "ou sem autorização de uso."
        "</p>"
        "</div>"
    )

    st.markdown(onboarding_html, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 2, 1])

    with c2:
        if st.button("Entendi e quero começar", type="primary", use_container_width=True):
            st.session_state.onboarding_completed = True
            st.rerun()

    st.stop()


st.markdown(
    f"<div class='header'><h1>🔎 {APP_TITLE}</h1><p>{APP_SUBTITLE}</p></div>",
    unsafe_allow_html=True,
)

if not CORE_AVAILABLE:
    st.error(f"O aplicativo não pode executar análises porque faltam módulos essenciais: {CORE_ERROR}")
    st.stop()

selected = option_menu(
    None,
    [
        "Nova análise",
        "Biblioteca",
        "Busca web",
        "Padrões linguísticos",
        "Relatórios",
    ],
    icons=[
        "search",
        "folder",
        "globe",
        "body-text",
        "file-earmark-pdf",
    ],
    orientation="horizontal",
)

with st.sidebar:
    st.header("Configurações")

    st.session_state.profile = st.selectbox(
        "Perfil de comparação",
        list(PROFILES),
        index=list(PROFILES).index(st.session_state.profile),
    )

    st.caption("Os documentos da biblioteca permanecem somente durante a sessão atual.")
    st.divider()
    st.caption("Veritas © 2026")


def text_input_block(prefix: str):
    pasted = ""
    uploaded_text = ""
    uploaded_name = ""

    tab1, tab2 = st.tabs(["Colar texto", "Enviar arquivo"])

    with tab1:
        pasted = st.text_area("Texto", height=260, key=f"{prefix}_paste")

    with tab2:
        uploaded = st.file_uploader(
            "PDF, DOCX ou TXT",
            type=["pdf", "docx", "txt"],
            key=f"{prefix}_upload",
        )

        if uploaded:
            try:
                uploaded_text = read_uploaded_file(uploaded)
                uploaded_name = uploaded.name

                st.success(f"Texto extraído: {len(split_words(uploaded_text))} palavras.")

                with st.expander("Conferir texto extraído"):
                    st.text_area(
                        "Pré-visualização",
                        uploaded_text[:12000],
                        height=260,
                        disabled=True,
                        key=f"{prefix}_preview",
                    )

            except Exception as exc:
                st.error(str(exc))

    return (uploaded_text or pasted).strip(), (uploaded_name or "Texto inserido")


if selected == "Nova análise":
    st.subheader("Nova análise local")
    st.markdown(f"<div class='note'>{LOCAL_DISCLAIMER}</div>", unsafe_allow_html=True)

    left, right = st.columns([1, 1.15])

    with left:
        text, name = text_input_block("local")
        profile = PROFILES[st.session_state.profile]

        if st.button("Comparar com a biblioteca", type="primary", disabled=not text):
            if not st.session_state.library:
                st.error("Adicione ao menos um documento à biblioteca.")
            else:
                with st.spinner("Comparando os documentos..."):
                    similarity, matches = compute_matches(
                        text,
                        st.session_state.library,
                        **profile,
                    )

                    total_chunks = count_possible_chunks(
                        text,
                        profile["chunk_words"],
                        profile["stride_words"],
                    )

                    st.session_state.local_result = {
                        "name": name,
                        "text": text,
                        "similarity": similarity,
                        "matches": matches,
                        "total_chunks": total_chunks,
                        "documents": len(st.session_state.library),
                    }

    with right:
        result = st.session_state.local_result

        if result:
            score = result["similarity"]

            if score < .03:
                label = "Baixa similaridade"
                explanation = "Não foram encontradas correspondências relevantes na biblioteca selecionada."
            elif score < .25:
                label = "Similaridade limitada"
                explanation = "Alguns fragmentos apresentam correspondência e devem ser revisados no contexto."
            else:
                label = "Similaridade elevada"
                explanation = "Uma parcela relevante dos fragmentos analisados encontrou correspondência na biblioteca."

            st.markdown(
                f"""
                <div class='card'>
                    <h2>{score * 100:.1f}%</h2>
                    <b>{label}</b>
                    <p>{explanation}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            c1, c2, c3 = st.columns(3)
            c1.metric("Trechos avaliados", result["total_chunks"])
            c2.metric("Documentos", result["documents"])
            c3.metric("Correspondências", len(result["matches"]))

            st.caption(
                "O percentual representa cobertura aproximada de trechos com correspondência, "
                "sem concluir plágio ou originalidade."
            )

            for match in result["matches"]:
                with st.expander(f"{match.score * 100:.1f}% — {match.source_doc}"):
                    st.markdown("**Trecho analisado**")
                    st.write(match.query_chunk)

                    st.markdown("**Trecho da fonte**")
                    st.write(match.source_chunk)


elif selected == "Biblioteca":
    st.subheader("Biblioteca de comparação")

    st.info(
        "Os arquivos permanecem apenas na sessão atual. "
        "Não envie documentos sem autorização ou que contenham dados sensíveis desnecessários."
    )

    uploads = st.file_uploader(
        "Adicionar documentos",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        key="library_upload",
    )

    if uploads and st.button("Adicionar à biblioteca", type="primary"):
        added = 0

        for upload in uploads:
            try:
                text = read_uploaded_file(upload)
                st.session_state.library[upload.name] = text
                added += 1
            except Exception as exc:
                st.error(f"{upload.name}: {exc}")

        if added:
            st.success(f"{added} documento(s) adicionado(s).")
            st.rerun()

    if not st.session_state.library:
        st.warning("A biblioteca está vazia.")

    for filename, content in list(st.session_state.library.items()):
        c1, c2, c3 = st.columns([5, 1, 1])

        c1.write(f"**{filename}** — {len(split_words(content))} palavras")

        with c2:
            with st.popover("Visualizar"):
                st.text_area(
                    filename,
                    content[:15000],
                    height=300,
                    disabled=True,
                    key=f"view_{filename}",
                )

        if c3.button("Remover", key=f"remove_{filename}"):
            del st.session_state.library[filename]
            st.rerun()


elif selected == "Busca web":
    st.subheader("Busca de correspondências na web")
    st.markdown(f"<div class='note'>{WEB_DISCLAIMER}</div>", unsafe_allow_html=True)

    text, name = text_input_block("web")
    profile = PROFILES[st.session_state.profile]

    max_possible = (
        count_possible_chunks(
            text,
            profile["chunk_words"],
            profile["stride_words"],
        )
        if text
        else 0
    )

    requested = st.slider(
        "Limite de trechos enviados para busca na web",
        1,
        20,
        min(8, max(1, max_possible or 8)),
    )

    preview = (
        build_chunks(
            text,
            profile["chunk_words"],
            profile["stride_words"],
            requested,
        )
        if text
        else []
    )

    if preview:
        with st.expander("Ver os trechos que serão pesquisados na internet"):
            st.caption(
                "Para proteger a privacidade, o Veritas não envia o documento inteiro. "
                "Abaixo estão apenas os trechos que poderão ser enviados ao mecanismo de busca."
            )

            for i, fragment in enumerate(preview, 1):
                st.write(f"**Trecho {i}:** {fragment}")

    consent = st.checkbox(
        "Revisei os trechos e confirmo que não contêm dados pessoais, clínicos, "
        "sigilosos ou conteúdo cuja transmissão não seja autorizada."
    )

    if st.button("Pesquisar na web", type="primary", disabled=not (text and consent)):
        key = get_serpapi_key()

        if not key:
            st.error("A chave SERPAPI_KEY não está configurada.")
        else:
            try:
                hits, searched = web_similarity_scan(text, key, profile, requested, 5)

                st.session_state.web_result = {
                    "name": name,
                    "hits": hits,
                    "searched": searched,
                    "possible": max_possible,
                }

            except Exception as exc:
                st.error(f"A busca não pôde ser concluída: {exc}")

    result = st.session_state.web_result

    if result:
        coverage = (
            result["searched"] / result["possible"] * 100
            if result["possible"]
            else 0
        )

        st.info(
            f"Foram pesquisados {result['searched']} de aproximadamente "
            f"{result['possible']} trechos possíveis "
            f"({coverage:.1f}% de cobertura estimada)."
        )

        if not result["hits"]:
            st.success("Nenhum resultado relevante foi encontrado nas prévias consultadas.")

        for hit in result["hits"]:
            st.markdown(f"### [{hit.title}]({hit.link})")
            st.write(hit.snippet)

            st.caption(
                f"Semelhança com a prévia do resultado de busca: {hit.score * 100:.1f}%. "
                "Esta comparação é preliminar: usa apenas o pequeno trecho exibido pelo buscador, "
                "não a página completa."
            )

            st.divider()


elif selected == "Padrões linguísticos":
    st.subheader("Análise exploratória de padrões linguísticos")
    st.markdown(f"<div class='note'>{LINGUISTIC_DISCLAIMER}</div>", unsafe_allow_html=True)

    text, name = text_input_block("ling")

    if st.button("Analisar padrões", type="primary", disabled=not text):
        st.session_state.ling_result = {
            "name": name,
            "result": analyze_linguistic_patterns(text),
        }

    data = st.session_state.ling_result

    if data:
        result = data["result"]

        st.markdown(
            f"""
            <div class='card'>
                <h3>Síntese</h3>
                <p>{result['summary']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        columns = st.columns(min(3, len(result["display_metrics"])))

        for index, (label, value) in enumerate(result["display_metrics"].items()):
            columns[index % len(columns)].metric(label, value)

        st.markdown("#### Observações")

        if result["observations"]:
            for observation in result["observations"]:
                st.write(f"• {observation}")
        else:
            st.write("Nenhuma concentração incomum nos indicadores avaliados.")


elif selected == "Relatórios":
    st.subheader("Relatórios")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("#### Comparação local")
        result = st.session_state.local_result

        if result:
            coverage = (
                f"Foram avaliados aproximadamente {result['total_chunks']} trechos "
                f"contra {result['documents']} documentos."
            )

            pdf = generate_local_report(
                result["name"],
                result["similarity"],
                result["matches"],
                coverage,
                LOCAL_DISCLAIMER,
            )

            st.download_button(
                "Baixar PDF local",
                pdf,
                "veritas_comparacao_local.pdf",
                "application/pdf",
            )
        else:
            st.caption("Nenhuma análise disponível.")

    with c2:
        st.markdown("#### Busca web")
        result = st.session_state.web_result

        if result:
            coverage = (
                f"Foram enviados {result['searched']} de aproximadamente "
                f"{result['possible']} trechos possíveis."
            )

            pdf = generate_web_report(
                result["name"],
                result["hits"],
                coverage,
                WEB_DISCLAIMER,
            )

            st.download_button(
                "Baixar PDF web",
                pdf,
                "veritas_busca_web.pdf",
                "application/pdf",
            )
        else:
            st.caption("Nenhuma busca disponível.")

    with c3:
        st.markdown("#### Padrões linguísticos")
        data = st.session_state.ling_result

        if data:
            pdf = generate_linguistic_report(
                data["name"],
                data["result"],
                LINGUISTIC_DISCLAIMER,
            )

            st.download_button(
                "Baixar PDF linguístico",
                pdf,
                "veritas_padroes_linguisticos.pdf",
                "application/pdf",
            )
        else:
            st.caption("Nenhuma análise disponível.")
