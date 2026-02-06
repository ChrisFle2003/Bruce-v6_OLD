-- ============================================================
-- Verification Queries for Hierarchical Knowledge Schema
-- ============================================================
-- Run these queries to verify the database setup
-- Usage: psql -h localhost -U bruce -d bruce_knowledge -f verify_schema.sql

-- 1. Check All Tables Exist
\echo '=== TABLE VERIFICATION ==='
SELECT
    table_name,
    CASE
        WHEN table_name IN ('bibliotheken', 'kategorien', 'regale', 'buecher', 'kapitel', 'seiten', 'vektoren')
        THEN '✓ REQUIRED'
        ELSE '  optional'
    END as status
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
  AND table_name LIKE '%bib%' OR table_name LIKE '%kat%' OR table_name LIKE '%regal%'
  OR table_name LIKE '%buch%' OR table_name LIKE '%kapitel%' OR table_name LIKE '%seite%'
  OR table_name = 'vektoren'
ORDER BY table_name;

\echo ''
\echo '=== TABLE ROW COUNTS ==='
SELECT
    'bibliotheken' as table_name, COUNT(*) as row_count FROM bibliotheken
UNION ALL
SELECT 'kategorien', COUNT(*) FROM kategorien
UNION ALL
SELECT 'regale', COUNT(*) FROM regale
UNION ALL
SELECT 'buecher', COUNT(*) FROM buecher
UNION ALL
SELECT 'kapitel', COUNT(*) FROM kapitel
UNION ALL
SELECT 'seiten', COUNT(*) FROM seiten
UNION ALL
SELECT 'vektoren', COUNT(*) FROM vektoren
ORDER BY table_name;

\echo ''
\echo '=== VECTOR VERIFICATION ==='
SELECT
    ebene,
    array_length(dims, 1) as vector_dims,
    CASE
        WHEN array_length(dims, 1) = 64 THEN '✓ CORRECT'
        ELSE '✗ WRONG'
    END as dims_check
FROM vektoren
ORDER BY ebene;

\echo ''
\echo '=== SEED DATA PATH ==='
SELECT
    bib_name,
    kat_name,
    regal_name,
    buch_titel,
    kapitel_titel
FROM wissens_pfade
LIMIT 1;

\echo ''
\echo '=== FULL SEED PATH CONTENT ==='
SELECT
    bib_name || ' > ' || kat_name || ' > ' || regal_name || ' > ' ||
    buch_titel || ' > ' || kapitel_titel as full_path,
    LEFT(seite_inhalt, 80) || '...' as content_preview
FROM wissens_pfade
WHERE seite_inhalt IS NOT NULL
LIMIT 1;

\echo ''
\echo '=== INDEX VERIFICATION ==='
SELECT
    indexname,
    tablename,
    CASE
        WHEN indexname LIKE 'idx_%' THEN '✓ CUSTOM'
        WHEN indexname LIKE '%_pkey' THEN '✓ PRIMARY'
        ELSE '  OTHER'
    END as index_type
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('bibliotheken', 'kategorien', 'regale', 'buecher', 'kapitel', 'seiten', 'vektoren')
ORDER BY tablename, indexname;

\echo ''
\echo '=== MATERIALIZED VIEW VERIFICATION ==='
SELECT
    matviewname as view_name,
    'EXISTS' as status
FROM pg_matviews
WHERE schemaname = 'public'
  AND matviewname = 'wissens_pfade';

\echo ''
\echo '=== CONSTRAINT VERIFICATION ==='
SELECT
    constraint_name,
    constraint_type,
    table_name
FROM information_schema.table_constraints
WHERE table_schema = 'public'
  AND table_name IN ('bibliotheken', 'kategorien', 'regale', 'buecher', 'kapitel', 'seiten', 'vektoren')
ORDER BY table_name, constraint_name;

\echo ''
\echo '=== EXTENSION VERIFICATION ==='
SELECT
    extname,
    CASE WHEN extname = 'vector' THEN '✓ pgvector installed' ELSE '  other extension' END as status
FROM pg_extension;

\echo ''
\echo '=== FINAL STATUS ==='
SELECT
    CASE
        WHEN (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' AND table_name IN ('bibliotheken', 'kategorien', 'regale', 'buecher', 'kapitel', 'seiten', 'vektoren')) = 7
        AND (SELECT COUNT(*) FROM vektoren) = 6
        AND (SELECT COUNT(*) FROM bibliotheken) = 1
        AND (SELECT COUNT(*) FROM wissens_pfade) >= 1
        THEN '✓ SCHEMA VERIFICATION PASSED'
        ELSE '✗ SCHEMA VERIFICATION FAILED'
    END as verification_result;

\echo ''
\echo '=== Verification Complete ==='
