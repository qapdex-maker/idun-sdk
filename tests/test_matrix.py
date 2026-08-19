"""Offline tests for Idun Matrix retrieval + cell parsing (IDEA α). No network/API."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from idun.retrieve import chunk_text, rank_chunks, retrieve
from idun.matrix import _parse, build_matrix, build_drift


def test_chunk_text_overlap():
    t = "x" * 100 + " " + "y" * 100 + " " + "z" * 100
    chunks = chunk_text(t, size=80, overlap=20)
    assert len(chunks) >= 3
    # overlap: end of one chunk appears near start of next
    assert chunks[0][-10:] in chunks[1] or chunks[1][-10:] in chunks[2]


def test_rank_chunks_picks_relevant():
    chunks = [
        "The recyclate quota is 30 percent for packaging.",
        "The office is open from nine to five on weekdays.",
        "Contoso leads on service model and takeback programs.",
    ]
    top = rank_chunks("recyclate quota packaging", chunks, top_k=1)
    assert "recyclate" in top[0].lower()


def test_retrieve_returns_named_hits():
    docs = {"a.txt": "recyclate quota 30 percent packaging", "b.txt": "lunch menu soup salad"}
    hits = retrieve("recyclate quota", docs, top_k=1)
    assert hits and hits[0][0] == "a.txt"


def test_parse_green():
    c = _parse("The quota is 30%. [Section 4.2]")
    assert c["status"] == "GREEN"
    assert "Section 4.2" in c["citation"]


def test_parse_gray():
    c = _parse("NO INFO")
    assert c["status"] == "GRAY"


def test_parse_red():
    c = _parse("CONTRADICTION: clause says 30% but policy says 50%. [Clause 3]")
    assert c["status"] == "RED"
    assert "Clause 3" in c["citation"]


class _FakeClient:
    def __init__(self, responder):
        self._r = responder
    def complete(self, prompt, max_output_tokens=400):
        return {"text": self._r(prompt)}


def test_build_matrix_offline():
    docs = {"contract_a.txt": "recyclate quota 30 percent", "contract_b.txt": "no relevant clause"}
    questions = ["What is the recyclate quota?"]
    def responder(prompt):
        # contract_b's chunk text is "no relevant clause" -> no answer
        if "no relevant clause" in prompt:
            return "NO INFO"
        return "30 percent. [Section 4]"
    matrix = build_matrix(_FakeClient(responder), docs, questions)
    cell_a = matrix[questions[0]]["contract_a.txt"]
    cell_b = matrix[questions[0]]["contract_b.txt"]
    assert cell_a["status"] == "GREEN"
    assert cell_b["status"] == "GRAY"


class _FakeDriftClient:
    def __init__(self, responder):
        self._r = responder
    def complete(self, prompt, max_output_tokens=400):
        return {"text": self._r(prompt)}

def test_build_drift_offline():
    a = "recyclate quota 30 percent packaging. Takeback at 1200 points."
    b = "recyclate target 45 percent by 2030. No takeback mentioned."
    topics = ["recyclate quota", "takeback service"]
    def responder(prompt):
        # build_drift injects "TOPIC: <topic>" into the prompt
        if "TOPIC: takeback" in prompt:
            return "ONE-SIDED: B says no takeback; A has 1200 points"
        return "CONTRADICTION: A says 30%, B says 45%"
    res = build_drift(_FakeDriftClient(responder), a, b, topics)
    assert res["recyclate quota"]["verdict"] == "RED"
    assert res["takeback service"]["verdict"] == "GRAY"
