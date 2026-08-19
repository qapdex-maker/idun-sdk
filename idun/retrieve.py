"""Retrieval helper for Idun Matrix (IDEA α).

Stdlib-only, tenant-agnostic. Splits documents into chunks and ranks them by a
lightweight keyword overlap score (BM25-lite) so the SDK can answer questions
"from the provided context only" without an external vector store.

The Idun SDK itself does NOT embed or call a model here — retrieval is pure
text matching; the LLM call still goes through IdunClient.complete().
"""

import re
from collections import defaultdict


def chunk_text(text, size=1500, overlap=150):
    """Split text into ~`size`-char chunks with `overlap` characters of context."""
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


_STOP = set("the a an and or of to in on for with is are was were be been being "
            "this that these those it its as at by from we you they he she them "
            "will would can could should may might must do does did has have had "
            "not no nor so if then than too very just also more most other some "
            "any all each both few many such only own same s t can t".split())


def _tokens(s):
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in _STOP and len(w) > 1]


def _idf(docs_tokens):
    df = defaultdict(int)
    for toks in docs_tokens:
        for w in set(toks):
            df[w] += 1
    n = max(len(docs_tokens), 1)
    return {w: (1 + (n - freq) / n) for w, freq in df.items()}


def rank_chunks(question, chunks, top_k=3):
    """Return the top_k chunks most relevant to `question` (BM25-lite)."""
    if not chunks:
        return []
    all_tokens = [_tokens(c) for c in chunks]
    idf = _idf(all_tokens)
    q = _tokens(question)
    if not q:
        # no query tokens -> return first chunks
        return chunks[:top_k]
    scores = []
    for i, toks in enumerate(all_tokens):
        tf = defaultdict(int)
        for w in toks:
            tf[w] += 1
        score = 0.0
        for w in q:
            if w in tf:
                # BM25-lite: tf * idf, length-normalized
                score += (tf[w] * (1 + idf.get(w, 0))) / (len(toks) + 1)
        scores.append((score, i))
    scores.sort(reverse=True)
    return [chunks[i] for _, i in scores[:top_k] if _ > 0] or chunks[:top_k]


def retrieve(question, documents, top_k=3, chunk_size=1500):
    """Given {name: text} documents, return [(doc_name, chunk_text), ...] for `question`."""
    hits = []
    for name, text in documents.items():
        for ch in rank_chunks(question, chunk_text(text, chunk_size)):
            hits.append((name, ch))
    # sort hits across docs by a light global re-rank (chunk score already per-doc)
    # keep top_k*len(documents) but cap to avoid huge context
    return hits[: top_k * len(documents)]
