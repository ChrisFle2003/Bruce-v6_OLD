# Bruce Hierarchical Knowledge System - Implementation Plan

## Executive Summary

Dieser Plan beschreibt die **technische Implementierung** des hierarchischen Bibliotheks-Systems. Statt "flacher Vektor-Suppe" bauen wir eine **navigierbare Wissens-Taxonomie** mit 6 Hierarchie-Ebenen, wo jede Ebene sowohl als ID (deterministisch) als auch als Vektor (semantisch) existiert.

**Kern-Innovation:** Cascade Filtering - jede Ebene reduziert Suchraum für die nächste um Faktor 10-100.

---

## Database Schema (PostgreSQL + pgvector)

### Migration File: `knowledge/migrations/002_hierarchical_library_schema.sql`

```sql
-- ============================================
-- BRUCE HIERARCHICAL KNOWLEDGE LIBRARY
-- Schema Version: 2.0
-- Author: [Your Name]
-- Date: 2025-02-05
-- ============================================

-- Enable Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;  -- pgvector
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- ============================================
-- EBENE 0: VEKTOREN (Shared Pool)
-- ============================================

CREATE TABLE vektoren (
    id SERIAL PRIMARY KEY,
    
    -- Die 64-dimensionalen Koordinaten (int16 für Byte-Efficiency)
    dims SMALLINT[64] NOT NULL,
    
    -- Alternativ: Falls du doch float brauchst
    -- embedding vector(64),
    
    -- Metadaten
    ebene TEXT NOT NULL,  -- "bibliothek", "kategorie", "regal", "buch", "kapitel", "seite"
    source TEXT NOT NULL, -- "ollama:nomic-embed-text:v1.5:sha256:abc123..."
    erstellt_am TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_dims_length CHECK (array_length(dims, 1) = 64),
    CONSTRAINT valid_ebene CHECK (ebene IN ('bibliothek', 'kategorie', 'regal', 'buch', 'kapitel', 'seite'))
);

-- GIN Index für int16[] Arrays (schnellste Option für unsere Zwecke)
CREATE INDEX idx_vektoren_dims ON vektoren USING GIN (dims);

-- Index nach Ebene (für Level-spezifische Queries)
CREATE INDEX idx_vektoren_ebene ON vektoren (ebene);

-- Falls du pgvector nutzt (für float embeddings):
-- CREATE INDEX idx_vektoren_embedding ON vektoren USING hnsw (embedding vector_cosine_ops);

-- ============================================
-- EBENE 1: BIBLIOTHEKEN (Top-Level Domains)
-- ============================================

CREATE TABLE bibliotheken (
    id SERIAL PRIMARY KEY,
    
    -- Name (human-readable)
    name TEXT NOT NULL UNIQUE,
    beschreibung TEXT,
    
    -- Vektor-Referenz
    vektor_id INT REFERENCES vektoren(id) ON DELETE SET NULL,
    
    -- Metadaten
    metadata JSONB DEFAULT '{}',
    
    -- Lifecycle
    erstellt_am TIMESTAMPTZ DEFAULT NOW(),
    aktualisiert_am TIMESTAMPTZ DEFAULT NOW(),
    
    -- Multi-Tenant (optional)
    tenant_id UUID DEFAULT NULL
);

CREATE INDEX idx_bibliotheken_name ON bibliotheken (name);
CREATE INDEX idx_bibliotheken_tenant ON bibliotheken (tenant_id) WHERE tenant_id IS NOT NULL;

-- ============================================
-- EBENE 2: KATEGORIEN (Sub-Domains)
-- ============================================

CREATE TABLE kategorien (
    id SERIAL PRIMARY KEY,
    
    -- Hierarchie-Link
    bibliothek_id INT NOT NULL REFERENCES bibliotheken(id) ON DELETE CASCADE,
    
    -- Name
    name TEXT NOT NULL,
    beschreibung TEXT,
    
    -- Vektor-Referenz
    vektor_id INT REFERENCES vektoren(id) ON DELETE SET NULL,
    
    -- Metadaten
    metadata JSONB DEFAULT '{}',
    
    -- Lifecycle
    erstellt_am TIMESTAMPTZ DEFAULT NOW(),
    aktualisiert_am TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_kategorie_per_bib UNIQUE (bibliothek_id, name)
);

CREATE INDEX idx_kategorien_bibliothek ON kategorien (bibliothek_id);
CREATE INDEX idx_kategorien_name ON kategorien (name);

-- ============================================
-- EBENE 3: REGALE (Topic Clusters)
-- ============================================

CREATE TABLE regale (
    id SERIAL PRIMARY KEY,
    
    -- Hierarchie-Link
    kategorie_id INT NOT NULL REFERENCES kategorien(id) ON DELETE CASCADE,
    
    -- Name
    name TEXT NOT NULL,
    beschreibung TEXT,
    
    -- Vektor-Referenz
    vektor_id INT REFERENCES vektoren(id) ON DELETE SET NULL,
    
    -- Metadaten
    metadata JSONB DEFAULT '{}',
    
    -- Lifecycle
    erstellt_am TIMESTAMPTZ DEFAULT NOW(),
    aktualisiert_am TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_regal_per_kategorie UNIQUE (kategorie_id, name)
);

CREATE INDEX idx_regale_kategorie ON regale (kategorie_id);

-- ============================================
-- EBENE 4: BÜCHER (Documents)
-- ============================================

CREATE TABLE buecher (
    id SERIAL PRIMARY KEY,
    
    -- Hierarchie-Link
    regal_id INT NOT NULL REFERENCES regale(id) ON DELETE CASCADE,
    
    -- Metadaten
    titel TEXT NOT NULL,
    autor TEXT,
    version TEXT DEFAULT '1.0',
    
    -- Vektor-Referenz
    vektor_id INT REFERENCES vektoren(id) ON DELETE SET NULL,
    
    -- Größe (für Budget-Kontrolle)
    groesse_mb FLOAT NOT NULL DEFAULT 0,
    
    -- Content Hash (für Deduplication)
    content_hash BYTEA UNIQUE,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Lifecycle
    erstellt_am TIMESTAMPTZ DEFAULT NOW(),
    aktualisiert_am TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_groesse CHECK (groesse_mb >= 0 AND groesse_mb <= 1024)  -- Max 1GB pro Buch
);

CREATE INDEX idx_buecher_regal ON buecher (regal_id);
CREATE INDEX idx_buecher_titel ON buecher USING GIN (titel gin_trgm_ops);
CREATE INDEX idx_buecher_groesse ON buecher (groesse_mb);

-- ============================================
-- EBENE 5: KAPITEL (Sections)
-- ============================================

CREATE TABLE kapitel (
    id SERIAL PRIMARY KEY,
    
    -- Hierarchie-Link
    buch_id INT NOT NULL REFERENCES buecher(id) ON DELETE CASCADE,
    
    -- Ordering
    nummer INT NOT NULL,  -- Kapitel 1, 2, 3...
    titel TEXT,
    
    -- Vektor-Referenz
    vektor_id INT REFERENCES vektoren(id) ON DELETE SET NULL,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Lifecycle
    erstellt_am TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_kapitel_nummer UNIQUE (buch_id, nummer),
    CONSTRAINT valid_nummer CHECK (nummer > 0)
);

CREATE INDEX idx_kapitel_buch ON kapitel (buch_id);
CREATE INDEX idx_kapitel_nummer ON kapitel (buch_id, nummer);

-- ============================================
-- EBENE 6: SEITEN (Chunks)
-- ============================================

CREATE TABLE seiten (
    id BIGSERIAL PRIMARY KEY,  -- BIGSERIAL weil viele Seiten erwartet
    
    -- Hierarchie-Link
    kapitel_id INT NOT NULL REFERENCES kapitel(id) ON DELETE CASCADE,
    
    -- Ordering
    nummer INT NOT NULL,  -- Seite 1, 2, 3...
    
    -- Content (der eigentliche Text!)
    inhalt TEXT NOT NULL,
    
    -- Vektor-Referenz
    vektor_id INT REFERENCES vektoren(id) ON DELETE SET NULL,
    
    -- Größe
    groesse_kb FLOAT NOT NULL,
    
    -- Content Hash
    content_hash BYTEA NOT NULL,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Lifecycle
    erstellt_am TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_seite_nummer UNIQUE (kapitel_id, nummer),
    CONSTRAINT valid_seite_nummer CHECK (nummer > 0),
    CONSTRAINT valid_seite_groesse CHECK (groesse_kb > 0 AND groesse_kb <= 1024)  -- Max 1MB
);

CREATE INDEX idx_seiten_kapitel ON seiten (kapitel_id);
CREATE INDEX idx_seiten_groesse ON seiten (groesse_kb);
CREATE INDEX idx_seiten_hash ON seiten (content_hash);

-- Partitionierung (optional, für Skalierung)
-- ALTER TABLE seiten PARTITION BY RANGE (id);

-- ============================================
-- MATERIALIZED VIEW: KOMPLETTE HIERARCHIE-PFADE
-- (Für schnelle Navigation & Debugging)
-- ============================================

CREATE MATERIALIZED VIEW wissens_pfade AS
SELECT 
    s.id AS seite_id,
    b.id AS bibliothek_id,
    k.id AS kategorie_id,
    r.id AS regal_id,
    bu.id AS buch_id,
    kap.id AS kapitel_id,
    
    -- Hierarchie als String (für Debugging)
    b.name || ' > ' || 
    k.name || ' > ' || 
    r.name || ' > ' || 
    bu.titel || ' > ' || 
    'Kap.' || kap.nummer || ' > ' ||
    'S.' || s.nummer AS pfad_string,
    
    -- Vektor-IDs (für Cascade Search)
    b.vektor_id AS bibliothek_vektor_id,
    k.vektor_id AS kategorie_vektor_id,
    r.vektor_id AS regal_vektor_id,
    bu.vektor_id AS buch_vektor_id,
    kap.vektor_id AS kapitel_vektor_id,
    s.vektor_id AS seite_vektor_id
    
FROM seiten s
JOIN kapitel kap ON s.kapitel_id = kap.id
JOIN buecher bu ON kap.buch_id = bu.id
JOIN regale r ON bu.regal_id = r.id
JOIN kategorien k ON r.kategorie_id = k.id
JOIN bibliotheken b ON k.bibliothek_id = b.id;

-- Index für schnelle Pfad-Suche
CREATE INDEX idx_wissens_pfade_bibliothek ON wissens_pfade (bibliothek_id);
CREATE INDEX idx_wissens_pfade_kategorie ON wissens_pfade (kategorie_id);
CREATE INDEX idx_wissens_pfade_pfad ON wissens_pfade USING GIN (pfad_string gin_trgm_ops);

-- Refresh-Funktion (manuell oder via Cron)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY wissens_pfade;

-- ============================================
-- QUERY LOG (Audit Trail)
-- ============================================

CREATE TABLE query_log (
    id BIGSERIAL PRIMARY KEY,
    
    -- Query Info
    query_text TEXT NOT NULL,
    query_hash BYTEA NOT NULL,
    
    -- Hierarchical Search Path
    search_path JSONB NOT NULL,  -- {"bibliothek": [1], "kategorie": [101, 102], ...}
    
    -- Results
    gefundene_seiten_ids BIGINT[] NOT NULL,
    anzahl_seiten INT NOT NULL,
    gesamt_mb FLOAT NOT NULL,
    
    -- Performance
    dauer_ms INT NOT NULL,
    
    -- Timestamps
    erstellt_am TIMESTAMPTZ DEFAULT NOW(),
    
    -- Tenant
    tenant_id UUID DEFAULT NULL
);

CREATE INDEX idx_query_log_hash ON query_log (query_hash);
CREATE INDEX idx_query_log_created ON query_log (erstellt_am DESC);
CREATE INDEX idx_query_log_tenant ON query_log (tenant_id) WHERE tenant_id IS NOT NULL;

-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Funktion: Berechne Gesamt-Größe eines Buchs
CREATE OR REPLACE FUNCTION buch_groesse_aktualisieren(p_buch_id INT)
RETURNS VOID AS $$
DECLARE
    neue_groesse FLOAT;
BEGIN
    SELECT COALESCE(SUM(s.groesse_kb) / 1024.0, 0)
    INTO neue_groesse
    FROM kapitel kap
    JOIN seiten s ON kap.id = s.kapitel_id
    WHERE kap.buch_id = p_buch_id;
    
    UPDATE buecher
    SET groesse_mb = neue_groesse,
        aktualisiert_am = NOW()
    WHERE id = p_buch_id;
END;
$$ LANGUAGE plpgsql;

-- Funktion: Hierarchie-Pfad als Array zurückgeben
CREATE OR REPLACE FUNCTION get_hierarchie_pfad(p_seite_id BIGINT)
RETURNS INT[] AS $$
DECLARE
    pfad INT[];
BEGIN
    SELECT ARRAY[
        b.id,
        k.id,
        r.id,
        bu.id,
        kap.id,
        s.id::INT
    ]
    INTO pfad
    FROM seiten s
    JOIN kapitel kap ON s.kapitel_id = kap.id
    JOIN buecher bu ON kap.buch_id = bu.id
    JOIN regale r ON bu.regal_id = r.id
    JOIN kategorien k ON r.kategorie_id = k.id
    JOIN bibliotheken b ON k.bibliothek_id = b.id
    WHERE s.id = p_seite_id;
    
    RETURN pfad;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================
-- TRIGGERS
-- ============================================

-- Trigger: Auto-Update Buch-Größe wenn Seiten hinzugefügt werden
CREATE OR REPLACE FUNCTION trigger_update_buch_groesse()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM buch_groesse_aktualisieren(
        (SELECT buch_id FROM kapitel WHERE id = NEW.kapitel_id)
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER auto_update_buch_groesse
AFTER INSERT OR UPDATE OR DELETE ON seiten
FOR EACH ROW
EXECUTE FUNCTION trigger_update_buch_groesse();

-- Trigger: Auto-Update aktualisiert_am Timestamps
CREATE OR REPLACE FUNCTION trigger_update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.aktualisiert_am = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_bibliotheken_timestamp
BEFORE UPDATE ON bibliotheken
FOR EACH ROW
EXECUTE FUNCTION trigger_update_timestamp();

CREATE TRIGGER update_kategorien_timestamp
BEFORE UPDATE ON kategorien
FOR EACH ROW
EXECUTE FUNCTION trigger_update_timestamp();

CREATE TRIGGER update_regale_timestamp
BEFORE UPDATE ON regale
FOR EACH ROW
EXECUTE FUNCTION trigger_update_timestamp();

CREATE TRIGGER update_buecher_timestamp
BEFORE UPDATE ON buecher
FOR EACH ROW
EXECUTE FUNCTION trigger_update_timestamp();

-- ============================================
-- SEED DATA: Minimal-Bibliothek für Testing
-- ============================================

-- Insert Dummy Vektoren (werden später durch echte Embeddings ersetzt)
DO $$
DECLARE
    v_bib_id INT;
    v_kat_id INT;
    v_reg_id INT;
    v_buch_id INT;
    v_kap_id INT;
BEGIN
    -- Bibliothek
    INSERT INTO vektoren (dims, ebene, source)
    VALUES (
        ARRAY(SELECT (random() * 200 - 100)::SMALLINT FROM generate_series(1, 64)),
        'bibliothek',
        'seed:dummy:v1'
    ) RETURNING id INTO v_bib_id;
    
    INSERT INTO bibliotheken (name, beschreibung, vektor_id)
    VALUES ('Programming', 'Software Development & Programming', v_bib_id);
    
    -- Kategorie
    INSERT INTO vektoren (dims, ebene, source)
    VALUES (
        ARRAY(SELECT (random() * 200 - 100)::SMALLINT FROM generate_series(1, 64)),
        'kategorie',
        'seed:dummy:v1'
    ) RETURNING id INTO v_kat_id;
    
    INSERT INTO kategorien (bibliothek_id, name, beschreibung, vektor_id)
    VALUES (
        (SELECT id FROM bibliotheken WHERE name = 'Programming'),
        'Python',
        'Python Programming Language',
        v_kat_id
    );
    
    -- Regal
    INSERT INTO vektoren (dims, ebene, source)
    VALUES (
        ARRAY(SELECT (random() * 200 - 100)::SMALLINT FROM generate_series(1, 64)),
        'regal',
        'seed:dummy:v1'
    ) RETURNING id INTO v_reg_id;
    
    INSERT INTO regale (kategorie_id, name, beschreibung, vektor_id)
    VALUES (
        (SELECT id FROM kategorien WHERE name = 'Python'),
        'Advanced Features',
        'Advanced Python Programming Topics',
        v_reg_id
    );
    
    -- Buch
    INSERT INTO vektoren (dims, ebene, source)
    VALUES (
        ARRAY(SELECT (random() * 200 - 100)::SMALLINT FROM generate_series(1, 64)),
        'buch',
        'seed:dummy:v1'
    ) RETURNING id INTO v_buch_id;
    
    INSERT INTO buecher (regal_id, titel, autor, vektor_id, groesse_mb, content_hash)
    VALUES (
        (SELECT id FROM regale WHERE name = 'Advanced Features'),
        'Python Lambda Functions Guide',
        'Expert Author',
        v_buch_id,
        0,  -- Wird via Trigger berechnet
        decode('deadbeef', 'hex')
    );
    
    -- Kapitel
    INSERT INTO vektoren (dims, ebene, source)
    VALUES (
        ARRAY(SELECT (random() * 200 - 100)::SMALLINT FROM generate_series(1, 64)),
        'kapitel',
        'seed:dummy:v1'
    ) RETURNING id INTO v_kap_id;
    
    INSERT INTO kapitel (buch_id, nummer, titel, vektor_id)
    VALUES (
        (SELECT id FROM buecher WHERE titel = 'Python Lambda Functions Guide'),
        1,
        'Introduction to Lambda Functions',
        v_kap_id
    );
    
    -- Seite
    INSERT INTO vektoren (dims, ebene, source)
    VALUES (
        ARRAY(SELECT (random() * 200 - 100)::SMALLINT FROM generate_series(1, 64)),
        'seite',
        'seed:dummy:v1'
    );
    
    INSERT INTO seiten (kapitel_id, nummer, inhalt, vektor_id, groesse_kb, content_hash)
    VALUES (
        (SELECT id FROM kapitel WHERE titel = 'Introduction to Lambda Functions'),
        1,
        E'# Lambda Functions in Python\n\nLambda functions are anonymous functions defined with the lambda keyword.\n\nExample:\n```python\nsquare = lambda x: x**2\nprint(square(5))  # Output: 25\n```\n\nLambda functions are useful for:\n- Short, throwaway functions\n- Functional programming patterns\n- map(), filter(), reduce() operations',
        (SELECT id FROM vektoren WHERE ebene = 'seite' ORDER BY id DESC LIMIT 1),
        0.5,  -- 500 bytes
        decode('cafebabe', 'hex')
    );
END $$;

-- Refresh Materialized View
REFRESH MATERIALIZED VIEW wissens_pfade;

-- Verify
SELECT * FROM wissens_pfade;

-- ============================================
-- STATISTICS & MAINTENANCE
-- ============================================

-- Analyze alle Tabellen
ANALYZE bibliotheken, kategorien, regale, buecher, kapitel, seiten, vektoren;

-- Setze Autovacuum Aggressiveness (optional)
ALTER TABLE seiten SET (
    autovacuum_vacuum_scale_factor = 0.01,
    autovacuum_analyze_scale_factor = 0.01
);
```

---

## Python Implementation

### 1. Hierarchical Embedder

**Datei:** `knowledge/services/hierarchical_embedder.py`

```python
"""
Hierarchical Embedder - Embeds jede Hierarchie-Ebene mit Kontext

Key Insight: Bibliothek-Embedding ist abstrakt, Seiten-Embedding ist konkret
"""

from typing import List, Optional
import ollama
import numpy as np


class HierarchicalEmbedder:
    """
    Generiert kontextuelle Embeddings für jede Hierarchie-Ebene
    """
    
    def __init__(self, model: str = "nomic-embed-text"):
        self.model = model
        self.model_hash = self._compute_model_hash()
    
    def _compute_model_hash(self) -> str:
        """Get model version hash for determinism"""
        # In production: SHA256 des Modell-Files
        return f"{self.model}:v1.5:sha256:abc123def456"
    
    def _embed_raw(self, text: str) -> List[float]:
        """Raw Ollama embedding (768D float)"""
        response = ollama.embeddings(
            model=self.model,
            prompt=text
        )
        return response['embedding']
    
    def _quantize_to_int16(self, float_emb: List[float], target_dims: int = 64) -> List[int]:
        """
        Reduce dimensions + Quantize zu int16
        
        Method: PCA-like reduction (simplified)
        1. Chunk in 768/64 = 12 segments
        2. Average each segment
        3. Normalize & Scale to int16
        """
        arr = np.array(float_emb)
        
        # Dimension Reduction (Simple Averaging)
        chunk_size = len(arr) // target_dims
        reduced = []
        for i in range(target_dims):
            start = i * chunk_size
            end = start + chunk_size if i < target_dims - 1 else len(arr)
            avg = np.mean(arr[start:end])
            reduced.append(avg)
        
        # Normalize to [-1, 1]
        arr_reduced = np.array(reduced)
        min_val = np.min(arr_reduced)
        max_val = np.max(arr_reduced)
        
        if max_val == min_val:
            normalized = np.zeros(target_dims)
        else:
            normalized = (arr_reduced - min_val) / (max_val - min_val) * 2 - 1
        
        # Scale to int16 range [-32767, 32767]
        int_emb = (normalized * 32767).astype(np.int16).tolist()
        
        return int_emb
    
    # ============================================
    # EBENE 1: BIBLIOTHEK (sehr abstrakt)
    # ============================================
    
    def embed_bibliothek(self, name: str, beschreibung: str = "") -> List[int]:
        """
        Bibliothek Embedding - High-Level Domain
        
        Beispiel: "Programming" → sehr breites Konzept
        """
        text = f"Knowledge domain: {name}"
        if beschreibung:
            text += f". {beschreibung}"
        
        float_emb = self._embed_raw(text)
        return self._quantize_to_int16(float_emb)
    
    # ============================================
    # EBENE 2: KATEGORIE (Topic-Level)
    # ============================================
    
    def embed_kategorie(
        self, 
        bibliothek_name: str,
        kategorie_name: str,
        beschreibung: str = ""
    ) -> List[int]:
        """
        Kategorie Embedding - Im Kontext der Bibliothek
        
        Beispiel: "Programming → Python" → spezifischer als nur "Python"
        """
        text = f"Topic within {bibliothek_name}: {kategorie_name}"
        if beschreibung:
            text += f". {beschreibung}"
        
        float_emb = self._embed_raw(text)
        return self._quantize_to_int16(float_emb)
    
    # ============================================
    # EBENE 3: REGAL (Cluster-Level)
    # ============================================
    
    def embed_regal(
        self,
        kategorie_kontext: str,  # "Programming → Python"
        regal_name: str,
        beschreibung: str = ""
    ) -> List[int]:
        """
        Regal Embedding - Topic Cluster
        
        Beispiel: "Python → Advanced Features"
        """
        text = f"Topic cluster in {kategorie_kontext}: {regal_name}"
        if beschreibung:
            text += f". {beschreibung}"
        
        float_emb = self._embed_raw(text)
        return self._quantize_to_int16(float_emb)
    
    # ============================================
    # EBENE 4: BUCH (Document-Level)
    # ============================================
    
    def embed_buch(
        self,
        regal_kontext: str,  # "Python → Advanced"
        titel: str,
        autor: str = "",
        abstract: str = ""
    ) -> List[int]:
        """
        Buch Embedding - Dokument-Semantik
        
        Beispiel: "Python Lambda Functions Guide"
        """
        text = f"Book in {regal_kontext}: {titel}"
        if autor:
            text += f" by {autor}"
        if abstract:
            text += f". {abstract}"
        
        float_emb = self._embed_raw(text)
        return self._quantize_to_int16(float_emb)
    
    # ============================================
    # EBENE 5: KAPITEL (Section-Level)
    # ============================================
    
    def embed_kapitel(
        self,
        buch_kontext: str,  # "Python Lambda Functions Guide"
        kapitel_nummer: int,
        kapitel_titel: str
    ) -> List[int]:
        """
        Kapitel Embedding - Section Theme
        
        Beispiel: "Chapter 1: Introduction to Lambda Functions"
        """
        text = f"Chapter {kapitel_nummer} in '{buch_kontext}': {kapitel_titel}"
        
        float_emb = self._embed_raw(text)
        return self._quantize_to_int16(float_emb)
    
    # ============================================
    # EBENE 6: SEITE (Chunk-Level, sehr konkret)
    # ============================================
    
    def embed_seite(
        self,
        kapitel_kontext: str,  # "Chapter 1: Intro to Lambdas"
        inhalt: str
    ) -> List[int]:
        """
        Seiten Embedding - Actual Content
        
        Beispiel: "Lambda functions are anonymous..."
        """
        # Truncate Content für Embedding (max 8000 chars)
        truncated = inhalt[:8000]
        
        text = f"Page in {kapitel_kontext}:\n\n{truncated}"
        
        float_emb = self._embed_raw(text)
        return self._quantize_to_int16(float_emb)


# ============================================
# USAGE EXAMPLE
# ============================================

if __name__ == "__main__":
    embedder = HierarchicalEmbedder()
    
    # Beispiel: Embed komplette Hierarchie
    bib_vec = embedder.embed_bibliothek("Programming", "Software Development")
    print(f"Bibliothek Vector (64D): {bib_vec[:5]}...")  # Zeige erste 5 Dims
    
    kat_vec = embedder.embed_kategorie("Programming", "Python", "Python language")
    print(f"Kategorie Vector (64D): {kat_vec[:5]}...")
    
    # etc für alle Ebenen...
```

### 2. Hierarchical Search Engine

**Datei:** `knowledge/services/hierarchical_search.py`

```python
"""
Hierarchical Search Engine - Cascade Filtering durch 6 Ebenen

Algorithmus:
1. Start mit allen Bibliotheken
2. Für jede Ebene:
   - Embed Query für diese Ebene
   - Suche Top-K Vektoren (nur innerhalb Parent-Filter!)
   - Update Filter für nächste Ebene
3. Return finale Seiten

Performance: O(log n) statt O(n) durch Cascade
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import psycopg2
import numpy as np
from hierarchical_embedder import HierarchicalEmbedder


@dataclass
class SearchResult:
    """Ein gefundenes Element (Bibliothek, Kategorie, etc.)"""
    id: int
    ebene: str
    name: str
    vektor_id: int
    similarity: float
    parent_id: Optional[int] = None


@dataclass
class SearchConfig:
    """Konfiguration für Hierarchical Search"""
    max_depth: int = 6  # Bis zu welcher Ebene suchen? (1=Bib, 6=Seite)
    top_k_per_level: List[int] = None  # Wie viele Items pro Ebene? [1, 3, 5, 5, 10, 20]
    budget_mb: float = 100.0  # Max MB Bücher/Seiten
    min_similarity: float = 0.5  # Min Cosine Similarity
    
    def __post_init__(self):
        if self.top_k_per_level is None:
            # Default: 1 Bib, 3 Kat, 5 Regal, 5 Bücher, 10 Kapitel, 20 Seiten
            self.top_k_per_level = [1, 3, 5, 5, 10, 20]


class HierarchicalSearchEngine:
    """
    Hierarchische Vektor-Suche mit Cascade Filtering
    """
    
    # Tabellen-Namen pro Ebene
    TABLES = {
        1: 'bibliotheken',
        2: 'kategorien',
        3: 'regale',
        4: 'buecher',
        5: 'kapitel',
        6: 'seiten'
    }
    
    # Parent FK Column Names
    PARENT_FKS = {
        2: 'bibliothek_id',
        3: 'kategorie_id',
        4: 'regal_id',
        5: 'buch_id',
        6: 'kapitel_id'
    }
    
    def __init__(self, db_connection, embedder: HierarchicalEmbedder):
        self.db = db_connection
        self.embedder = embedder
    
    def _cosine_similarity(self, vec_a: List[int], vec_b: List[int]) -> float:
        """Cosine Similarity zwischen zwei int16 Vektoren"""
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(dot / (norm_a * norm_b))
    
    def _vector_search_level(
        self,
        table: str,
        query_vec: List[int],
        parent_filter: Optional[Dict[str, List[int]]],
        top_k: int,
        min_similarity: float
    ) -> List[SearchResult]:
        """
        Vektor-Suche auf einer Hierarchie-Ebene
        
        Args:
            table: Tabellenname (z.B. "kategorien")
            query_vec: 64D Query-Vektor
            parent_filter: {"bibliothek_id": [1, 2]} (nur diese Parents)
            top_k: Wie viele Results?
            min_similarity: Min Score
        
        Returns:
            List von SearchResults (sortiert nach Similarity)
        """
        cursor = self.db.cursor()
        
        # Build Query
        if parent_filter:
            filter_col = list(parent_filter.keys())[0]
            filter_ids = parent_filter[filter_col]
            
            query = f"""
                SELECT 
                    t.id,
                    t.name,
                    t.vektor_id,
                    v.dims,
                    t.{filter_col} AS parent_id
                FROM {table} t
                JOIN vektoren v ON t.vektor_id = v.id
                WHERE t.{filter_col} = ANY(%s)
            """
            cursor.execute(query, (filter_ids,))
        else:
            # Keine Filter (nur auf Bibliothek-Ebene)
            query = f"""
                SELECT 
                    t.id,
                    t.name,
                    t.vektor_id,
                    v.dims,
                    NULL AS parent_id
                FROM {table} t
                JOIN vektoren v ON t.vektor_id = v.id
            """
            cursor.execute(query)
        
        # Compute Similarities
        results = []
        for row in cursor.fetchall():
            item_id, name, vektor_id, dims, parent_id = row
            
            # Cosine Similarity
            similarity = self._cosine_similarity(query_vec, dims)
            
            if similarity >= min_similarity:
                results.append(SearchResult(
                    id=item_id,
                    ebene=table,
                    name=name,
                    vektor_id=vektor_id,
                    similarity=similarity,
                    parent_id=parent_id
                ))
        
        # Sort by Similarity (descending)
        results.sort(key=lambda r: r.similarity, reverse=True)
        
        # Return Top-K
        return results[:top_k]
    
    def search(
        self, 
        query_text: str,
        config: SearchConfig = None
    ) -> Dict[str, Any]:
        """
        Haupt-Suchfunktion: Query → Hierarchische Cascade → Seiten
        
        Returns:
            {
                "query": "...",
                "pfad": {
                    "bibliothek": [...],
                    "kategorie": [...],
                    # etc
                },
                "seiten": [...],
                "total_mb": 12.5,
                "dauer_ms": 150
            }
        """
        import time
        start_time = time.time()
        
        if config is None:
            config = SearchConfig()
        
        # Result Accumulator
        pfad = {}
        current_filter = None
        
        # ============================================
        # LEVEL 1: BIBLIOTHEK
        # ============================================
        
        if config.max_depth >= 1:
            # Embed Query für Bibliothek-Ebene (sehr abstrakt)
            query_vec = self.embedder.embed_bibliothek(query_text)
            
            # Search
            bibliotheken = self._vector_search_level(
                table='bibliotheken',
                query_vec=query_vec,
                parent_filter=None,  # Keine Parents
                top_k=config.top_k_per_level[0],
                min_similarity=config.min_similarity
            )
            
            pfad['bibliothek'] = bibliotheken
            
            # Update Filter für nächste Ebene
            current_filter = {'bibliothek_id': [b.id for b in bibliotheken]}
        
        # ============================================
        # LEVEL 2: KATEGORIE
        # ============================================
        
        if config.max_depth >= 2 and current_filter:
            # Embed mit Kontext (wir wissen schon die Bibliothek!)
            # Vereinfacht: nehme erste Bibliothek als Kontext
            bib_name = pfad['bibliothek'][0].name if pfad['bibliothek'] else "Unknown"
            query_vec = self.embedder.embed_kategorie(bib_name, query_text)
            
            kategorien = self._vector_search_level(
                table='kategorien',
                query_vec=query_vec,
                parent_filter=current_filter,
                top_k=config.top_k_per_level[1],
                min_similarity=config.min_similarity
            )
            
            pfad['kategorie'] = kategorien
            current_filter = {'kategorie_id': [k.id for k in kategorien]}
        
        # ============================================
        # LEVEL 3: REGAL
        # ============================================
        
        if config.max_depth >= 3 and current_filter:
            kontext = f"{bib_name} → {pfad['kategorie'][0].name}" if pfad.get('kategorie') else bib_name
            query_vec = self.embedder.embed_regal(kontext, query_text)
            
            regale = self._vector_search_level(
                table='regale',
                query_vec=query_vec,
                parent_filter=current_filter,
                top_k=config.top_k_per_level[2],
                min_similarity=config.min_similarity
            )
            
            pfad['regal'] = regale
            current_filter = {'regal_id': [r.id for r in regale]}
        
        # ============================================
        # LEVEL 4: BUCH (mit Budget Check!)
        # ============================================
        
        if config.max_depth >= 4 and current_filter:
            kontext = f"{bib_name} → Advanced"  # Simplified
            query_vec = self.embedder.embed_buch(kontext, query_text)
            
            # Fetch Bücher mit Größen-Info
            cursor = self.db.cursor()
            regal_ids = current_filter['regal_id']
            
            cursor.execute("""
                SELECT 
                    b.id,
                    b.titel AS name,
                    b.vektor_id,
                    v.dims,
                    b.regal_id AS parent_id,
                    b.groesse_mb
                FROM buecher b
                JOIN vektoren v ON b.vektor_id = v.id
                WHERE b.regal_id = ANY(%s)
            """, (regal_ids,))
            
            buecher_candidates = []
            for row in cursor.fetchall():
                item_id, name, vektor_id, dims, parent_id, groesse_mb = row
                similarity = self._cosine_similarity(query_vec, dims)
                
                if similarity >= config.min_similarity:
                    result = SearchResult(
                        id=item_id,
                        ebene='buecher',
                        name=name,
                        vektor_id=vektor_id,
                        similarity=similarity,
                        parent_id=parent_id
                    )
                    # Attach size
                    result.groesse_mb = groesse_mb
                    buecher_candidates.append(result)
            
            # Sort & Budget-Filter
            buecher_candidates.sort(key=lambda b: b.similarity, reverse=True)
            
            buecher = []
            total_mb = 0.0
            for buch in buecher_candidates:
                if total_mb + buch.groesse_mb <= config.budget_mb:
                    buecher.append(buch)
                    total_mb += buch.groesse_mb
                    
                    if len(buecher) >= config.top_k_per_level[3]:
                        break
            
            pfad['buch'] = buecher
            current_filter = {'buch_id': [b.id for b in buecher]}
        
        # ============================================
        # LEVEL 5: KAPITEL
        # ============================================
        
        if config.max_depth >= 5 and current_filter:
            buch_name = pfad['buch'][0].name if pfad.get('buch') else "Unknown Book"
            query_vec = self.embedder.embed_kapitel(buch_name, 1, query_text)  # Vereinfacht
            
            kapitel = self._vector_search_level(
                table='kapitel',
                query_vec=query_vec,
                parent_filter=current_filter,
                top_k=config.top_k_per_level[4],
                min_similarity=config.min_similarity
            )
            
            pfad['kapitel'] = kapitel
            current_filter = {'kapitel_id': [k.id for k in kapitel]}
        
        # ============================================
        # LEVEL 6: SEITEN (Final Results!)
        # ============================================
        
        seiten_results = []
        if config.max_depth >= 6 and current_filter:
            kapitel_name = pfad['kapitel'][0].name if pfad.get('kapitel') else "Chapter"
            
            # Hier brauchen wir den Content!
            cursor = self.db.cursor()
            kapitel_ids = current_filter['kapitel_id']
            
            cursor.execute("""
                SELECT 
                    s.id,
                    s.inhalt,
                    s.vektor_id,
                    v.dims,
                    s.kapitel_id AS parent_id,
                    s.groesse_kb
                FROM seiten s
                JOIN vektoren v ON s.vektor_id = v.id
                WHERE s.kapitel_id = ANY(%s)
            """, (kapitel_ids,))
            
            for row in cursor.fetchall():
                item_id, inhalt, vektor_id, dims, parent_id, groesse_kb = row
                
                # Embed Query für Seiten-Ebene
                query_vec_seite = self.embedder.embed_seite(kapitel_name, query_text)
                similarity = self._cosine_similarity(query_vec_seite, dims)
                
                if similarity >= config.min_similarity:
                    result = SearchResult(
                        id=item_id,
                        ebene='seiten',
                        name=f"Seite (ID: {item_id})",
                        vektor_id=vektor_id,
                        similarity=similarity,
                        parent_id=parent_id
                    )
                    result.inhalt = inhalt
                    result.groesse_kb = groesse_kb
                    seiten_results.append(result)
            
            # Sort & Limit
            seiten_results.sort(key=lambda s: s.similarity, reverse=True)
            seiten_results = seiten_results[:config.top_k_per_level[5]]
            
            pfad['seite'] = seiten_results
        
        # ============================================
        # RESULT ASSEMBLY
        # ============================================
        
        end_time = time.time()
        dauer_ms = int((end_time - start_time) * 1000)
        
        total_mb = sum(s.groesse_kb / 1024.0 for s in seiten_results)
        
        return {
            "query": query_text,
            "pfad": pfad,
            "seiten": [
                {
                    "id": s.id,
                    "inhalt": s.inhalt,
                    "similarity": s.similarity,
                    "groesse_kb": s.groesse_kb
                }
                for s in seiten_results
            ],
            "total_mb": round(total_mb, 2),
            "anzahl_seiten": len(seiten_results),
            "dauer_ms": dauer_ms
        }


# ============================================
# USAGE EXAMPLE
# ============================================

if __name__ == "__main__":
    import psycopg2
    
    # Setup
    db_conn = psycopg2.connect("postgresql://localhost/bruce_knowledge")
    embedder = HierarchicalEmbedder()
    search_engine = HierarchicalSearchEngine(db_conn, embedder)
    
    # Search
    config = SearchConfig(
        max_depth=6,
        top_k_per_level=[1, 3, 5, 3, 5, 10],
        budget_mb=50.0,
        min_similarity=0.3
    )
    
    results = search_engine.search(
        query_text="Python Lambda Functions Tutorial",
        config=config
    )
    
    print(f"\n=== SEARCH RESULTS ===")
    print(f"Query: {results['query']}")
    print(f"Duration: {results['dauer_ms']}ms")
    print(f"Found: {results['anzahl_seiten']} Seiten ({results['total_mb']} MB)")
    print(f"\nPath:")
    for ebene, items in results['pfad'].items():
        if items:
            print(f"  {ebene}: {[i.name for i in items]}")
    
    print(f"\nTop Seiten:")
    for seite in results['seiten'][:3]:
        print(f"  - ID {seite['id']}: {seite['inhalt'][:100]}... (sim={seite['similarity']:.3f})")
```

---

## C++ Bruce Integration

### `include/bruce/knowledge/hierarchical_guard.hpp`

```cpp
#pragma once
#include "bruce/core/state/state.hpp"
#include "bruce/core/rules/rule_set.hpp"
#include <cstdint>
#include <vector>
#include <string>
#include <optional>

namespace bruce::knowledge {

// ============================================
// HIERARCHICAL PATH (7 Levels)
// ============================================

struct HierarchicalPath {
    std::optional<std::uint32_t> bibliothek_id;
    std::optional<std::uint32_t> kategorie_id;
    std::optional<std::uint32_t> regal_id;
    std::optional<std::uint32_t> buch_id;
    std::optional<std::uint32_t> kapitel_id;
    std::optional<std::uint32_t> seite_id;
    std::optional<std::uint32_t> vektoren_id;  // 64D Embedding Pointer
    
    std::string to_string() const {
        std::string s = "path[";
        if (bibliothek_id) s += std::to_string(*bibliothek_id);
        else s += "?";
        s += "/";
        if (kategorie_id) s += std::to_string(*kategorie_id);
        else s += "?";
        s += "/";
        if (regal_id) s += std::to_string(*regal_id);
        else s += "?";
        s += "/";
        if (buch_id) s += std::to_string(*buch_id);
        else s += "?";
        s += "/";
        if (kapitel_id) s += std::to_string(*kapitel_id);
        else s += "?";
        s += "/";
        if (seite_id) s += std::to_string(*seite_id);
        else s += "?";
        s += "]";
        return s;
    }
};

// ============================================
// HIERARCHICAL MANIFEST
// ============================================

struct HierarchicalManifest {
    std::string query_id;
    std::string query_text;
    
    // Allowed Path Constraints
    std::vector<std::uint32_t> allowed_bibliothek_ids;
    std::vector<std::uint32_t> allowed_kategorie_ids;
    std::vector<std::uint32_t> allowed_regal_ids;
    std::vector<std::uint32_t> allowed_buch_ids;
    
    // Budget Constraints
    float max_buecher_mb{1000.0f};  // Max 1GB Bücher
    std::uint32_t max_seiten{20};
    std::uint32_t max_depth{6};  // Wie tief suchen?
    
    // Policies
    bool no_network{true};
    bool deterministic{true};
    std::vector<std::string> allowed_languages{"de", "en"};
    
    std::string to_json() const;  // Implementiert in .cpp
};

// ============================================
// HIERARCHICAL GUARD RULE
// ============================================

class HierarchicalGuardRule {
public:
    virtual ~HierarchicalGuardRule() = default;
    
    // Prüft ob dieser Pfad erlaubt ist
    virtual bool allow_path(const HierarchicalPath& path) const = 0;
    
    // Prüft Budget
    virtual bool allow_budget(float buecher_mb, std::uint32_t seiten_count) const = 0;
};

// Beispiel: Bibliothek Whitelist
class BibliothekWhitelistRule : public HierarchicalGuardRule {
public:
    explicit BibliothekWhitelistRule(std::vector<std::uint32_t> allowed)
      : allowed_bib_ids_(std::move(allowed)) {}
    
    bool allow_path(const HierarchicalPath& path) const override {
        if (!path.bibliothek_id) return false;  // Muss gesetzt sein
        
        for (auto id : allowed_bib_ids_) {
            if (*path.bibliothek_id == id) return true;
        }
        return false;
    }
    
    bool allow_budget(float, std::uint32_t) const override {
        return true;  // Keine Budget-Restriktion
    }

private:
    std::vector<std::uint32_t> allowed_bib_ids_;
};

// Budget Rule
class BudgetLimitRule : public HierarchicalGuardRule {
public:
    BudgetLimitRule(float max_mb, std::uint32_t max_seiten)
      : max_mb_(max_mb), max_seiten_(max_seiten) {}
    
    bool allow_path(const HierarchicalPath&) const override {
        return true;  // Path egal
    }
    
    bool allow_budget(float buecher_mb, std::uint32_t seiten_count) const override {
        return buecher_mb <= max_mb_ && seiten_count <= max_seiten_;
    }

private:
    float max_mb_;
    std::uint32_t max_seiten_;
};

// ============================================
// HIERARCHICAL GUARD
// ============================================

class HierarchicalGuard {
public:
    HierarchicalGuard() = default;
    
    void add_rule(std::unique_ptr<HierarchicalGuardRule> rule) {
        rules_.push_back(std::move(rule));
    }
    
    bool validate_manifest(const HierarchicalManifest& manifest) const {
        // Validate Budget
        for (const auto& rule : rules_) {
            if (!rule->allow_budget(manifest.max_buecher_mb, manifest.max_seiten)) {
                return false;
            }
        }
        
        // Validate Paths (simplified - nur Bibliothek-IDs hier)
        for (auto bib_id : manifest.allowed_bibliothek_ids) {
            HierarchicalPath path;
            path.bibliothek_id = bib_id;
            
            bool allowed = false;
            for (const auto& rule : rules_) {
                if (rule->allow_path(path)) {
                    allowed = true;
                    break;
                }
            }
            
            if (!allowed) return false;
        }
        
        return true;
    }

private:
    std::vector<std::unique_ptr<HierarchicalGuardRule>> rules_;
};

// ============================================
// STATE → HIERARCHICAL PATH MAPPER
// ============================================

class StateToHierarchyMapper {
public:
    /**
     * Mapped Bruce's 7D State zu Hierarchical Path
     * 
     * Mapping-Strategie:
     * - State Vec[0-6] enthalten "Intent Hints"
     * - Positive Werte → bestimmte IDs
     * - Kombinationen → komplexe Pfade
     * 
     * Beispiel:
     * State.vec = [7000, 6000, 0, 0, 4000, 0, 6000]
     * → BibliothekID = 1 (Programming)
     * → KategorieID = 101 (Python)
     * → etc.
     */
    static HierarchicalPath map(const bruce::core::State& state) {
        HierarchicalPath path;
        
        // Vereinfachte Heuristik (in Realität: Lookup Table oder LLM)
        
        // Dim 0: Bibliothek Intent
        if (state.vec[0] > 5000) {
            path.bibliothek_id = 1;  // Programming
        } else if (state.vec[0] < -5000) {
            path.bibliothek_id = 2;  // Medicine
        }
        
        // Dim 1: Kategorie Intent
        if (state.vec[1] > 3000 && path.bibliothek_id == 1) {
            path.kategorie_id = 101;  // Python
        } else if (state.vec[1] < -3000 && path.bibliothek_id == 1) {
            path.kategorie_id = 102;  // C++
        }
        
        // Dim 2: Regal Intent (simplified)
        if (state.vec[2] > 5000) {
            path.regal_id = 201;  // Advanced
        }
        
        // Dims 3-6: Feinere Granularität (später ausarbeiten)
        
        return path;
    }
};

} // namespace bruce::knowledge
```

---

## Testing Strategy

### Unit Tests (C++)

**Datei:** `tests/test_hierarchical_guard.cpp`

```cpp
#include "bruce/knowledge/hierarchical_guard.hpp"
#include <cassert>
#include <iostream>

using namespace bruce::knowledge;

int main() {
    // Test 1: Bibliothek Whitelist
    HierarchicalGuard guard;
    guard.add_rule(std::make_unique<BibliothekWhitelistRule>(
        std::vector<std::uint32_t>{1, 2}  // Nur Bib 1 & 2 erlaubt
    ));
    
    HierarchicalManifest manifest;
    manifest.query_id = "test-001";
    manifest.allowed_bibliothek_ids = {1};
    
    assert(guard.validate_manifest(manifest));
    std::cout << "✓ Test 1: Valid bibliothek accepted\n";
    
    // Test 2: Ungültige Bibliothek
    manifest.allowed_bibliothek_ids = {99};  // Nicht in Whitelist
    assert(!guard.validate_manifest(manifest));
    std::cout << "✓ Test 2: Invalid bibliothek rejected\n";
    
    // Test 3: Budget Limit
    HierarchicalGuard guard2;
    guard2.add_rule(std::make_unique<BudgetLimitRule>(50.0f, 10));
    
    manifest.allowed_bibliothek_ids = {1};
    manifest.max_buecher_mb = 30.0f;
    manifest.max_seiten = 5;
    
    assert(guard2.validate_manifest(manifest));
    std::cout << "✓ Test 3: Budget within limits\n";
    
    manifest.max_buecher_mb = 100.0f;  // Über Limit
    assert(!guard2.validate_manifest(manifest));
    std::cout << "✓ Test 4: Budget exceeded rejected\n";
    
    // Test 5: State Mapping
    bruce::core::State state;
    state.vec = {7000, 6000, 0, 0, 4000, 0, 6000};
    
    auto path = StateToHierarchyMapper::map(state);
    assert(path.bibliothek_id.has_value());
    assert(*path.bibliothek_id == 1);  // Programming
    std::cout << "✓ Test 5: State mapped to path: " << path.to_string() << "\n";
    
    std::cout << "\n✅ All Hierarchical Guard tests passed!\n";
    return 0;
}
```

### Integration Tests (Python)

**Datei:** `knowledge/tests/test_hierarchical_search_integration.py`

```python
import pytest
import psycopg2
from services.hierarchical_embedder import HierarchicalEmbedder
from services.hierarchical_search import HierarchicalSearchEngine, SearchConfig


@pytest.fixture
def db_connection():
    conn = psycopg2.connect("postgresql://localhost/bruce_knowledge")
    yield conn
    conn.close()


@pytest.fixture
def search_engine(db_connection):
    embedder = HierarchicalEmbedder()
    return HierarchicalSearchEngine(db_connection, embedder)


def test_search_finds_python_lambda(search_engine):
    """Test: Query findet Python Lambda Seite"""
    config = SearchConfig(
        max_depth=6,
        top_k_per_level=[1, 2, 3, 2, 3, 5],
        budget_mb=10.0,
        min_similarity=0.3
    )
    
    results = search_engine.search(
        query_text="Python Lambda Functions",
        config=config
    )
    
    # Assertions
    assert results['anzahl_seiten'] > 0, "Keine Seiten gefunden"
    assert results['total_mb'] <= 10.0, "Budget überschritten"
    assert results['dauer_ms'] < 1000, "Zu langsam"
    
    # Pfad validieren
    assert 'bibliothek' in results['pfad']
    assert len(results['pfad']['bibliothek']) > 0
    assert results['pfad']['bibliothek'][0].name == 'Programming'
    
    print(f"✓ Found {results['anzahl_seiten']} Seiten in {results['dauer_ms']}ms")


def test_budget_respected(search_engine):
    """Test: Budget-Limit wird respektiert"""
    config = SearchConfig(
        max_depth=4,  # Nur bis Bücher
        budget_mb=0.5,  # Sehr kleines Budget
        top_k_per_level=[1, 2, 3, 5]
    )
    
    results = search_engine.search("Python Tutorial", config)
    
    # Check Bücher-Budget
    buecher = results['pfad'].get('buch', [])
    total_mb = sum(b.groesse_mb for b in buecher)
    
    assert total_mb <= 0.5, f"Budget exceeded: {total_mb} MB"
    print(f"✓ Budget respected: {total_mb} MB < 0.5 MB")


def test_empty_query_returns_nothing(search_engine):
    """Test: Leere Query findet nichts"""
    results = search_engine.search("")
    
    assert results['anzahl_seiten'] == 0
```

---

## Performance Benchmarks

**Datei:** `knowledge/benchmarks/bench_hierarchical_vs_flat.py`

```python
"""
Benchmark: Hierarchical vs Flat Search

Hypothesis: Hierarchical ist 10-100x schneller
"""

import time
import psycopg2
from services.hierarchical_search import HierarchicalSearchEngine, SearchConfig
from services.hierarchical_embedder import HierarchicalEmbedder


def bench_hierarchical_search(db_conn, queries):
    """Hierarchical Search"""
    embedder = HierarchicalEmbedder()
    engine = HierarchicalSearchEngine(db_conn, embedder)
    config = SearchConfig(max_depth=6, budget_mb=100.0)
    
    times = []
    for query in queries:
        start = time.time()
        results = engine.search(query, config)
        end = time.time()
        times.append((end - start) * 1000)  # ms
    
    return times


def bench_flat_search(db_conn, queries):
    """Flat Search (naive, alle Seiten scannen)"""
    embedder = HierarchicalEmbedder()
    cursor = db_conn.cursor()
    
    times = []
    for query in queries:
        start = time.time()
        
        # Query Embedding
        query_vec = embedder.embed_seite("", query)
        
        # Scan ALL Seiten (keine Hierarchie!)
        cursor.execute("""
            SELECT s.id, s.inhalt, v.dims
            FROM seiten s
            JOIN vektoren v ON s.vektor_id = v.id
            LIMIT 10000  -- Cap für Test
        """)
        
        # Compute Similarities (in Python, langsam!)
        import numpy as np
        best_seiten = []
        for row in cursor.fetchall():
            seite_id, inhalt, dims = row
            
            # Cosine Similarity
            a = np.array(query_vec, dtype=np.float32)
            b = np.array(dims, dtype=np.float32)
            sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
            
            best_seiten.append((seite_id, sim))
        
        # Sort & Take Top-10
        best_seiten.sort(key=lambda x: x[1], reverse=True)
        best_seiten = best_seiten[:10]
        
        end = time.time()
        times.append((end - start) * 1000)  # ms
    
    return times


if __name__ == "__main__":
    db_conn = psycopg2.connect("postgresql://localhost/bruce_knowledge")
    
    # Test Queries
    queries = [
        "Python Lambda Functions",
        "C++ Templates",
        "Async Programming Basics",
        "Machine Learning Algorithms",
        "Database Indexing Strategies"
    ]
    
    print("=== BENCHMARK: Hierarchical vs Flat ===\n")
    
    # Hierarchical
    print("Running Hierarchical Search...")
    hierarchical_times = bench_hierarchical_search(db_conn, queries)
    
    # Flat
    print("Running Flat Search...")
    flat_times = bench_flat_search(db_conn, queries)
    
    # Results
    print("\n=== RESULTS ===")
    print(f"Queries: {len(queries)}")
    print(f"\nHierarchical Search:")
    print(f"  Median: {sorted(hierarchical_times)[len(hierarchical_times)//2]:.1f} ms")
    print(f"  Mean:   {sum(hierarchical_times)/len(hierarchical_times):.1f} ms")
    
    print(f"\nFlat Search:")
    print(f"  Median: {sorted(flat_times)[len(flat_times)//2]:.1f} ms")
    print(f"  Mean:   {sum(flat_times)/len(flat_times):.1f} ms")
    
    speedup = (sum(flat_times)/len(flat_times)) / (sum(hierarchical_times)/len(hierarchical_times))
    print(f"\n🚀 Speedup: {speedup:.1f}x faster")
```

---

## Deployment (Docker Compose)

**Datei:** `docker-compose.hierarchical.yml`

```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: bruce_knowledge
      POSTGRES_USER: bruce
      POSTGRES_PASSWORD: dev_secret
    volumes:
      - ./knowledge/migrations:/docker-entrypoint-initdb.d
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5433:5433"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bruce"]
      interval: 5s
      timeout: 5s
      retries: 5

  knowledge_service:
    build:
      context: ./knowledge
      dockerfile: Dockerfile.service
    environment:
      DATABASE_URL: postgresql://bruce:dev_secret@postgres:5433/bruce_knowledge
      OLLAMA_HOST: http://ollama:11434
    depends_on:
      postgres:
        condition: service_healthy
      ollama:
        condition: service_started
    ports:
      - "8000:8000"

  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - "11434:11434"
    # GPU Support (optional)
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]

  bruce_core:
    build:
      context: .
      dockerfile: Dockerfile.bruce
    environment:
      KNOWLEDGE_SERVICE_URL: http://knowledge_service:8000
    depends_on:
      - knowledge_service
    ports:
      - "9000:9000"

volumes:
  postgres_data:
  ollama_data:
```

---

## Nächste Schritte (Konkret)

1. **HEUTE:** Setup PostgreSQL + pgvector via Docker
2. **MORGEN:** Run Migration 002 + Seed Data + Verify
3. **TAG 3:** Build `HierarchicalEmbedder` + Unit Tests
4. **TAG 4-5:** Build `HierarchicalSearchEngine` + Integration Tests
5. **WOCHE 2:** C++ Guard Integration + End-to-End Test
6. **WOCHE 3:** Performance Benchmark + Optimization

---

*"Hierarchie ist nicht Komplexität - Hierarchie ist Klarheit."*
