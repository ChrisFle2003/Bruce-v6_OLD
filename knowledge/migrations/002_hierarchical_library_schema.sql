-- ============================================================
-- Bruce Hierarchical Knowledge Library Schema
-- ============================================================
-- 6-level hierarchical knowledge system with cascade filtering
-- for deterministic semantic search
-- ============================================================

-- Enable pgvector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- 1. VEKTOREN TABLE (Vector Pool)
-- ============================================================
-- Central repository for all 64D int16 vectors
-- Each hierarchical level has its own vector entry

CREATE TABLE IF NOT EXISTS vektoren (
    id SERIAL PRIMARY KEY,
    ebene VARCHAR(50) NOT NULL UNIQUE,  -- Level name: 'bibliothek', 'kategorie', etc.
    dims INT2[] NOT NULL,               -- 64D int16 vector (array of int16)
    created_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    CHECK (array_length(dims, 1) = 64)  -- Ensure 64 dimensions
);

COMMENT ON TABLE vektoren IS
    'Vector pool: Central storage for 64D int16 embeddings. '
    'Each hierarchical level has one representative vector.';

-- ============================================================
-- 2. BIBLIOTHEKEN TABLE (Level 1: Libraries/Domains)
-- ============================================================
-- Top-level domains (e.g., "Programming", "Science", etc.)

CREATE TABLE IF NOT EXISTS bibliotheken (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    beschreibung TEXT,
    vektor_id INT NOT NULL REFERENCES vektoren(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE bibliotheken IS
    'Level 1: Top-level knowledge domains. '
    'Examples: "Programming", "Science", "Literature", etc.';

CREATE INDEX idx_bibliotheken_name ON bibliotheken(name);
CREATE INDEX idx_bibliotheken_vektor_id ON bibliotheken(vektor_id);

-- ============================================================
-- 3. KATEGORIEN TABLE (Level 2: Categories)
-- ============================================================
-- Categories within a library (filtered by bibliothek_id)

CREATE TABLE IF NOT EXISTS kategorien (
    id SERIAL PRIMARY KEY,
    bibliothek_id INT NOT NULL REFERENCES bibliotheken(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    beschreibung TEXT,
    vektor_id INT NOT NULL REFERENCES vektoren(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(bibliothek_id, name)
);

COMMENT ON TABLE kategorien IS
    'Level 2: Categories within libraries (cascade-filtered by bibliothek_id). '
    'Examples: "Python", "Java", "Machine Learning", etc.';

CREATE INDEX idx_kategorien_bibliothek_id ON kategorien(bibliothek_id);
CREATE INDEX idx_kategorien_name ON kategorien(name);
CREATE INDEX idx_kategorien_vektor_id ON kategorien(vektor_id);

-- ============================================================
-- 4. REGALE TABLE (Level 3: Shelves/Topics)
-- ============================================================
-- Topic clusters within a category

CREATE TABLE IF NOT EXISTS regale (
    id SERIAL PRIMARY KEY,
    kategorie_id INT NOT NULL REFERENCES kategorien(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    beschreibung TEXT,
    vektor_id INT NOT NULL REFERENCES vektoren(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(kategorie_id, name)
);

COMMENT ON TABLE regale IS
    'Level 3: Topic clusters within categories (cascade-filtered by kategorie_id). '
    'Examples: "Advanced Features", "Basics", "Performance Optimization", etc.';

CREATE INDEX idx_regale_kategorie_id ON regale(kategorie_id);
CREATE INDEX idx_regale_name ON regale(name);
CREATE INDEX idx_regale_vektor_id ON regale(vektor_id);

-- ============================================================
-- 5. BUECHER TABLE (Level 4: Books/Documents)
-- ============================================================
-- Individual documents or guides

CREATE TABLE IF NOT EXISTS buecher (
    id SERIAL PRIMARY KEY,
    regal_id INT NOT NULL REFERENCES regale(id) ON DELETE CASCADE,
    titel VARCHAR(255) NOT NULL,
    beschreibung TEXT,
    groesse_bytes INT DEFAULT 0,  -- Approximate size for budget tracking
    vektor_id INT NOT NULL REFERENCES vektoren(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(regal_id, titel)
);

COMMENT ON TABLE buecher IS
    'Level 4: Individual documents/books (cascade-filtered by regal_id). '
    'Examples: "Lambda Functions Guide", "Type System Reference", etc.';

CREATE INDEX idx_buecher_regal_id ON buecher(regal_id);
CREATE INDEX idx_buecher_titel ON buecher(titel);
CREATE INDEX idx_buecher_vektor_id ON buecher(vektor_id);

-- ============================================================
-- 6. KAPITEL TABLE (Level 5: Chapters)
-- ============================================================
-- Sections within a book

CREATE TABLE IF NOT EXISTS kapitel (
    id SERIAL PRIMARY KEY,
    buch_id INT NOT NULL REFERENCES buecher(id) ON DELETE CASCADE,
    titel VARCHAR(255) NOT NULL,
    beschreibung TEXT,
    reihenfolge INT DEFAULT 0,  -- Chapter ordering
    vektor_id INT NOT NULL REFERENCES vektoren(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(buch_id, titel)
);

COMMENT ON TABLE kapitel IS
    'Level 5: Chapters/sections within books (cascade-filtered by buch_id). '
    'Examples: "Introduction", "Syntax", "Examples", etc.';

CREATE INDEX idx_kapitel_buch_id ON kapitel(buch_id);
CREATE INDEX idx_kapitel_titel ON kapitel(titel);
CREATE INDEX idx_kapitel_vektor_id ON kapitel(vektor_id);
CREATE INDEX idx_kapitel_reihenfolge ON kapitel(reihenfolge);

-- ============================================================
-- 7. SEITEN TABLE (Level 6: Pages/Content)
-- ============================================================
-- Actual content chunks to be searched

CREATE TABLE IF NOT EXISTS seiten (
    id SERIAL PRIMARY KEY,
    kapitel_id INT NOT NULL REFERENCES kapitel(id) ON DELETE CASCADE,
    inhalt TEXT NOT NULL,
    nummer INT DEFAULT 0,  -- Page number or chunk index
    groesse_bytes INT DEFAULT 0,  -- Size of content for budget tracking
    vektor_id INT NOT NULL REFERENCES vektoren(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(kapitel_id, nummer)
);

COMMENT ON TABLE seiten IS
    'Level 6: Individual pages/content chunks (cascade-filtered by kapitel_id). '
    'These are the final results of hierarchical search.';

CREATE INDEX idx_seiten_kapitel_id ON seiten(kapitel_id);
CREATE INDEX idx_seiten_nummer ON seiten(nummer);
CREATE INDEX idx_seiten_vektor_id ON seiten(vektor_id);

-- ============================================================
-- 8. MATERIALIZED VIEW: WISSENS_PFADE (Navigation Paths)
-- ============================================================
-- Pre-computed full hierarchical paths for fast navigation

CREATE MATERIALIZED VIEW IF NOT EXISTS wissens_pfade AS
SELECT
    b.id AS bib_id,
    b.name AS bib_name,
    k.id AS kat_id,
    k.name AS kat_name,
    r.id AS regal_id,
    r.name AS regal_name,
    bu.id AS buch_id,
    bu.titel AS buch_titel,
    kap.id AS kapitel_id,
    kap.titel AS kapitel_titel,
    s.id AS seite_id,
    s.inhalt AS seite_inhalt,
    (COALESCE(bu.groesse_bytes, 0) + COALESCE(s.groesse_bytes, 0)) AS gesamt_groesse,
    seiten_count.cnt AS seiten_im_kapitel
FROM
    bibliotheken b
    LEFT JOIN kategorien k ON b.id = k.bibliothek_id
    LEFT JOIN regale r ON k.id = r.kategorie_id
    LEFT JOIN buecher bu ON r.id = bu.regal_id
    LEFT JOIN kapitel kap ON bu.id = kap.buch_id
    LEFT JOIN seiten s ON kap.id = s.kapitel_id
    LEFT JOIN (
        SELECT kapitel_id, COUNT(*) as cnt
        FROM seiten
        GROUP BY kapitel_id
    ) seiten_count ON kap.id = seiten_count.kapitel_id
ORDER BY
    b.id, k.id, r.id, bu.id, kap.reihenfolge, s.nummer;

COMMENT ON MATERIALIZED VIEW wissens_pfade IS
    'Pre-computed hierarchical paths for fast navigation. '
    'Includes full chain from Bibliothek to Seite. '
    'Refresh after significant updates: REFRESH MATERIALIZED VIEW wissens_pfade;';

CREATE INDEX idx_wissens_pfade_bib_id ON wissens_pfade(bib_id);
CREATE INDEX idx_wissens_pfade_seite_id ON wissens_pfade(seite_id);

-- ============================================================
-- 9. SEED DATA
-- ============================================================
-- Insert one complete test path: Programming → Python → Advanced → Lambda Guide
-- This demonstrates the full 6-level hierarchy

DO $$
DECLARE
    v_bib_id INT;
    v_kat_id INT;
    v_regal_id INT;
    v_buch_id INT;
    v_kapitel_id INT;
    v_seite_id INT;
BEGIN
    -- Insert placeholder vectors (will be replaced with real embeddings)
    -- Each vector is 64 int16 values (range: -32767 to 32767)
    -- Format: 16 groups of 4 values = 64 total
    INSERT INTO vektoren (ebene, dims) VALUES
        ('bibliothek_programming',
         '{100,200,300,400,500,600,700,800,900,1000,100,200,300,400,500,600,700,800,900,1000,100,200,300,400,500,600,700,800,900,1000,100,200,300,400,500,600,700,800,900,1000,100,200,300,400,500,600,700,800,900,1000,100,200,300,400,500,600,700,800,900,1000,100,200,300,400}'::INT2[]),
        ('kategorie_python',
         '{-100,-200,-300,-400,-500,-600,-700,-800,-900,-1000,-100,-200,-300,-400,-500,-600,-700,-800,-900,-1000,-100,-200,-300,-400,-500,-600,-700,-800,-900,-1000,-100,-200,-300,-400,-500,-600,-700,-800,-900,-1000,-100,-200,-300,-400,-500,-600,-700,-800,-900,-1000,-100,-200,-300,-400,-500,-600,-700,-800,-900,-1000,-100,-200,-300,-400}'::INT2[]),
        ('regal_advanced',
         '{50,100,150,200,50,100,150,200,50,100,150,200,50,100,150,200,50,100,150,200,50,100,150,200,50,100,150,200,50,100,150,200,50,100,150,200,50,100,150,200,50,100,150,200,50,100,150,200,50,100,150,200,50,100,150,200,50,100,150,200,50,100,150,200}'::INT2[]),
        ('buch_lambda_guide',
         '{-50,-100,-150,-200,-50,-100,-150,-200,-50,-100,-150,-200,-50,-100,-150,-200,-50,-100,-150,-200,-50,-100,-150,-200,-50,-100,-150,-200,-50,-100,-150,-200,-50,-100,-150,-200,-50,-100,-150,-200,-50,-100,-150,-200,-50,-100,-150,-200,-50,-100,-150,-200,-50,-100,-150,-200,-50,-100,-150,-200,-50,-100,-150,-200}'::INT2[]),
        ('kapitel_introduction',
         '{1000,-1000,2000,-2000,1000,-1000,2000,-2000,1000,-1000,2000,-2000,1000,-1000,2000,-2000,1000,-1000,2000,-2000,1000,-1000,2000,-2000,1000,-1000,2000,-2000,1000,-1000,2000,-2000,1000,-1000,2000,-2000,1000,-1000,2000,-2000,1000,-1000,2000,-2000,1000,-1000,2000,-2000,1000,-1000,2000,-2000,1000,-1000,2000,-2000,1000,-1000,2000,-2000,1000,-1000,2000,-2000}'::INT2[]),
        ('seite_lambda_syntax',
         '{32000,-32000,16000,-16000,8000,-8000,4000,-4000,32000,-32000,16000,-16000,8000,-8000,4000,-4000,32000,-32000,16000,-16000,8000,-8000,4000,-4000,32000,-32000,16000,-16000,8000,-8000,4000,-4000,32000,-32000,16000,-16000,8000,-8000,4000,-4000,32000,-32000,16000,-16000,8000,-8000,4000,-4000,32000,-32000,16000,-16000,8000,-8000,4000,-4000,32000,-32000,16000,-16000,8000,-8000,4000,-4000}'::INT2[]);

    -- Insert Bibliothek
    INSERT INTO bibliotheken (name, beschreibung, vektor_id)
    SELECT 'Programming', 'Software development and computer science', id
    FROM vektoren WHERE ebene = 'bibliothek_programming'
    RETURNING id INTO v_bib_id;

    -- Insert Kategorie
    INSERT INTO kategorien (bibliothek_id, name, beschreibung, vektor_id)
    SELECT v_bib_id, 'Python', 'Python programming language', id
    FROM vektoren WHERE ebene = 'kategorie_python'
    RETURNING id INTO v_kat_id;

    -- Insert Regal
    INSERT INTO regale (kategorie_id, name, beschreibung, vektor_id)
    SELECT v_kat_id, 'Advanced Features', 'Advanced Python features and patterns', id
    FROM vektoren WHERE ebene = 'regal_advanced'
    RETURNING id INTO v_regal_id;

    -- Insert Buch
    INSERT INTO buecher (regal_id, titel, beschreibung, groesse_bytes, vektor_id)
    SELECT v_regal_id, 'Lambda Functions Guide', 'Comprehensive guide to lambda functions in Python', 15000, id
    FROM vektoren WHERE ebene = 'buch_lambda_guide'
    RETURNING id INTO v_buch_id;

    -- Insert Kapitel
    INSERT INTO kapitel (buch_id, titel, beschreibung, reihenfolge, vektor_id)
    SELECT v_buch_id, 'Introduction', 'Introduction to lambda functions', 1, id
    FROM vektoren WHERE ebene = 'kapitel_introduction'
    RETURNING id INTO v_kapitel_id;

    -- Insert Seite
    INSERT INTO seiten (kapitel_id, inhalt, nummer, groesse_bytes, vektor_id)
    SELECT v_kapitel_id,
           'Lambda functions are anonymous functions defined with the lambda keyword. ' ||
           'Syntax: lambda arguments: expression. ' ||
           'Example: lambda x: x**2 returns a function that squares its argument.',
           1, 500, id
    FROM vektoren WHERE ebene = 'seite_lambda_syntax'
    RETURNING id INTO v_seite_id;

    RAISE NOTICE 'Seed data inserted successfully!';
    RAISE NOTICE 'Created path: Programming > Python > Advanced Features > Lambda Functions Guide > Introduction > Page 1';

END $$;

-- ============================================================
-- 10. REFRESH MATERIALIZED VIEW
-- ============================================================
REFRESH MATERIALIZED VIEW wissens_pfade;

-- ============================================================
-- 11. VERIFICATION QUERIES
-- ============================================================
-- Run these to verify the schema is working

-- Check table counts
-- SELECT 'bibliotheken' as table_name, COUNT(*) FROM bibliotheken
-- UNION ALL
-- SELECT 'kategorien', COUNT(*) FROM kategorien
-- UNION ALL
-- SELECT 'regale', COUNT(*) FROM regale
-- UNION ALL
-- SELECT 'buecher', COUNT(*) FROM buecher
-- UNION ALL
-- SELECT 'kapitel', COUNT(*) FROM kapitel
-- UNION ALL
-- SELECT 'seiten', COUNT(*) FROM seiten
-- UNION ALL
-- SELECT 'vektoren', COUNT(*) FROM vektoren;

-- Check materialized view
-- SELECT COUNT(*) as wissens_pfade_count FROM wissens_pfade;
-- SELECT bib_name, kat_name, regal_name, buch_titel, kapitel_titel, seite_inhalt
-- FROM wissens_pfade LIMIT 1;

COMMIT;
