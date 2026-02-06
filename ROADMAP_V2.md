# Bruce Hierarchical Knowledge Library - Roadmap V2

## Vision Statement

Bruce wird zur **intelligenten Bibliothek** - ein deterministischer Wächter, der durch ein **7-stufiges hierarchisches Wissenssystem** navigiert. Statt flacher Vektor-Suche nutzen wir die mentale Struktur einer physischen Bibliothek: Bibliothek → Kategorie → Regal → Buch → Kapitel → Seite.

**Das Dewey-Decimal-System meets Vector Embeddings.**

---

## 🎯 Kernprinzip: Hierarchie schlägt Flat Search

### Alte Welt (Flat Vector Search)
```
10 Millionen Chunks → ein riesiger Vektor-Pool
Query → scanne ALLE Vektoren → Top-K
Problem: Langsam (500ms), unkontrollierbar, nicht auditierbar
```

### Neue Welt (Hierarchische Navigation)
```
Bibliothek (10 Optionen)     → Filter in 1ms
  ↓ Kategorie (100 Optionen)  → Filter in 5ms
    ↓ Regal (500 Optionen)     → Filter in 10ms
      ↓ Buch (2k Optionen)      → Filter in 20ms
        ↓ Kapitel (10k Optionen) → Filter in 30ms
          ↓ Seite (50k Optionen) → Final Search in 50ms

TOTAL: ~116ms statt 500ms (4x schneller!)
Und: Jeder Schritt ist auditierbar, deterministisch, erklärbar
```

---

## 🏗️ Architektur: Die 7 Säulen

### Hierarchie-Ebenen (jede hat eigene Tabelle + Vektoren)

```
1. BibliothekID    - Grobe Domäne (Programming, Medicine, Law, ...)
2. KategorieID     - Sub-Domäne (Python, C++, Rust, ...)
3. RegalID         - Topic Cluster (Basics, Advanced, Async, ...)
4. BuchID          - Spezifisches Werk (max 1GB Content)
5. KapitelID       - Thematische Unterteilung
6. SeiteID         - Eigentlicher Content-Chunk (max 1MB)
7. VektorenID      - FK zu 64D Embedding-Koordinaten
```

**Warum 7 Ebenen?**
- Entspricht menschlichem Denken (wie Library of Congress)
- Jede Ebene hat eigene semantische Granularität
- Bruce's 7D States mappen 1:1 auf 7 Hierarchie-Levels!

### Mapping: Bruce States ↔ Wissens-Hierarchie

```cpp
// Bruce's 7D Vector (bestehend):
state.vec = [dim0, dim1, dim2, dim3, dim4, dim5, dim6]

// Neues Mapping:
dim0 → BibliothekID  (z.B. 1 = Programming)
dim1 → KategorieID   (z.B. 101 = Python)
dim2 → RegalID       (z.B. 201 = Advanced)
dim3 → BuchID        (z.B. 301 = "Lambda Guide")
dim4 → KapitelID     (z.B. 401 = "Chapter 3: Closures")
dim5 → SeiteID       (z.B. 5001 = "Page 42")
dim6 → VektorenID    (z.B. 8888 → 64D Embedding-Koordinaten)
```

**MIND = BLOWN:** Bruce muss sich nicht ändern! Die 7D Struktur war bereits perfekt!

---

## Phase 0: Fundament (Woche 1-2)

### Ziel: Hierarchisches Schema + Seed Data

**Deliverables:**
- [x] PostgreSQL Schema V2 mit 7 Hierarchie-Tabellen
- [x] Vektoren-Tabelle (shared pool für alle Ebenen)
- [x] Wissens-Pfade Tabelle (Main Table für schnelle Navigation)
- [x] Seed Data: Minimal-Hierarchie für Testing
  ```
  Bibliothek: Programming, Medicine
  Kategorie: Python, C++, Anatomy
  Regal: Basics, Advanced
  Buch: "Python Lambda Guide" (1 Beispiel-Buch)
  Kapitel: Chapter 1-5
  Seiten: 50 Test-Seiten mit echtem Content
  ```

**Success Metric:**
✅ Ein kompletter Pfad existiert in DB:
```sql
SELECT * FROM wissens_pfade WHERE
  bibliothek_id = 1 AND  -- Programming
  kategorie_id = 101 AND -- Python
  regal_id = 201 AND     -- Advanced
  buch_id = 301 AND      -- Lambda Guide
  kapitel_id = 401 AND   -- Chapter 3
  seite_id = 5001;       -- Page 42
```

**Realitäts-Check:**
- Schema ist komplex, aber PostgreSQL ist dafür gemacht
- Indizes kosten Speicher (ca. +30% Overhead), aber Queries werden 10x schneller
- Migration von altem System: später via Batch-Job

---

## Phase 1: Hierarchical Embedder (Woche 3-4)

### Ziel: Jede Hierarchie-Ebene bekommt semantische Vektoren

**Kern-Idee:** Jede Ebene hat unterschiedliche Semantik!

**Bibliothek-Embedding:**
- Input: "Programming"
- Embedding: High-level, abstrakt
- Beispiel-Prompt: "Knowledge domain: Programming and Computer Science"

**Kategorie-Embedding:**
- Input: "Python" (im Kontext von "Programming")
- Embedding: Domain-spezifisch
- Beispiel-Prompt: "Programming → Python programming language"

**Seite-Embedding:**
- Input: Eigentlicher Content-Text
- Embedding: Konkret, detailreich
- Beispiel-Prompt: (der Text selbst)

**Deliverables:**
- [x] `HierarchicalEmbedder` Python Service
  ```python
  class HierarchicalEmbedder:
      def embed_bibliothek(name: str) -> List[int]  # 64D int16
      def embed_kategorie(bib_name: str, kat_name: str) -> List[int]
      def embed_regal(kat_name: str, regal_name: str) -> List[int]
      def embed_buch(regal_name: str, buch_titel: str) -> List[int]
      def embed_kapitel(buch_titel: str, kapitel_titel: str) -> List[int]
      def embed_seite(content: str) -> List[int]
  ```

- [x] Batch-Embedding Script für Seed Data
- [x] Vektor-Validation (alle 64D, int16 range, keine NaNs)

**Querdenker-Twist:**
💡 **Was wenn wir Ebenen-Kontext komprimieren?**

Statt jedem Buch-Embedding die komplette Hierarchie mitzugeben:
```
"Programming → Python → Advanced → Lambda Guide"  (lang, redundant)
```

Nutze **Parent-Vektor als Prefix**:
```python
# Buch-Embedding = Regal-Vektor (erste 32D) + Buch-Semantik (letzte 32D)
buch_vec = regal_vec[:32] + embed_buch_only(titel)[32:]
```

**Vorteil:** Hierarchie ist im Vektor codiert! Ähnliche Bücher im gleichen Regal haben automatisch ähnliche Vektoren.

**Nachteil:** Weniger Flexibilität (Buch kann nicht "semantisch weit" vom Regal sein)

**Entscheidung:** Teste beide Ansätze, messe Retrieval-Qualität

**Success Metric:**
✅ Alle Seed-Data Einträge haben Vektor-IDs
✅ Similarity-Test: "Python" ist näher an "Programming" als an "Medicine"

---

## Phase 2: Hierarchical Search Engine (Woche 5-6)

### Ziel: Top-Down Filtering von Bibliothek → Seite

**Algorithmus:**

```python
def hierarchical_search(
    query: str,
    max_depth: int = 6,
    top_k: List[int] = [1, 3, 3, 3, 5, 10]  # Pro Ebene
) -> List[SeiteID]:
    
    query_vec = embed_text(query)
    
    # Level 1: Bibliothek (global search)
    bib_candidates = vector_search(
        query_vec, 
        table='bibliotheken',
        top_k=top_k[0]  # Top-1 Bibliothek
    )
    
    # Level 2: Kategorie (nur in ausgewählten Bibliotheken)
    kat_candidates = vector_search(
        query_vec,
        table='kategorien',
        filter={'bibliothek_id': bib_candidates},
        top_k=top_k[1]  # Top-3 Kategorien
    )
    
    # Level 3-6: Analog weiter filtern...
    
    # Final: Top-10 Seiten
    return seite_candidates
```

**Key Insight:** Jeder Level **filtert** die Suchspace für den nächsten!

**Deliverables:**
- [x] `HierarchicalSearchEngine` Python Class
- [x] PostgreSQL Custom Functions für Vector-Search pro Ebene
- [x] Bruce Integration: `KnowledgeGuard` validiert Pfad-Tiefe

**Performance Optimization:**
```sql
-- EXPLAIN ANALYZE für jeden Level
-- Erwartung: Level 1-3 < 50ms, Level 4-6 < 100ms

-- Materialized View für häufige Pfade
CREATE MATERIALIZED VIEW top_pfade AS
SELECT bibliothek_id, kategorie_id, regal_id, COUNT(*) as frequency
FROM query_log
GROUP BY bibliothek_id, kategorie_id, regal_id
ORDER BY frequency DESC
LIMIT 1000;

REFRESH MATERIALIZED VIEW top_pfade;  -- Täglich
```

**Success Metric:**
✅ Query "Python Lambda Functions" findet richtige Seiten (Precision > 80%)
✅ Search-Zeit < 150ms (P95)
✅ Alle Zwischenschritte sind in `query_log` auditierbar

---

## Phase 3: Adaptive Zoom-Level (Woche 7-8)

### Ziel: Bruce entscheidet, auf welcher Ebene gestoppt wird

**Problem:** Manchmal braucht User "ganzes Buch", manchmal nur "eine Seite"

**Lösung:** Mindset Compiler bestimmt Zoom-Level basierend auf Intent

```python
# Query: "Gib mir einen Überblick über Python"
# → Zoom-Level = 2 (Kategorie-Ebene)
# → Lade: Kategorie-Beschreibung + Top-3 Regal-Summaries

# Query: "Wie schreibe ich Lambda mit Closure?"
# → Zoom-Level = 6 (Seiten-Ebene)
# → Lade: Top-10 spezifische Seiten
```

**Heuristiken:**

| Intent | Keywords | Zoom-Level | Was wird geladen |
|--------|----------|------------|------------------|
| Overview | "Überblick", "Einführung" | 2-3 | Kategorie/Regal |
| Learn | "Tutorial", "lernen" | 4-5 | Buch/Kapitel |
| Lookup | "Wie", "Syntax", "Beispiel" | 6 | Seiten |
| Code | "Schreib Code", "Implementiere" | 6 | Seiten + Code-Snippets |

**Deliverables:**
- [x] `ZoomLevelDecider` in Mindset Compiler
- [x] Content Assembly für verschiedene Levels
  ```python
  if zoom_level == 2:  # Kategorie
      return kategorie.description + top_regal_summaries
  elif zoom_level == 6:  # Seiten
      return concat(seiten_content)
  ```

**Success Metric:**
✅ "Überblick Python" → < 100KB Content (Summary)
✅ "Lambda Closure Syntax" → 10-50KB Content (Specific Pages)

---

## Phase 4: Multi-Tenant Bibliotheken (Woche 9-10)

### Ziel: Jeder User/Tenant hat eigene Bibliothek

**Use Cases:**
- **Shared Knowledge:** "Programming" Bibliothek für alle
- **Private Knowledge:** "Firma X Interna" nur für Firma X
- **Personal Knowledge:** User's persönliche Notizen

**Schema-Erweiterung:**

```sql
ALTER TABLE bibliotheken ADD COLUMN tenant_id UUID;
ALTER TABLE bibliotheken ADD COLUMN visibility TEXT DEFAULT 'public';
-- visibility: 'public', 'tenant_only', 'private'

CREATE POLICY bibliothek_access ON bibliotheken
  FOR SELECT
  USING (
    visibility = 'public' OR
    (visibility = 'tenant_only' AND tenant_id = current_setting('app.tenant_id')::UUID)
  );
```

**Bruce Guard Integration:**
```cpp
// KnowledgeRule erweitert um Tenant-Check
class TenantIsolationRule : public KnowledgeRule {
    bool allow_category(const CategoryPath& path, const std::string& user) {
        // Check: User darf diese Bibliothek sehen?
        auto tenant_id = extract_tenant(user);
        return db_->check_bibliothek_access(path.bibliothek_id, tenant_id);
    }
};
```

**Success Metric:**
✅ User A sieht nur seine Private + Public Bibliotheken
✅ User B sieht seine eigene Private Bibliothek (nicht A's)

---

## Phase 5: Living Knowledge (Woche 11-16)

### Ziel: Wissen wächst kontinuierlich & kontrolliert

**Indexer Pipeline:**

```python
# 1. Document Upload
doc = upload_pdf("python_async_tutorial.pdf")

# 2. Automatic Classification
classifier = HierarchicalClassifier()
predicted_path = classifier.predict(doc.text)
# → Bibliothek: Programming
# → Kategorie: Python
# → Regal: Advanced
# → Neues Buch: "Async/Await Tutorial"

# 3. Confidence Check
if classifier.confidence > 0.9:
    # Auto-Insert
    insert_buch(predicted_path, doc)
else:
    # Review Queue
    review_queue.add(doc, predicted_path, classifier.confidence)

# 4. Human Review (optional)
admin_approves(review_queue[0])
# → Buch wird eingefügt
# → Embeddings werden generiert
# → Sofort suchbar
```

**Wachstums-Strategie:**
- **Kern-Bibliotheken (Public):** Kuratiert, hohe Qualität
- **Crowd-Sourced Content:** Review Queue, Community-Voting
- **AI-Generated Summaries:** Automatisch generierte Kapitel-Zusammenfassungen

**Success Metric:**
✅ 1000+ Seiten pro Woche hinzugefügt
✅ < 5% False Positives (falsch klassifiziert)
✅ Review Queue < 100 Items (bearbeitbar)

---

## Phase 6: Semantic Cross-References (Woche 17+)

### Ziel: Bücher verlinken sich gegenseitig (wie Wikipedia)

**Idee:** Seite über "Python Lambda" verlinkt auf Seite über "Closures"

**Implementierung:**

```sql
CREATE TABLE seiten_referenzen (
    von_seite_id INT REFERENCES seiten(id),
    zu_seite_id INT REFERENCES seiten(id),
    referenz_typ TEXT,  -- 'related', 'prerequisite', 'advanced'
    auto_generated BOOLEAN DEFAULT FALSE
);

-- Automatische Referenzen via Embedding-Ähnlichkeit
INSERT INTO seiten_referenzen (von_seite_id, zu_seite_id, referenz_typ)
SELECT 
    s1.id, 
    s2.id, 
    'related'
FROM seiten s1
CROSS JOIN seiten s2
WHERE s1.id != s2.id
  AND vector_similarity(s1.vektor_id, s2.vektor_id) > 0.85
LIMIT 10000;
```

**LLM Integration:**
```python
# Beim Content Assembly:
seite_content = load_seite(5001)
referenzen = load_referenzen(5001)

llm_prompt = f"""
Content:
{seite_content}

Related Topics:
{'\n'.join(ref.titel for ref in referenzen)}

User Question: {query}
Answer:
"""
```

**Success Metric:**
✅ Jede Seite hat 3-10 sinnvolle Referenzen
✅ User-Feedback: "Hilfreiche Querverweise" > 80%

---

## Technologie-Stack (Final)

### Bruce Core (C++ - bleibt unverändert!)
- Deterministische State Machine (7D Vektoren)
- Rule Engine für Knowledge Access
- Audit Logging

### Knowledge Layer (neu)
- **PostgreSQL 16 + pgvector:** Hierarchische Tabellen + Vektor-Indizes
- **Python Services:**
  - Hierarchical Embedder (Ollama Integration)
  - Search Engine
  - Indexer Pipeline
  - Review Queue Manager
- **Redis:** Cache für Top-Pfade, Session-Daten

### IPC
- Unix Domain Sockets (< 1ms Latenz)
- Oder: gRPC (bei Multi-Server Deployment)

### Observability
- PostgreSQL Query Logs → Grafana
- Bruce Audit Logs → eigenes Monitoring
- Prometheus Metrics: Search Latency, Hit Rate, Cache Performance

---

## Entscheidungspunkte

### A) Ebenen-Anzahl: 7 oder weniger?

**Option 1:** Volle 7 Ebenen (wie geplant)
- Pro: Maximum Granularität
- Con: Mehr DB-Queries, mehr Overhead

**Option 2:** Nur 5 Ebenen (Bibliothek/Kategorie/Buch/Kapitel/Seite)
- Pro: Einfacher, schneller
- Con: Weniger Struktur

**Empfehlung:** Start mit 7, collapse später bei Bedarf
- Materialized Views können Ebenen zusammenfassen
- "Regal" kann optional sein (NULL erlauben)

### B) Vektor-Dimensionen: 64 oder 1024?

**Reality Check:**
- Ollama nomic-embed-text: **768D** (Standard)
- Quantisierung zu int16: **funktioniert bis ~256D** (danach zu viel Informationsverlust)

**Empfehlung:** 
- **128D int16** (Kompromiss zwischen Qualität und Byte-Efficiency)
- Teste mit 64D, 128D, 256D → messe Precision@10

### C) Content-Storage: PostgreSQL oder S3?

**Seiten-Content:**
- < 1MB pro Seite → PostgreSQL TEXT Column (OK)
- Große PDFs/Videos → S3 + URL in PostgreSQL

**Empfehlung:** Hybrid
- Textuelle Seiten: PostgreSQL
- Binaries (PDFs, Videos): S3 oder File-System + FK

---

## Risiken & Mitigationen

### Risiko 1: Komplexität

**Problem:** 7 Tabellen + Vektoren + Referenzen = viele Moving Parts
**Mitigation:**
- Start Simple: Nur 3 Ebenen first (Bibliothek/Kategorie/Seite)
- Add Layers progressiv
- Automatisierte Tests für jede Ebene

### Risiko 2: Hierarchie zu starr

**Problem:** Was wenn Buch in mehrere Regale passt?
**Mitigation:**
- **Soft-Hierarchie:** Buch kann mehrere `regal_id` haben (many-to-many)
- **Tag-System:** Zusätzlich zu Hierarchie (hybrid)

### Risiko 3: Embedding-Drift

**Problem:** Ollama-Modell Update → alle Vektoren ändern sich
**Mitigation:**
- **Versionierung:** `vektoren.source` speichert Modell-Hash
- **Re-Embedding Pipeline:** Batch-Job rechnet bei Modell-Update neu

---

## Success Criteria (Gesamt)

✅ **Funktional:**
- User fragt: "Python Lambda Functions Tutorial"
- System navigiert: Programming → Python → Advanced → Lambda Guide → Chapter 3 → Seite 42
- LLM bekommt: 10 relevante Seiten (50KB statt 100GB)
- Antwort ist korrekt, in Deutsch, mit Code-Beispiel

✅ **Non-Funktional:**
- Search-Zeit < 150ms (P95)
- 99.9% Uptime
- Deterministisch (gleiche Query → gleiche Results)
- Offline-fähig (kein Internet nötig)

✅ **Architektur:**
- Bruce Core bleibt < 10k LoC
- Hierarchie ist wartbar (neue Ebene hinzufügen = 1 SQL Migration)
- System skaliert auf 10M+ Seiten
- Audit Trail für jede Query

---

## Nächste Schritte (Priorisiert)

**SOFORT (heute):**
1. Lies IMPLEMENTATION_PLAN_V2.md (detailliertes Tech-Design)
2. Lies CLAUDE_CODE_START_PROMPT_V2.md (Ready-to-paste)
3. Setup PostgreSQL + pgvector lokal

**TAG 1-2:**
1. Erstelle hierarchisches Schema (002_hierarchie.sql)
2. Seed Data einfügen (minimal: 1 kompletter Pfad)
3. Test: SELECT * FROM wissens_pfade WHERE ...

**WOCHE 1:**
1. Hierarchical Embedder bauen
2. Embed Seed Data
3. Test: Vector-Search auf Bibliothek-Ebene

**WOCHE 2:**
1. Search Engine implementieren
2. Bruce Integration (KnowledgeGuard erweitern)
3. Ende-zu-Ende Test: Query → Seiten

**WOCHE 3-4:**
1. Indexer Pipeline
2. Review Queue
3. 100+ Real Docs einlesen

**Danach:** Production Hardening, Performance Tuning, Multi-Tenant

---

*"Die Bibliothek ist keine Metapher - sie ist das System."*
