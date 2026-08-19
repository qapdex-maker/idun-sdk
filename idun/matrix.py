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
