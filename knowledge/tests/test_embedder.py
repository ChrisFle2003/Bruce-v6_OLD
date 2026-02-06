"""
Unit Tests for Hierarchical Embedder
=====================================

Tests embedding generation, validation, and context awareness.
"""

import sys
import os

# Add services directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))

from hierarchical_embedder import HierarchicalEmbedder


class TestHierarchicalEmbedder:
    """Test suite for hierarchical embedding service."""

    @classmethod
    def setup_class(cls):
        """Setup test fixtures."""
        print("\n" + "=" * 60)
        print("Hierarchical Embedder Test Suite")
        print("=" * 60 + "\n")

        # Use mock mode for deterministic testing
        cls.embedder = HierarchicalEmbedder(use_mock=True)

    def test_embedding_dimensions(self):
        """Test that all embeddings have exactly 64 dimensions."""
        print("Test 1: Embedding Dimensions")

        embeddings = [
            self.embedder.embed_bibliothek("Test", ""),
            self.embedder.embed_kategorie("Test", "Sub", ""),
            self.embedder.embed_regal("Test", "Shelf", ""),
            self.embedder.embed_buch("Test", "Book", ""),
            self.embedder.embed_kapitel("Test", "Ch", ""),
            self.embedder.embed_seite("Test", "Content"),
        ]

        for i, emb in enumerate(embeddings):
            assert len(emb) == 64, f"Embedding {i} has {len(emb)} dims, expected 64"
            print(f"  [OK] Embedding {i+1}: {len(emb)} dimensions")

    def test_embedding_type(self):
        """Test that embeddings are int16 arrays."""
        print("\nTest 2: Embedding Data Type")

        embedding = self.embedder.embed_bibliothek("Test")

        # Check all values are integers
        for val in embedding:
            assert isinstance(val, (int, type(0))), f"Value {val} is not integer"

        # Check range
        assert all(-32767 <= x <= 32767 for x in embedding), "Values out of int16 range"

        print(f"  [OK] All {len(embedding)} values are valid int16")

    def test_embedding_not_empty(self):
        """Test that embeddings are not all zeros."""
        print("\nTest 3: Non-Zero Embeddings")

        embedding = self.embedder.embed_bibliothek("Programming")

        assert not all(x == 0 for x in embedding), "Embedding is all zeros"
        non_zero_count = sum(1 for x in embedding if x != 0)

        print(f"  ✓ Embedding has {non_zero_count}/{len(embedding)} non-zero values")

    def test_context_awareness(self):
        """Test that embeddings differ based on context."""
        print("\nTest 4: Context Awareness")

        # Same name but different contexts should produce different embeddings
        emb1 = self.embedder.embed_kategorie("Programming", "Python")
        emb2 = self.embedder.embed_kategorie("Science", "Python")

        assert emb1 != emb2, "Context doesn't affect embedding"
        print(f"  ✓ Different parent context produces different embeddings")

        # Same full path should produce same embedding (caching)
        emb3 = self.embedder.embed_kategorie("Programming", "Python")
        assert emb1 == emb3, "Same input doesn't produce same output (cache failed)"
        print(f"  ✓ Same input produces same output (deterministic/cached)")

    def test_hierarchical_differences(self):
        """Test that different levels produce different embeddings."""
        print("\nTest 5: Hierarchical Level Differences")

        # Same content at different levels should differ
        bib = self.embedder.embed_bibliothek("Python")
        kat = self.embedder.embed_kategorie("Root", "Python")
        reg = self.embedder.embed_regal("Python", "Python")

        assert bib != kat, "Level 1 and 2 should differ"
        assert kat != reg, "Level 2 and 3 should differ"
        assert bib != reg, "Level 1 and 3 should differ"

        print(f"  ✓ Level 1 ≠ Level 2 ≠ Level 3 (all different)")

    def test_full_hierarchy_path(self):
        """Test embedding a complete hierarchical path."""
        print("\nTest 6: Full Hierarchical Path")

        # Build complete path
        embeddings = {
            'bib': self.embedder.embed_bibliothek("Programming", "Software"),
            'kat': self.embedder.embed_kategorie("Programming", "Python", "Language"),
            'reg': self.embedder.embed_regal("Python", "Advanced", "Patterns"),
            'buc': self.embedder.embed_buch("Advanced", "Lambda Guide", "Guide"),
            'kap': self.embedder.embed_kapitel("Lambda Guide", "Intro", "Chapter 1"),
            'sei': self.embedder.embed_seite("Intro", "Lambda is an anon function"),
        }

        # Verify all are valid
        for level, emb in embeddings.items():
            valid, msg = self.embedder.validate_embedding(emb)
            assert valid, f"Level {level} invalid: {msg}"
            print(f"  ✓ {level}: {len(emb)}D int16 valid")

    def test_validation_function(self):
        """Test embedding validation function."""
        print("\nTest 7: Validation Function")

        # Valid embedding
        valid_emb = self.embedder.embed_bibliothek("Test")
        is_valid, msg = self.embedder.validate_embedding(valid_emb)
        assert is_valid, f"Valid embedding marked invalid: {msg}"
        print(f"  ✓ Valid embedding passes validation")

        # Invalid: wrong length
        invalid_len = valid_emb[:-1]  # Remove one element
        is_valid, msg = self.embedder.validate_embedding(invalid_len)
        assert not is_valid, "Wrong length not caught"
        print(f"  ✓ Wrong length caught: {msg}")

        # Invalid: wrong type
        invalid_type = [float(x) for x in valid_emb]  # Convert to float
        is_valid, msg = self.embedder.validate_embedding(invalid_type)
        assert not is_valid, "Wrong type not caught"
        print(f"  ✓ Wrong type caught: {msg}")

        # Invalid: all zeros
        all_zeros = [0] * 64
        is_valid, msg = self.embedder.validate_embedding(all_zeros)
        assert not is_valid, "All-zero embedding not caught"
        print(f"  ✓ All-zero embedding caught: {msg}")

    def test_caching(self):
        """Test that embeddings are cached correctly."""
        print("\nTest 8: Caching")

        # Clear cache by creating new embedder
        embedder = HierarchicalEmbedder(use_mock=True)

        stats_before = embedder.get_statistics()
        initial_cache = stats_before['cached_embeddings']

        # Generate embedding
        embedder.embed_bibliothek("Test1", "Desc1")
        stats_after = embedder.get_statistics()
        assert stats_after['cached_embeddings'] == initial_cache + 1
        print(f"  ✓ Cache increased from {initial_cache} to {stats_after['cached_embeddings']}")

        # Generate same embedding (should use cache)
        embedder.embed_bibliothek("Test1", "Desc1")
        stats_again = embedder.get_statistics()
        assert stats_again['cached_embeddings'] == stats_after['cached_embeddings']
        print(f"  ✓ Cache size unchanged on duplicate (cache hit)")

        # Generate different embedding
        embedder.embed_bibliothek("Test2", "Desc2")
        stats_new = embedder.get_statistics()
        assert stats_new['cached_embeddings'] == stats_again['cached_embeddings'] + 1
        print(f"  ✓ Cache increased for new embedding")

    def test_deterministic_mock_mode(self):
        """Test that mock mode is deterministic."""
        print("\nTest 9: Deterministic Mock Mode")

        embedder1 = HierarchicalEmbedder(use_mock=True)
        embedder2 = HierarchicalEmbedder(use_mock=True)

        # Same input should produce same output
        emb1a = embedder1.embed_bibliothek("TestDet", "Description")
        emb2a = embedder2.embed_bibliothek("TestDet", "Description")

        assert emb1a == emb2a, "Mock mode not deterministic"
        print(f"  ✓ Different instances produce same embedding")

        # Different input should produce different output
        emb1b = embedder1.embed_bibliothek("TestDet2", "Description")
        assert emb1a != emb1b, "Different input produces same embedding"
        print(f"  ✓ Different input produces different embedding")

    def test_statistics(self):
        """Test statistics reporting."""
        print("\nTest 10: Statistics")

        embedder = HierarchicalEmbedder(use_mock=True)
        stats = embedder.get_statistics()

        assert 'cached_embeddings' in stats
        assert 'use_mock' in stats
        assert 'ollama_host' in stats
        assert 'embedding_model' in stats
        assert 'target_dims' in stats

        assert stats['use_mock'] == True
        assert stats['target_dims'] == 64

        print(f"  ✓ Statistics available:")
        for key, val in stats.items():
            print(f"    - {key}: {val}")


def run_tests():
    """Run all tests."""
    test_suite = TestHierarchicalEmbedder()
    test_suite.setup_class()

    tests = [
        test_suite.test_embedding_dimensions,
        test_suite.test_embedding_type,
        test_suite.test_embedding_not_empty,
        test_suite.test_context_awareness,
        test_suite.test_hierarchical_differences,
        test_suite.test_full_hierarchy_path,
        test_suite.test_validation_function,
        test_suite.test_caching,
        test_suite.test_deterministic_mock_mode,
        test_suite.test_statistics,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
