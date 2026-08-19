"""Idun Matrix (IDEA α) — build an N×M answer matrix from documents + questions.

Tenant-agnostic, stdlib-only except the Idun SDK itself. Each (document, question)
pair becomes one cell: {answer, citation, status}. Status is derived from the
model answer: GREEN = answered + cited, RED = contradiction/wrong, GRAY = no info.

Usage:
    from idun.matrix import build_matrix
    client = IdunClient(...)  # or AsyncIdunClient
    docs = {"contract_a.txt": "...", "contract_b.txt": "..."}
    questions = ["What is the recyclate quota?", "..."]
    matrix = build_matrix(client, docs, questions)  # -> {q: {doc: cell}}
"""

import re
from .retrieve import retrieve

PROMPT = (
    "You are a precise document analyst. Answer the QUESTION using ONLY the CONTEXT "
    "below. Rules:\n"
    "1. If the context answers it, give a short answer (<= 40 words) and cite the exact "
    "source phrase in [brackets].\n"
    "2. If the context contradicts itself or the answer conflicts with a stated policy, "
    "start with CONTRADICTION: and explain briefly.\n"
    "3. If the context has NO information, reply exactly: NO INFO.\n"
    "4. Never use knowledge outside the context.\n\n"
    "CONTEXT:\n{txt}\n\nQUESTION: {q}\n\nANSWER:"
)


def _parse(cell_text):
    """Extract (answer, status, citation) from a model response."""
    t = (cell_text or "").strip()
    if t.upper().startswith("NO INFO") or t.upper() == "NO INFO":
        return {"answer": "", "citation": "", "status": "GRAY"}
    if t.upper().startswith("CONTRADICTION"):
        # citation = first bracket group if present
        cit = ""
        m = re.search(r"\[([^\]]+)\]", t)
        if m:
            cit = m.group(1)
        return {"answer": t, "citation": cit, "status": "RED"}
    # GREEN: answer + optional citation
    cit = ""
    m = re.search(r"\[([^\]]+)\]", t)
    if m:
        cit = m.group(1)
    return {"answer": t, "citation": cit, "status": "GREEN"}


def build_matrix(client, documents, questions, top_k=3):
    """Return {question: {doc_name: {answer, citation, status}}}."""
    matrix = {}
    for q in questions:
        matrix[q] = {}
        for name, text in documents.items():
            ctx = "\n---\n".join(
                f"[{n}] {c}" for n, (dn, c) in enumerate(retrieve(q, {name: text}, top_k=top_k))
            ) if False else "\n---\n".join(c for _, c in retrieve(q, {name: text}, top_k=top_k))
            prompt = PROMPT.format(txt=ctx, q=q)
            try:
                out = client.complete(prompt, max_output_tokens=400)
            except Exception as e:  # surface as GRAY cell, never fake a pass
                matrix[q][name] = {"answer": f"ERROR: {e}", "citation": "", "status": "GRAY"}
                continue
            cell = _parse(out.get("text") if isinstance(out, dict) else str(out))
            matrix[q][name] = cell
    return matrix


async def build_matrix_async(client, documents, questions, top_k=3):
    """Async variant using AsyncIdunClient.acomplete."""
    matrix = {}
    for q in questions:
        matrix[q] = {}
        for name, text in documents.items():
            ctx = "\n---\n".join(c for _, c in retrieve(q, {name: text}, top_k=top_k))
            prompt = PROMPT.format(txt=ctx, q=q)
            try:
                out = await client.acomplete(prompt, max_output_tokens=400)
            except Exception as e:
                matrix[q][name] = {"answer": f"ERROR: {e}", "citation": "", "status": "GRAY"}
                continue
            matrix[q][name] = _parse(out.get("text") if isinstance(out, dict) else str(out))
    return matrix

DRIFT_PROMPT = (
    "You compare two documents (A and B) on the SAME topic. For the topic below, "
    "state whether A and B AGREE, CONTRADICT, or whether the info is PRESENT in only "
    "one of them.\n"
    "Rules:\n"
    "1. If both say the same -> reply: AGREE: <short summary>.\n"
    "2. If they conflict -> reply: CONTRADICTION: <what A says> vs <what B says>.\n"
    "3. If only one mentions it -> reply: ONE-SIDED: <which doc> says <what>.\n"
    "4. Never use outside knowledge.\n\n"
    "TOPIC: {topic}\n\n"
    "DOCUMENT A:\n{a}\n\nDOCUMENT B:\n{b}\n\nVERDICT:"
)


def _parse_drift(text):
    t = (text or "").strip()
    up = t.upper()
    if up.startswith("AGREE"):
        return {"verdict": "GREEN", "detail": t}
    if up.startswith("CONTRADICTION"):
        return {"verdict": "RED", "detail": t}
    if up.startswith("ONE-SIDED"):
        return {"verdict": "GRAY", "detail": t}
    return {"verdict": "GRAY", "detail": t}


def build_drift(client, doc_a_text, doc_b_text, topics):
    """Compare two documents across a list of topics (IDEA γ: clause drift).

    Returns {topic: {verdict, detail}} where verdict is
    GREEN (agree) / RED (contradiction) / GRAY (one-sided).
    """
    out = {}
    for topic in topics:
        ctx_a = "\n---\n".join(c for _, c in retrieve(topic, {"A": doc_a_text}, top_k=2))
        ctx_b = "\n---\n".join(c for _, c in retrieve(topic, {"B": doc_b_text}, top_k=2))
        prompt = DRIFT_PROMPT.format(topic=topic, a=ctx_a, b=ctx_b)
        try:
            resp = client.complete(prompt, max_output_tokens=400)
        except Exception as e:
            out[topic] = {"verdict": "GRAY", "detail": f"ERROR: {e}"}
            continue
        out[topic] = _parse_drift(resp.get("text") if isinstance(resp, dict) else str(resp))
    return out


async def build_drift_async(client, doc_a_text, doc_b_text, topics):
    """Async variant of build_drift."""
    out = {}
    for topic in topics:
        ctx_a = "\n---\n".join(c for _, c in retrieve(topic, {"A": doc_a_text}, top_k=2))
        ctx_b = "\n---\n".join(c for _, c in retrieve(topic, {"B": doc_b_text}, top_k=2))
        prompt = DRIFT_PROMPT.format(topic=topic, a=ctx_a, b=ctx_b)
        try:
            resp = await client.acomplete(prompt, max_output_tokens=400)
        except Exception as e:
            out[topic] = {"verdict": "GRAY", "detail": f"ERROR: {e}"}
            continue
        out[topic] = _parse_drift(resp.get("text") if isinstance(resp, dict) else str(resp))
    return out
