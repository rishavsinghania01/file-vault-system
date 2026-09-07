"""Text extraction and vector operations used by semantic search."""

import math
from functools import lru_cache

from django.conf import settings


class EmbeddingUnavailable(RuntimeError):
    """Raised when the configured embedding model cannot be loaded."""


@lru_cache(maxsize=1)
def _embedding_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise EmbeddingUnavailable(
            "Semantic search dependencies are not installed. "
            "Install requirements-semantic.txt and restart the backend."
        ) from exc

    model_name = getattr(
        settings,
        "FILE_EMBEDDING_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2",
    )
    return SentenceTransformer(model_name)


def embed_text(text):
    """Create a normalised embedding for document or query text."""
    cleaned = " ".join(text.split())
    if not cleaned:
        return None
    max_characters = getattr(settings, "MAX_EMBEDDING_CHARACTERS", 120_000)
    vector = _embedding_model().encode(
        cleaned[:max_characters],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vector.tolist()


def extract_text(file_obj, file_type, content_type=""):
    """Extract searchable text from text files and PDFs, then rewind the upload."""
    file_type = (file_type or "").lower()
    content_type = (content_type or "").lower()
    max_characters = getattr(settings, "MAX_EXTRACTED_TEXT_CHARACTERS", 500_000)

    try:
        file_obj.seek(0)
        if file_type == "pdf" or content_type == "application/pdf":
            from pypdf import PdfReader

            reader = PdfReader(file_obj)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            return text[:max_characters]

        text_extensions = {"txt", "md", "csv", "json", "py", "js", "ts", "html", "css", "xml"}
        if content_type.startswith("text/") or file_type in text_extensions:
            raw = file_obj.read(max_characters * 4)
            return raw.decode("utf-8", errors="ignore")[:max_characters]
        return ""
    finally:
        file_obj.seek(0)


def build_document_embedding(file_obj, file_type, content_type=""):
    text = extract_text(file_obj, file_type, content_type)
    return text, embed_text(text) if text else None


def cosine_similarity(left, right):
    if not left or not right or len(left) != len(right):
        return 0.0
    dot_product = sum(a * b for a, b in zip(left, right))
    left_length = math.sqrt(sum(value * value for value in left))
    right_length = math.sqrt(sum(value * value for value in right))
    if not left_length or not right_length:
        return 0.0
    return dot_product / (left_length * right_length)
