"""
Hierarchical Search Engine MVP
==============================

6-Level Cascade Filtering Search

Implements the full cascade filtering algorithm:
1. Level 1 (Bibliothek):  Find best library/domain
2. Level 2 (Kategorie):   Find best categories IN that library
3. Level 3 (Regal):       Find best shelves IN those categories
4. Level 4 (Buch):        Find best books IN those shelves
5. Level 5 (Kapitel):     Find best chapters IN those books
6. Level 6 (Seite):       Find top-N pages IN those chapters

Performance: 10M items reduced to ~100 items scanned → 100x+ faster than flat search!

Architecture:
- Each level filters search space for next level
- Similarity scores guide filtering (Top-K from each level)
- Database indices enable fast lookups
"""

import os
import psycopg2
import psycopg2.extras
import numpy as np
import time
import json
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Import embedder
import sys
sys.path.insert(0, os.path.dirname(__file__))
from hierarchical_embedder import HierarchicalEmbedder


# ============================================================
# Data Classes
# ============================================================

@dataclass
class SearchResult:
    """Single search result item."""
    level: str
    id: int
    name: str
    content: str
    similarity: float
    path: Dict  # Full path from root to this node


@dataclass
class CascadeSearchResponse:
    """Complete search response with path and results."""
    query: str
    query_id: str
    duration_ms: int

    # Cascade path (6 levels)
    bibliothek: Optional[Dict]
    kategorie: Optional[Dict]
    regal: Optional[Dict]
    buch: Optional[Dict]
    kapitel: Optional[Dict]

    # Final results
    seiten: List[Dict]
    seiten_count: int

    # Metadata
    timestamp: str


# ============================================================
# Hierarchical Search Engine
# ============================================================

class HierarchicalSearchMVP:
    """
    6-Level cascade search engine.

    Levels:
    1. Bibliothek (Library) - top domain
    2. Kategorie (Category) - sub-domain
    3. Regal (Shelf) - collection
    4. Buch (Book) - document
    5. Kapitel (Chapter) - section
    6. Seite (Page) - content chunks
    """

    # Search parameters (cascade filtering at each level)
    TOP_K_BIBLIOTHEK = 1
    TOP_K_KATEGORIE = 3
    TOP_K_REGAL = 5
    TOP_K_BUCH = 5
    TOP_K_KAPITEL = 10
    TOP_K_SEITE = 10
    MAX_PAGES_BEFORE_FILTER = 100

    def __init__(
        self,
        db_host: str = "localhost",
        db_port: int = 5433,
        db_name: str = "bruce_knowledge",
        db_user: str = "bruce",
        db_password: str = "dev_secret",
        use_mock_embeddings: bool = False,
    ):
        """
        Initialize search engine.

        Args:
            db_host: PostgreSQL host
            db_port: PostgreSQL port
            db_name: Database name
            db_user: Database user
            db_password: Database password
            use_mock_embeddings: Use mock mode (for testing without Ollama)
        """
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password

        # Connect to database
        self.conn = self._connect_db()
        self.embedder = HierarchicalEmbedder(use_mock=use_mock_embeddings)

        print(f"[OK] Search engine initialized")
        print(f"     Database: {db_host}:{db_port}/{db_name}")
        print(f"     Embedder: {'Mock' if use_mock_embeddings else 'Ollama'}")

    def _connect_db(self) -> psycopg2.extensions.connection:
        """Connect to PostgreSQL database."""
        try:
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password,
            )
            print(f"[OK] PostgreSQL connected")
            return conn
        except Exception as e:
            raise ConnectionError(f"Failed to connect to PostgreSQL: {e}")

    def _cosine_similarity(self, vec_a: List[int], vec_b: List[int]) -> float:
        """
        Calculate cosine similarity between two int16 vectors.

        Args:
            vec_a: First vector (int16)
            vec_b: Second vector (int16)

        Returns:
            Similarity score in range [0, 1]
        """
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)

        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot / (norm_a * norm_b + 1e-8))

    # ========================================================
    # Level 1: BIBLIOTHEK
    # ========================================================

    def _search_bibliotheken(self, query_embedding: List[int]) -> Dict:
        """
        Find best Bibliothek for query.

        Returns:
            Best matching bibliothek with similarity score
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        query_sql = """
            SELECT b.id, b.name, b.beschreibung, v.dims
            FROM bibliotheken b
            JOIN vektoren v ON b.vektor_id = v.id
            ORDER BY b.id
        """

        cursor.execute(query_sql)
        rows = cursor.fetchall()

        best_match = None
        best_similarity = -1

        for row in rows:
            dims_str = row['dims']
            # Convert PostgreSQL array format to list
            if isinstance(dims_str, str):
                dims = [int(x) for x in dims_str.strip('{}').split(',')]
            else:
                dims = list(dims_str)

            similarity = self._cosine_similarity(query_embedding, dims)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = {
                    'id': row['id'],
                    'name': row['name'],
                    'beschreibung': row['beschreibung'],
                    'similarity': similarity,
                }

        cursor.close()
        return best_match

    # ========================================================
    # Level 2: KATEGORIE
    # ========================================================

    def _search_kategorien(
        self,
        bibliothek_id: int,
        query_embedding: List[int],
        top_k: int = TOP_K_KATEGORIE
    ) -> List[Dict]:
        """
        Find best Kategorien IN a specific Bibliothek.

        Cascade filter: only search categories belonging to selected bibliothek.

        Args:
            bibliothek_id: Parent bibliothek ID
            query_embedding: Query embedding
            top_k: Number of results to return

        Returns:
            List of top-K matching categories
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        query_sql = """
            SELECT k.id, k.name, k.beschreibung, v.dims
            FROM kategorien k
            JOIN vektoren v ON k.vektor_id = v.id
            WHERE k.bibliothek_id = %s
            ORDER BY k.id
        """

        cursor.execute(query_sql, (bibliothek_id,))
        rows = cursor.fetchall()

        matches = []

        for row in rows:
            dims_str = row['dims']
            if isinstance(dims_str, str):
                dims = [int(x) for x in dims_str.strip('{}').split(',')]
            else:
                dims = list(dims_str)

            similarity = self._cosine_similarity(query_embedding, dims)

            matches.append({
                'id': row['id'],
                'name': row['name'],
                'beschreibung': row['beschreibung'],
                'similarity': similarity,
            })

        # Sort by similarity and take top-K
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        cursor.close()

        return matches[:top_k]

    # ========================================================
    # Level 3: REGAL
    # ========================================================

    def _search_regale(
        self,
        kategorie_ids: List[int],
        query_embedding: List[int],
        top_k: int = TOP_K_REGAL
    ) -> List[Dict]:
        """
        Find best Regale IN specific Kategorien.

        Cascade filter: only search shelves belonging to selected categories.

        Args:
            kategorie_ids: List of parent kategorie IDs
            query_embedding: Query embedding
            top_k: Number of results to return

        Returns:
            List of top-K matching shelves
        """
        if not kategorie_ids:
            return []

        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Build placeholders for IN clause
        placeholders = ','.join(['%s'] * len(kategorie_ids))

        query_sql = f"""
            SELECT r.id, r.name, r.beschreibung, v.dims
            FROM regale r
            JOIN vektoren v ON r.vektor_id = v.id
            WHERE r.kategorie_id IN ({placeholders})
            ORDER BY r.id
        """

        cursor.execute(query_sql, kategorie_ids)
        rows = cursor.fetchall()

        matches = []

        for row in rows:
            dims_str = row['dims']
            if isinstance(dims_str, str):
                dims = [int(x) for x in dims_str.strip('{}').split(',')]
            else:
                dims = list(dims_str)

            similarity = self._cosine_similarity(query_embedding, dims)

            matches.append({
                'id': row['id'],
                'name': row['name'],
                'beschreibung': row['beschreibung'],
                'similarity': similarity,
            })

        # Sort by similarity and take top-K
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        cursor.close()

        return matches[:top_k]

    # ========================================================
    # Level 4: BUCH
    # ========================================================

    def _search_buecher(
        self,
        regal_ids: List[int],
        query_embedding: List[int],
        top_k: int = TOP_K_BUCH
    ) -> List[Dict]:
        """
        Find best Buecher IN specific Regale.

        Cascade filter: only search books belonging to selected shelves.

        Args:
            regal_ids: List of parent regal IDs
            query_embedding: Query embedding
            top_k: Number of results to return

        Returns:
            List of top-K matching books
        """
        if not regal_ids:
            return []

        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Build placeholders for IN clause
        placeholders = ','.join(['%s'] * len(regal_ids))

        query_sql = f"""
            SELECT b.id, b.titel, b.beschreibung, v.dims
            FROM buecher b
            JOIN vektoren v ON b.vektor_id = v.id
            WHERE b.regal_id IN ({placeholders})
            ORDER BY b.id
        """

        cursor.execute(query_sql, regal_ids)
        rows = cursor.fetchall()

        matches = []

        for row in rows:
            dims_str = row['dims']
            if isinstance(dims_str, str):
                dims = [int(x) for x in dims_str.strip('{}').split(',')]
            else:
                dims = list(dims_str)

            similarity = self._cosine_similarity(query_embedding, dims)

            matches.append({
                'id': row['id'],
                'titel': row['titel'],
                'beschreibung': row['beschreibung'],
                'similarity': similarity,
            })

        # Sort by similarity and take top-K
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        cursor.close()

        return matches[:top_k]

    # ========================================================
    # Level 5: KAPITEL
    # ========================================================

    def _search_kapitel(
        self,
        buch_ids: List[int],
        query_embedding: List[int],
        top_k: int = TOP_K_KAPITEL
    ) -> List[Dict]:
        """
        Find best Kapitel IN specific Buecher.

        Cascade filter: only search chapters belonging to selected books.

        Args:
            buch_ids: List of parent buch IDs
            query_embedding: Query embedding
            top_k: Number of results to return

        Returns:
            List of top-K matching chapters
        """
        if not buch_ids:
            return []

        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Build placeholders for IN clause
        placeholders = ','.join(['%s'] * len(buch_ids))

        query_sql = f"""
            SELECT k.id, k.titel, k.beschreibung, v.dims
            FROM kapitel k
            JOIN vektoren v ON k.vektor_id = v.id
            WHERE k.buch_id IN ({placeholders})
            ORDER BY k.id
        """

        cursor.execute(query_sql, buch_ids)
        rows = cursor.fetchall()

        matches = []

        for row in rows:
            dims_str = row['dims']
            if isinstance(dims_str, str):
                dims = [int(x) for x in dims_str.strip('{}').split(',')]
            else:
                dims = list(dims_str)

            similarity = self._cosine_similarity(query_embedding, dims)

            matches.append({
                'id': row['id'],
                'titel': row['titel'],
                'beschreibung': row['beschreibung'],
                'similarity': similarity,
            })

        # Sort by similarity and take top-K
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        cursor.close()

        return matches[:top_k]

    # ========================================================
    # Level 6: SEITE (via JOINs)
    # ========================================================

    def _search_seiten(
        self,
        kapitel_ids: List[int],
        query_embedding: List[int],
        top_k: int = TOP_K_SEITE
    ) -> List[Dict]:
        """
        Find best Seiten IN specific Kapitel.

        Cascade filter: joins through full hierarchy to find all pages
        that belong to selected chapters.

        Args:
            kapitel_ids: List of parent kapitel IDs
            query_embedding: Query embedding
            top_k: Number of results to return

        Returns:
            List of top-K matching pages
        """
        if not kapitel_ids:
            return []

        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Build placeholders for IN clause
        placeholders = ','.join(['%s'] * len(kapitel_ids))

        query_sql = f"""
            SELECT DISTINCT s.id, s.inhalt, v.dims,
                   b.name as bib_name,
                   k.name as kat_name,
                   r.name as regal_name,
                   bu.titel as buch_titel,
                   kap.titel as kap_titel
            FROM seiten s
            JOIN vektoren v ON s.vektor_id = v.id
            JOIN kapitel kap ON s.kapitel_id = kap.id
            JOIN buecher bu ON kap.buch_id = bu.id
            JOIN regale r ON bu.regal_id = r.id
            JOIN kategorien k ON r.kategorie_id = k.id
            JOIN bibliotheken b ON k.bibliothek_id = b.id
            WHERE s.kapitel_id IN ({placeholders})
            LIMIT {self.MAX_PAGES_BEFORE_FILTER}
        """

        cursor.execute(query_sql, kapitel_ids)
        rows = cursor.fetchall()

        matches = []

        for row in rows:
            dims_str = row['dims']
            if isinstance(dims_str, str):
                dims = [int(x) for x in dims_str.strip('{}').split(',')]
            else:
                dims = list(dims_str)

            similarity = self._cosine_similarity(query_embedding, dims)

            matches.append({
                'id': row['id'],
                'inhalt': row['inhalt'],
                'similarity': similarity,
                'path': {
                    'bibliothek': row['bib_name'],
                    'kategorie': row['kat_name'],
                    'regal': row['regal_name'],
                    'buch': row['buch_titel'],
                    'kapitel': row['kap_titel'],
                }
            })

        # Sort by similarity and take top-K
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        cursor.close()

        return matches[:top_k]

    # ========================================================
    # Main Search Method
    # ========================================================

    def search(self, query_text: str) -> Dict:
        """
        Execute 6-level cascade search.

        Flow:
        1. Embed query at Bibliothek level -> find best library
        2. Embed query at Kategorie level (with library context) -> find best categories
        3. Embed query at Regal level (with category context) -> find best shelves
        4. Embed query at Buch level (with shelf context) -> find best books
        5. Embed query at Kapitel level (with book context) -> find best chapters
        6. Embed query at Seite level (with chapter context) -> find top pages

        Args:
            query_text: User search query

        Returns:
            Search response with path and results
        """
        start_time = time.time()

        print(f"\n{'='*60}")
        print(f"Cascade Search: {query_text[:50]}...")
        print(f"{'='*60}")

        # ============================================
        # LEVEL 1: BIBLIOTHEK
        # ============================================
        print("\nLevel 1: BIBLIOTHEK")
        bib_vec = self.embedder.embed_bibliothek(query_text)
        bib_match = self._search_bibliotheken(bib_vec)

        if not bib_match:
            print("  [ERR] No bibliotheken found")
            return self._error_response(query_text, "No bibliotheken found")

        print(f"  Found: {bib_match['name']} (sim={bib_match['similarity']:.3f})")

        # ============================================
        # LEVEL 2: KATEGORIE
        # ============================================
        print(f"\nLevel 2: KATEGORIE (filtered by {bib_match['name']})")
        kat_vec = self.embedder.embed_kategorie(
            bib_match['name'],
            query_text
        )

        kat_matches = self._search_kategorien(
            bib_match['id'],
            kat_vec,
            top_k=self.TOP_K_KATEGORIE
        )

        if not kat_matches:
            print("  [ERR] No kategorien found")
            return self._error_response(query_text, "No kategorien found")

        kat_ids = [k['id'] for k in kat_matches]
        print(f"  Found {len(kat_matches)} kategorien:")
        for k in kat_matches:
            print(f"    - {k['name']} (sim={k['similarity']:.3f})")

        # ============================================
        # LEVEL 3: REGAL
        # ============================================
        print(f"\nLevel 3: REGAL (filtered by {len(kat_ids)} kategorien)")
        # Use first matching category for context
        context_kat = kat_matches[0]['name'] if kat_matches else query_text
        regal_vec = self.embedder.embed_regal(
            context_kat,
            query_text
        )

        regal_matches = self._search_regale(
            kat_ids,
            regal_vec,
            top_k=self.TOP_K_REGAL
        )

        if not regal_matches:
            print("  [WARN] No regale found")
            regal_matches = []
            regal_ids = []
        else:
            regal_ids = [r['id'] for r in regal_matches]
            print(f"  Found {len(regal_matches)} regale:")
            for r in regal_matches:
                print(f"    - {r['name']} (sim={r['similarity']:.3f})")

        # ============================================
        # LEVEL 4: BUCH
        # ============================================
        if not regal_matches:
            print("\nLevel 4: BUCH (filtered by 0 regale) - SKIPPED")
            buch_matches = []
        else:
            print(f"\nLevel 4: BUCH (filtered by {len(regal_matches)} regale)")
            # Use first matching regal for context
            context_regal = regal_matches[0]['name'] if regal_matches else query_text
            buch_vec = self.embedder.embed_buch(
                context_regal,
                query_text
            )

            buch_matches = self._search_buecher(
                regal_ids,
                buch_vec,
                top_k=self.TOP_K_BUCH
            )

            if not buch_matches:
                print("  [WARN] No buecher found")
                buch_matches = []
                buch_ids = []
            else:
                buch_ids = [b['id'] for b in buch_matches]
                print(f"  Found {len(buch_matches)} buecher:")
                for b in buch_matches:
                    print(f"    - {b['titel']} (sim={b['similarity']:.3f})")

        # ============================================
        # LEVEL 5: KAPITEL
        # ============================================
        if not buch_matches:
            print("\nLevel 5: KAPITEL (filtered by 0 buecher) - SKIPPED")
            kapitel_matches = []
        else:
            print(f"\nLevel 5: KAPITEL (filtered by {len(buch_matches)} buecher)")
            # Use first matching buch for context
            context_buch = buch_matches[0]['titel'] if buch_matches else query_text
            kapitel_vec = self.embedder.embed_kapitel(
                context_buch,
                query_text
            )

            kapitel_matches = self._search_kapitel(
                buch_ids,
                kapitel_vec,
                top_k=self.TOP_K_KAPITEL
            )

            if not kapitel_matches:
                print("  [WARN] No kapitel found")
                kapitel_matches = []
                kapitel_ids = []
            else:
                kapitel_ids = [k['id'] for k in kapitel_matches]
                print(f"  Found {len(kapitel_matches)} kapitel:")
                for k in kapitel_matches[:3]:
                    print(f"    - {k['titel']} (sim={k['similarity']:.3f})")

        # ============================================
        # LEVEL 6: SEITE
        # ============================================
        if not kapitel_matches:
            print("\nLevel 6: SEITE (filtered by 0 kapitel) - SKIPPED")
            seiten = []
        else:
            print(f"\nLevel 6: SEITE (filtered by {len(kapitel_matches)} kapitel)")
            sei_vec = self.embedder.embed_seite(query_text, query_text[:200])

            seiten = self._search_seiten(kapitel_ids, sei_vec, top_k=self.TOP_K_SEITE)

            if not seiten:
                print("  [WARN] No seiten found")
                seiten = []
            else:
                print(f"  Found {len(seiten)} seiten:")
                for s in seiten[:3]:
                    content_preview = s['inhalt'][:60].replace('\n', ' ')
                    print(f"    - {content_preview}... (sim={s['similarity']:.3f})")

        # ============================================
        # COMPILE RESPONSE
        # ============================================
        duration_ms = int((time.time() - start_time) * 1000)

        response = {
            'query': query_text,
            'query_id': f"search_{int(start_time)}",
            'duration_ms': duration_ms,
            'bibliothek': {
                'id': bib_match['id'],
                'name': bib_match['name'],
                'similarity': float(bib_match['similarity']),
            },
            'kategorien': [
                {
                    'id': k['id'],
                    'name': k['name'],
                    'similarity': float(k['similarity']),
                }
                for k in kat_matches
            ],
            'regale': [
                {
                    'id': r['id'],
                    'name': r['name'],
                    'similarity': float(r['similarity']),
                }
                for r in regal_matches
            ],
            'buecher': [
                {
                    'id': b['id'],
                    'titel': b['titel'],
                    'similarity': float(b['similarity']),
                }
                for b in buch_matches
            ],
            'kapitel': [
                {
                    'id': k['id'],
                    'titel': k['titel'],
                    'similarity': float(k['similarity']),
                }
                for k in kapitel_matches
            ],
            'seiten': seiten,
            'seiten_count': len(seiten),
            'timestamp': datetime.now().isoformat(),
        }

        print(f"\n[OK] Search completed in {duration_ms}ms")
        print(f"{'='*60}\n")

        return response

    def _error_response(self, query: str, error: str) -> Dict:
        """Generate error response."""
        return {
            'query': query,
            'error': error,
            'timestamp': datetime.now().isoformat(),
        }


# ============================================================
# CLI Test
# ============================================================

if __name__ == "__main__":
    import sys

    print("Hierarchical Search Engine MVP - Test Mode")
    print("=" * 60)

    # Create search engine
    try:
        search = HierarchicalSearchMVP(
            db_host="localhost",
            db_port=5433,
            use_mock_embeddings=False  # Use real Ollama
        )
    except Exception as e:
        print(f"[ERR] {e}")
        print("\nFalling back to mock mode...")
        search = HierarchicalSearchMVP(
            db_host="localhost",
            db_port=5433,
            use_mock_embeddings=True
        )

    print()

    # Test searches
    test_queries = [
        "Python Lambda Functions",
        "Advanced Programming Patterns",
        "Function Definition",
    ]

    for query in test_queries:
        results = search.search(query)

        if 'error' in results:
            print(f"Error: {results['error']}")
        else:
            print(f"\nResults for: {query}")
            print(f"  Bibliothek: {results['bibliothek']['name']}")
            print(f"  Kategorien: {len(results['kategorien'])}")
            print(f"  Regale: {len(results.get('regale', []))}")
            print(f"  Buecher: {len(results.get('buecher', []))}")
            print(f"  Kapitel: {len(results.get('kapitel', []))}")
            print(f"  Seiten: {len(results['seiten'])}")

            if results['seiten']:
                print(f"\n  Top result:")
                top = results['seiten'][0]
                print(f"    {top['inhalt'][:100]}...")

        print()
