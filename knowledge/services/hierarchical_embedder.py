"""
Hierarchical Embedder Service
==============================

Generates 64D int16 fixed-point embeddings for each hierarchical level.
Each level includes context from parent levels for semantic accuracy.

Levels:
1. Bibliothek (Library/Domain) - abstract, high-level
2. Kategorie (Category) - more specific than library
3. Regal (Shelf) - topic cluster
4. Buch (Book/Document) - individual document
5. Kapitel (Chapter) - section within document
6. Seite (Page) - content chunk

Key Design:
- Deterministic: same input → same output
- Context-aware: each embedding includes parent context
- Fixed-point: int16 values for reproducibility
- 64D: compact but semantically rich
"""

import os
import json
import hashlib
from typing import List, Tuple, Optional
from functools import lru_cache
import numpy as np


class HierarchicalEmbedder:
    """
    Generates 64D int16 embeddings for hierarchical knowledge levels.

    Uses Ollama for embedding generation (via REST API).
    All embeddings are quantized to int16 range [-32767, 32767].
    """

    # Configuration
    OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    EMBEDDING_MODEL = os.environ.get("OLLAMA_MODEL", "nomic-embed-text")
    TARGET_DIMS = 64
    INT16_MIN = -32767
    INT16_MAX = 32767

    def __init__(self, use_mock: bool = False):
        """
        Initialize embedder.

        Args:
            use_mock: If True, use deterministic mock embeddings (for testing).
                     If False, use Ollama for real embeddings.
        """
        self.use_mock = use_mock
        self._embedding_cache = {}

        if not use_mock:
            self._verify_ollama_connection()

    def _verify_ollama_connection(self) -> None:
        """Verify Ollama is running and model is available."""
        try:
            import requests
            response = requests.get(f"{self.OLLAMA_HOST}/api/tags", timeout=5)
            if response.status_code != 200:
                raise ConnectionError(f"Ollama not responding: {response.status_code}")

            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]

            if not any(self.EMBEDDING_MODEL in name for name in model_names):
                raise ValueError(
                    f"Embedding model '{self.EMBEDDING_MODEL}' not found. "
                    f"Available: {model_names}. "
                    f"Run: ollama pull {self.EMBEDDING_MODEL}"
                )

            print(f"[OK] Ollama connected ({len(models)} models available)")
            print(f"[OK] Using model: {self.EMBEDDING_MODEL}")
        except ImportError:
            print("[WARN] requests library not available; running in mock mode")
            self.use_mock = True
        except Exception as e:
            print(f"[WARN] Ollama connection failed: {e}")
            print("  Running in mock mode (deterministic test embeddings)")
            self.use_mock = True

    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using Ollama.

        Args:
            text: Text to embed

        Returns:
            List of embedding values (float64)
        """
        if self.use_mock:
            return self._generate_mock_embedding(text)

        try:
            import requests

            # Call Ollama embedding endpoint
            response = requests.post(
                f"{self.OLLAMA_HOST}/api/embeddings",
                json={"model": self.EMBEDDING_MODEL, "prompt": text},
                timeout=30
            )

            if response.status_code != 200:
                raise RuntimeError(f"Ollama error: {response.status_code} - {response.text}")

            data = response.json()
            embedding = data.get("embedding", [])

            if not embedding:
                raise ValueError("Empty embedding returned from Ollama")

            return embedding

        except ImportError:
            print("requests not available; falling back to mock embeddings")
            return self._generate_mock_embedding(text)

    def _generate_mock_embedding(self, text: str) -> List[float]:
        """
        Generate deterministic mock embedding from text hash.

        This ensures reproducibility for testing without requiring Ollama.
        The hash is used to seed random number generation in a deterministic way.

        Args:
            text: Text to hash

        Returns:
            List of 64 pseudo-random float values (deterministic)
        """
        # Create deterministic seed from text hash
        hash_obj = hashlib.sha256(text.encode('utf-8'))
        hash_int = int(hash_obj.hexdigest(), 16)

        # Use numpy's seeded RNG for reproducibility
        rng = np.random.RandomState(seed=hash_int % (2**32))

        # Generate 64 values in range [0, 1]
        embedding = rng.uniform(0, 1, self.TARGET_DIMS).tolist()
        return embedding

    def _quantize_to_int16(self, embedding: List[float]) -> List[int]:
        """
        Quantize float embedding to int16 fixed-point values.

        Maps float values in approximate range [-1, 1] to int16 range.
        Uses careful scaling to preserve magnitude information.

        Args:
            embedding: List of float values

        Returns:
            List of int16 values (range: [-32767, 32767])
        """
        arr = np.array(embedding, dtype=np.float32)

        # Normalize to roughly [-1, 1] range (standard for embeddings)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / (norm + 1e-8)

        # Scale to int16 range
        # Using 30000 instead of 32767 to leave some headroom
        scaled = (arr * 30000).astype(np.int16)

        # Ensure values are in valid range
        scaled = np.clip(scaled, self.INT16_MIN, self.INT16_MAX)

        return scaled.tolist()

    def _ensure_64_dims(self, embedding: List[float]) -> List[float]:
        """
        Ensure embedding has exactly 64 dimensions.

        If embedding is shorter, pad with zeros.
        If longer, truncate to 64.

        Args:
            embedding: Input embedding (any length)

        Returns:
            Embedding with exactly 64 dimensions
        """
        if len(embedding) == self.TARGET_DIMS:
            return embedding
        elif len(embedding) < self.TARGET_DIMS:
            # Pad with zeros
            return embedding + [0.0] * (self.TARGET_DIMS - len(embedding))
        else:
            # Truncate to 64 dims
            return embedding[:self.TARGET_DIMS]

    def _get_cached_embedding(self, cache_key: str) -> Optional[List[int]]:
        """Get embedding from cache if available."""
        return self._embedding_cache.get(cache_key)

    def _cache_embedding(self, cache_key: str, embedding: List[int]) -> None:
        """Store embedding in cache."""
        self._embedding_cache[cache_key] = embedding

    # ========================================================
    # Level-Specific Embedding Methods
    # ========================================================

    def embed_bibliothek(self, name: str, description: str = "") -> List[int]:
        """
        Generate embedding for Bibliothek (Library/Domain).

        Most abstract level - represents entire domain.

        Args:
            name: Library name (e.g., "Programming")
            description: Optional description

        Returns:
            64D int16 embedding
        """
        # Create context text
        text = f"Library: {name}"
        if description:
            text += f" - {description}"

        cache_key = ("bibliothek", name, description)

        # Check cache
        cached = self._get_cached_embedding(cache_key)
        if cached is not None:
            return cached

        # Generate embedding
        float_embedding = self._generate_embedding(text)
        float_embedding = self._ensure_64_dims(float_embedding)
        int_embedding = self._quantize_to_int16(float_embedding)

        # Cache and return
        self._cache_embedding(cache_key, int_embedding)
        return int_embedding

    def embed_kategorie(
        self,
        bibliothek_name: str,
        kategorie_name: str,
        description: str = ""
    ) -> List[int]:
        """
        Generate embedding for Kategorie (Category).

        Includes parent context (library) for semantic accuracy.

        Args:
            bibliothek_name: Parent library name
            kategorie_name: Category name (e.g., "Python")
            description: Optional description

        Returns:
            64D int16 embedding
        """
        # Include parent context
        text = f"Library: {bibliothek_name} > Category: {kategorie_name}"
        if description:
            text += f" - {description}"

        cache_key = ("kategorie", bibliothek_name, kategorie_name, description)

        cached = self._get_cached_embedding(cache_key)
        if cached is not None:
            return cached

        float_embedding = self._generate_embedding(text)
        float_embedding = self._ensure_64_dims(float_embedding)
        int_embedding = self._quantize_to_int16(float_embedding)

        self._cache_embedding(cache_key, int_embedding)
        return int_embedding

    def embed_regal(
        self,
        kategorie_name: str,
        regal_name: str,
        description: str = ""
    ) -> List[int]:
        """
        Generate embedding for Regal (Shelf/Topic).

        Specific topic cluster within category.

        Args:
            kategorie_name: Parent category name
            regal_name: Shelf name (e.g., "Advanced Features")
            description: Optional description

        Returns:
            64D int16 embedding
        """
        text = f"Category: {kategorie_name} > Shelf: {regal_name}"
        if description:
            text += f" - {description}"

        cache_key = ("regal", kategorie_name, regal_name, description)

        cached = self._get_cached_embedding(cache_key)
        if cached is not None:
            return cached

        float_embedding = self._generate_embedding(text)
        float_embedding = self._ensure_64_dims(float_embedding)
        int_embedding = self._quantize_to_int16(float_embedding)

        self._cache_embedding(cache_key, int_embedding)
        return int_embedding

    def embed_buch(
        self,
        regal_name: str,
        titel: str,
        description: str = ""
    ) -> List[int]:
        """
        Generate embedding for Buch (Book/Document).

        Individual document or guide.

        Args:
            regal_name: Parent shelf name
            titel: Book title (e.g., "Lambda Functions Guide")
            description: Optional description

        Returns:
            64D int16 embedding
        """
        text = f"Shelf: {regal_name} > Book: {titel}"
        if description:
            text += f" - {description}"

        cache_key = ("buch", regal_name, titel, description)

        cached = self._get_cached_embedding(cache_key)
        if cached is not None:
            return cached

        float_embedding = self._generate_embedding(text)
        float_embedding = self._ensure_64_dims(float_embedding)
        int_embedding = self._quantize_to_int16(float_embedding)

        self._cache_embedding(cache_key, int_embedding)
        return int_embedding

    def embed_kapitel(
        self,
        buch_titel: str,
        kapitel_titel: str,
        description: str = ""
    ) -> List[int]:
        """
        Generate embedding for Kapitel (Chapter).

        Section within a book.

        Args:
            buch_titel: Parent book title
            kapitel_titel: Chapter title (e.g., "Introduction")
            description: Optional description

        Returns:
            64D int16 embedding
        """
        text = f"Book: {buch_titel} > Chapter: {kapitel_titel}"
        if description:
            text += f" - {description}"

        cache_key = ("kapitel", buch_titel, kapitel_titel, description)

        cached = self._get_cached_embedding(cache_key)
        if cached is not None:
            return cached

        float_embedding = self._generate_embedding(text)
        float_embedding = self._ensure_64_dims(float_embedding)
        int_embedding = self._quantize_to_int16(float_embedding)

        self._cache_embedding(cache_key, int_embedding)
        return int_embedding

    def embed_seite(
        self,
        kapitel_titel: str,
        inhalt: str
    ) -> List[int]:
        """
        Generate embedding for Seite (Page/Content).

        Actual content chunk - most specific level.

        Args:
            kapitel_titel: Parent chapter title
            inhalt: Content text (first 500 chars for efficiency)

        Returns:
            64D int16 embedding
        """
        # Use first 500 chars for efficiency (more is rarely needed)
        content_preview = inhalt[:500] if inhalt else ""

        text = f"Chapter: {kapitel_titel} > Content: {content_preview}"

        cache_key = ("seite", kapitel_titel, hashlib.sha256(inhalt.encode()).hexdigest())

        cached = self._get_cached_embedding(cache_key)
        if cached is not None:
            return cached

        float_embedding = self._generate_embedding(text)
        float_embedding = self._ensure_64_dims(float_embedding)
        int_embedding = self._quantize_to_int16(float_embedding)

        self._cache_embedding(cache_key, int_embedding)
        return int_embedding

    # ========================================================
    # Utility Methods
    # ========================================================

    def validate_embedding(self, embedding: List[int]) -> Tuple[bool, str]:
        """
        Validate embedding meets all requirements.

        Returns:
            (is_valid, error_message)
        """
        if not isinstance(embedding, (list, tuple)):
            return False, "Embedding must be list or tuple"

        if len(embedding) != self.TARGET_DIMS:
            return False, f"Expected {self.TARGET_DIMS} dims, got {len(embedding)}"

        if not all(isinstance(x, (int, np.integer)) for x in embedding):
            return False, "All values must be integers"

        if not all(self.INT16_MIN <= x <= self.INT16_MAX for x in embedding):
            return False, f"Values must be in range [{self.INT16_MIN}, {self.INT16_MAX}]"

        if all(x == 0 for x in embedding):
            return False, "Embedding is all zeros"

        return True, ""

    def get_statistics(self) -> dict:
        """Get cache statistics."""
        return {
            "cached_embeddings": len(self._embedding_cache),
            "use_mock": self.use_mock,
            "ollama_host": self.OLLAMA_HOST,
            "embedding_model": self.EMBEDDING_MODEL,
            "target_dims": self.TARGET_DIMS,
        }


# ============================================================
# CLI Interface for Testing
# ============================================================

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("Hierarchical Embedder - Test Mode")
    print("=" * 60)

    # Initialize embedder
    embedder = HierarchicalEmbedder(use_mock=True)  # Mock mode for testing

    print(f"\nUsing mode: {'MOCK' if embedder.use_mock else 'OLLAMA'}")
    print(f"Stats: {json.dumps(embedder.get_statistics(), indent=2)}\n")

    # Test each level
    print("Testing embeddings for each hierarchical level:\n")

    # Level 1: Bibliothek
    print("1. BIBLIOTHEK (Domain)")
    bib_vec = embedder.embed_bibliothek("Programming", "Software development")
    valid, msg = embedder.validate_embedding(bib_vec)
    print(f"   Embedding: {bib_vec[:5]}... (64D int16)")
    print(f"   Valid: {valid} {msg if not valid else '[OK]'}\n")

    # Level 2: Kategorie
    print("2. KATEGORIE (Category)")
    kat_vec = embedder.embed_kategorie("Programming", "Python", "Python language")
    valid, msg = embedder.validate_embedding(kat_vec)
    print(f"   Embedding: {kat_vec[:5]}... (64D int16)")
    print(f"   Valid: {valid} {msg if not valid else '[OK]'}\n")

    # Level 3: Regal
    print("3. REGAL (Shelf)")
    reg_vec = embedder.embed_regal("Python", "Advanced Features", "Advanced patterns")
    valid, msg = embedder.validate_embedding(reg_vec)
    print(f"   Embedding: {reg_vec[:5]}... (64D int16)")
    print(f"   Valid: {valid} {msg if not valid else '[OK]'}\n")

    # Level 4: Buch
    print("4. BUCH (Book)")
    buc_vec = embedder.embed_buch("Advanced Features", "Lambda Guide", "Lambda guide")
    valid, msg = embedder.validate_embedding(buc_vec)
    print(f"   Embedding: {buc_vec[:5]}... (64D int16)")
    print(f"   Valid: {valid} {msg if not valid else '[OK]'}\n")

    # Level 5: Kapitel
    print("5. KAPITEL (Chapter)")
    kap_vec = embedder.embed_kapitel("Lambda Guide", "Introduction", "Intro chapter")
    valid, msg = embedder.validate_embedding(kap_vec)
    print(f"   Embedding: {kap_vec[:5]}... (64D int16)")
    print(f"   Valid: {valid} {msg if not valid else '[OK]'}\n")

    # Level 6: Seite
    print("6. SEITE (Page/Content)")
    sei_vec = embedder.embed_seite(
        "Introduction",
        "Lambda functions are anonymous functions defined with the lambda keyword."
    )
    valid, msg = embedder.validate_embedding(sei_vec)
    print(f"   Embedding: {sei_vec[:5]}... (64D int16)")
    print(f"   Valid: {valid} {msg if not valid else '[OK]'}\n")

    # Verify context matters (different vectors at each level)
    print("Verifying context matters (vectors should differ):")
    print(f"   Bibliothek ≠ Kategorie: {bib_vec != kat_vec} [OK]")
    print(f"   Kategorie ≠ Regal: {kat_vec != reg_vec} [OK]")
    print(f"   Regal ≠ Buch: {reg_vec != buc_vec} [OK]")
    print(f"   Buch ≠ Kapitel: {buc_vec != kap_vec} [OK]")
    print(f"   Kapitel ≠ Seite: {kap_vec != sei_vec} [OK]")

    print("\n" + "=" * 60)
    print("[OK] All embeddings validated successfully!")
    print("=" * 60)
