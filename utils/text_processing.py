"""
utils/text_processing.py
------------------------
Text utilities: cleaning, chunking, and semantic deduplication.
Used by the Content Processing Agent and Analysis Agent.
"""

import re
import unicodedata
from typing import List

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from core.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


# ── Text Cleaning ─────────────────────────────────────────────────────────────

_WHITESPACE_RE = re.compile(r"\s{2,}")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(text: str) -> str:
    """
    Remove noise from raw scraped text:
    - Control characters
    - Unicode normalization (NFC)
    - Consecutive whitespace / blank lines collapsed
    - Leading/trailing whitespace stripped
    """
    if not text:
        return ""
    text = _CONTROL_CHARS_RE.sub("", text)
    text = unicodedata.normalize("NFC", text)
    # Collapse 3+ consecutive blank lines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def truncate_to_tokens(text: str, max_chars: int) -> str:
    """Rough token limit: 1 token ≈ 4 chars. Truncate at sentence boundary."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    # Try to end at sentence boundary
    last_period = truncated.rfind(".")
    if last_period > max_chars * 0.8:
        return truncated[: last_period + 1]
    return truncated


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = settings.CHUNK_SIZE,
    overlap: int = settings.CHUNK_OVERLAP,
) -> List[str]:
    """
    Split *text* into overlapping chunks of approximately *chunk_size* chars.
    Splits prefer sentence boundaries ('. ') over hard character cuts.

    Returns a list of chunk strings.
    """
    if not text:
        return []

    sentences: List[str] = re.split(r"(?<=[.!?])\s+", text)
    chunks: List[str] = []
    current = ""

    for sentence in sentences:
        # If adding this sentence stays under limit — accumulate
        if len(current) + len(sentence) + 1 <= chunk_size:
            current = (current + " " + sentence).strip()
        else:
            if current:
                chunks.append(current)
            # Start new chunk with overlap from the previous one
            if chunks and overlap > 0:
                prev_words = current.split()
                overlap_words = prev_words[-max(1, overlap // 6):]
                current = " ".join(overlap_words) + " " + sentence
            else:
                current = sentence

    if current:
        chunks.append(current)

    logger.debug("text_chunked", total_chunks=len(chunks))
    return chunks


# ── Semantic Deduplication ────────────────────────────────────────────────────

def _bag_of_words_vector(text: str, vocab: dict) -> np.ndarray:
    """Simple BoW vector over a shared vocabulary (no external deps)."""
    vec = np.zeros(len(vocab), dtype=np.float32)
    words = re.findall(r"\b\w+\b", text.lower())
    for w in words:
        if w in vocab:
            vec[vocab[w]] += 1
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def deduplicate_texts(
    texts: List[str],
    threshold: float = settings.DEDUP_THRESHOLD,
) -> List[str]:
    """
    Remove near-duplicate texts using cosine similarity on a shared BoW vocab.
    Returns the deduplicated subset preserving original order.

    *threshold* – documents with cosine similarity ≥ this value are considered
                  duplicates; only the first occurrence is kept.
    """
    if len(texts) <= 1:
        return texts

    # Build shared vocabulary
    vocab: dict = {}
    idx = 0
    for t in texts:
        for w in re.findall(r"\b\w+\b", t.lower()):
            if w not in vocab:
                vocab[w] = idx
                idx += 1

    vectors = np.vstack([_bag_of_words_vector(t, vocab) for t in texts])
    sim_matrix = cosine_similarity(vectors)

    kept: List[str] = []
    dropped = set()

    for i, text in enumerate(texts):
        if i in dropped:
            continue
        kept.append(text)
        for j in range(i + 1, len(texts)):
            if sim_matrix[i, j] >= threshold:
                dropped.add(j)

    logger.info(
        "deduplication_complete",
        original=len(texts),
        kept=len(kept),
        dropped=len(texts) - len(kept),
    )
    return kept


# ── Source Credibility ────────────────────────────────────────────────────────

# Simple domain-tier heuristic — extend as needed
_HIGH_CREDIBILITY_DOMAINS = {
    "nature.com", "science.org", "nejm.org", "thelancet.com",
    "pubmed.ncbi.nlm.nih.gov", "scholar.google.com",
    "arxiv.org", "ieee.org", "acm.org",
    "who.int", "cdc.gov", "nih.gov", "europa.eu",
    "reuters.com", "apnews.com", "bbc.com", "theguardian.com",
    "nytimes.com", "wsj.com", "economist.com",
    "mit.edu", "stanford.edu", "harvard.edu",
}

_LOW_CREDIBILITY_SIGNALS = {
    "blogspot.com", "wordpress.com", "tumblr.com",
    "reddit.com", "quora.com",
}


def score_source_credibility(url: str) -> float:
    """
    Return a credibility score in [0.0, 1.0] for a given URL.

    Scoring tiers:
      1.0  – known high-credibility academic / government / tier-1 news domains
      0.7  – HTTPS + recognised TLD (.edu, .gov, .org)
      0.5  – HTTPS generic domain
      0.2  – known low-credibility signals
      0.1  – HTTP (no encryption)
    """
    url_lower = url.lower()
    from urllib.parse import urlparse
    parsed = urlparse(url_lower)
    domain = parsed.netloc.lstrip("www.")

    # Check high-credibility whitelist
    for hc_domain in _HIGH_CREDIBILITY_DOMAINS:
        if domain == hc_domain or domain.endswith("." + hc_domain):
            return 1.0

    # Check low-credibility signals
    for lc_signal in _LOW_CREDIBILITY_SIGNALS:
        if lc_signal in domain:
            return 0.2

    # HTTPS + trusted TLD
    if parsed.scheme == "https":
        if any(domain.endswith(tld) for tld in (".edu", ".gov", ".org")):
            return 0.7
        return 0.5

    return 0.1
