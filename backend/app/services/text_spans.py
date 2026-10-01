"""Exact source offsets, sentence boundaries and adjacent exceptions."""
import re
from hashlib import sha256

VERSION = "sentence-context-v1"


def source_units(text):
    # Keep legal numbered clauses and complete sentences. Long indivisible
    # clauses remain whole; a character cap must not discard an exception.
    boundaries = [0]
    boundaries.extend(match.end() for match in re.finditer(r"(?<=[.!?。])\s+|\n+", text))
    boundaries.append(len(text))
    units = []
    for start, end in zip(boundaries, boundaries[1:]):
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end-1].isspace():
            end -= 1
        if start < end:
            units.append((start, end))
    return units


def select_windows(question, text, limit=3, budget=2400):
    units = source_units(text)
    terms = re.findall(r"[가-힣A-Za-z0-9]{2,}", question)
    pairs = {term[i:i+2] for term in terms for i in range(len(term)-1)}
    ranked = sorted(range(len(units)), key=lambda i: (
        -sum(pair in text[units[i][0]:units[i][1]] for pair in pairs), i))
    selected, consumed = [], 0
    for index in ranked:
        left, right = index, index
        # Include surrounding context and chained provisos, not an arbitrary
        # 280-character piece whose legal scope may be lost.
        if left > 0:
            left -= 1
        if right + 1 < len(units):
            right += 1
        while right + 1 < len(units) and text[units[right+1][0]:units[right+1][1]].startswith(("다만", "그러나", "단,", "제외", "예외")):
            right += 1
        start, end = units[left][0], units[right][1]
        if any(start < old_end and end > old_start for old_start, old_end in selected):
            continue
        # Never truncate a sentence to fit. If no complete context fits, the
        # document has no safe extract under this budget.
        if consumed + end-start > budget:
            continue
        selected.append((start, end))
        consumed += end-start
        if len(selected) >= limit:
            break
    digest = sha256(text.encode()).hexdigest()
    return [{"start": start, "end": end, "quote": text[start:end],
             "source_sha256": digest, "chunking_version": VERSION} for start, end in sorted(selected)]
