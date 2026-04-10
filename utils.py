"""
Shared utilities for academic-research-mcp.

Functions that multiple modules need (title similarity, medical term
detection) live here to avoid circular imports between orchestrator
and review_manager.
"""

import re
from difflib import SequenceMatcher


# Words too generic to distinguish academic papers — downweighted in title matching
_GENERIC_WORDS = frozenset(
    "a an the of in on for and or with by to from using based via is are was "
    "were be been being do does did will would could should may might shall "
    "real time deep learning artificial intelligence machine model models "
    "method methods approach system analysis study new novel".split()
)

# Medical/biomedical domain terms — if present in query, filter S2 by Medicine
_MEDICAL_TERMS = frozenset(
    "cancer adenocarcinoma carcinoma tumor tumour neoplasia neoplasm lesion polyp "
    "esophagus esophageal gastric gastritis intestinal metaplasia dysplasia barrett "
    "colon colonic rectal endoscopy endoscopic colonoscopy gastrointestinal gi "
    "biopsy histology pathology diagnosis diagnostic clinical patient patients "
    "disease therapy treatment prognosis survival mortality morbidity "
    "inflammatory ibd crohn ulcerative colitis celiac hepatic liver pancreatic "
    "biliary gallbladder stomach duodenal jejunal ileal cecal sigmoid".split()
)


def title_similarity(query: str, title: str) -> float:
    """
    Score how well a candidate title matches a query string.
    Distinctive words (author names, disease terms) count more than
    generic words (deep, learning, real-time, method).
    """
    q_words = re.sub(r"[^a-z0-9 ]", " ", query.lower()).split()
    t_norm = re.sub(r"[^a-z0-9 ]", " ", title.lower())
    t_words = set(t_norm.split())
    if not q_words or not t_words:
        return 0.0

    # Score each query word: distinctive words worth 2x
    total_weight = 0.0
    hit_weight = 0.0
    for w in q_words:
        weight = 0.5 if w in _GENERIC_WORDS else 1.0
        total_weight += weight
        if w in t_norm:
            hit_weight += weight

    word_score = hit_weight / total_weight if total_weight > 0 else 0.0

    # Sequence similarity (catches partial word matches)
    seq_sim = SequenceMatcher(None, query.lower(), title.lower()).ratio()

    return 0.65 * word_score + 0.35 * seq_sim


def has_medical_terms(query: str) -> bool:
    """Check if a query contains medical/biomedical terms."""
    words = set(re.sub(r"[^a-z0-9 ]", " ", query.lower()).split())
    return bool(words & _MEDICAL_TERMS)
