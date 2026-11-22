import math
from threading import Lock
from typing import List


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_model = None
_model_lock = Lock()


class EmbeddingError(RuntimeError):
    pass


def _load_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                try:
                    # Import and model download are deferred until the first comparison.
                    from sentence_transformers import SentenceTransformer

                    _model = SentenceTransformer(MODEL_NAME)
                except Exception:
                    raise EmbeddingError("The semantic matching model could not load. Check the model cache and network connection.") from None
    return _model


def get_embedding(text: str) -> List[float]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Embedding text cannot be empty.")
    model = _load_model()
    try:
        vector = model.encode(text, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
        embedding = [float(value) for value in vector.tolist()]
        if not embedding or not all(math.isfinite(value) for value in embedding):
            raise ValueError("Invalid embedding vector")
    except Exception:
        raise EmbeddingError("The semantic matching model could not encode the text.") from None
    return embedding
