from __future__ import annotations

import threading
from typing import Sequence

import numpy as np

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class SemanticUnavailable(RuntimeError):
    """Raised rather than silently substituting a word-overlap recommender."""


class SemanticEncoder:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self._model = None
        self._lock = threading.RLock()

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 384), dtype=np.float32)
        with self._lock:
            if self._model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    # Fixed, documented public model. Inference is local after download.
                    self._model = SentenceTransformer(self.model_name, device="cpu")
                except Exception as exc:
                    raise SemanticUnavailable(
                        "Semantic model could not load. Install requirements.txt and make "
                        "sure the pretrained model can be downloaded once; the server "
                        "will not pretend lexical matching is semantic understanding."
                    ) from exc
            try:
                vectors = np.asarray(
                    self._model.encode(list(texts), normalize_embeddings=True,
                                       convert_to_numpy=True, show_progress_bar=False),
                    dtype=np.float32,
                )
                if vectors.ndim != 2 or vectors.shape[0] != len(texts) or not np.isfinite(vectors).all():
                    raise ValueError("The embedding model returned invalid vectors")
                return vectors
            except Exception as exc:
                raise SemanticUnavailable("Semantic embedding inference failed") from exc


if __name__ == "__main__":
    print(f"Preparing {MODEL_NAME} ...")
    encoder = SemanticEncoder()
    encoder.encode(["An inspiring film about family and friendship."])
    print("Semantic model ready. The initial download is complete.")
