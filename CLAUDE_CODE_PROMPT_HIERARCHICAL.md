# CLAUDE_CODE_PROMPT_HIERARCHICAL.md
# Claude Code Start: Bruce Hierarchical Knowledge Library

## 🎯 Mission Statement

Du baust das **hierarchische Wissenssystem** für Bruce - ein System das funktioniert wie die **Library of Congress meets Google Search**: Strukturiert navigierbar (via IDs) UND semantisch intelligent (via Vektoren).

**Deine Aufgabe:** Verwandle "flache Vektor-Suppe" in eine **navigierbare 6-Level Bibliothek** wo jede Ebene (Bibliothek → Kategorie → Regal → Buch → Kapitel → Seite) sowohl als ID existiert (deterministisch) als auch als 64D Vektor (semantisch suchbar).

**Warum das brillant ist:** Statt 10 Millionen Vektoren zu scannen, reduziert jede Ebene den Suchraum um Faktor 10-100. **Cascade Filtering** = 100-1000x schneller als Flat Search!

---

## 🧠 Das Paradigma verstehen (Querdenker-Perspektive)

### Flat Vector DBs (alle machen es so)S

```
❌ Problem:
10M Chunks als flache Liste
→ Jede Query scannt ALLES (auch mit HNSW Index)
→ Keine Struktur, keine Navigation
→ "Wo bin ich gerade?" ist unmöglich zu beantworten
→ Budget-Kontrolle? Vergiss es.
```

### Hierarchical Library (wie DU es machst)

```
✅ Lösung:
Bibliothek: "Programming" (10 Domains total)
  ↓ Vektor-Match → 1-2 Bibliotheken
Kategorie: "Python" (100 Topics total, aber nur in "Programming")
  ↓ Vektor-Match → 3-5 Kategorien
Regal: "Advanced Features" (500 total, aber nur in "Python")
  ↓ Vektor-Match → 5-10 Regale
Buch: "Lambda Functions Guide" (2000 total, gefiltert)
  ↓ Vektor-Match → 3-5 Bücher
Kapitel: "Introduction" (10K total, gefiltert)
  ↓ Vektor-Match → 5-10 Kapitel
Seite: "Lambda syntax example" (50K total, gefiltert)
  ↓ Final Top-10 Seiten

RESULTAT: 10M → 10 in 6 Schritten!
Jede Ebene hat eigenen Vektor (abstrakt → konkret)
Jede Ebene filtered die nächste → Cascade Filtering
```

**Die Metapher:** Stell dir vor du suchst ein Buch in einer echten Bibliothek:
1. Welches Gebäude? (Bibliothek)
2. Welcher Stock? (Kategorie)
3. Welcher Gang? (Regal)
4. Welches Buch? (Buch)
5. Welches Kapitel? (Kapitel)
6. Welche Seite? (Seite)

Du gehst **nicht** jeden Gang in jedem Stock in jedem Gebäude ab - du filterst schrittweise!

---

## ⚙️ Was du baust (Komponenten)

### 1. PostgreSQL Schema (6 Hierarchie-Tabellen + 1 Vektor-Pool)

```
bibliotheken → kategorien → regale → buecher → kapitel → seiten
      ↓            ↓           ↓         ↓         ↓         ↓
   vektor_id    vektor_id   vektor_id  ...      ...      vektor_id
      ↓____________↓___________↓___________↓_____↓_______↓
                         vektoren (64D int16)
```

**Key Insight:** Jede Ebene hat eigene Tabelle + eigenen Vektor-Typ!
- Bibliothek-Vektor: "Programming" (sehr abstrakt)
- Seite-Vektor: "lambda x: x**2" (sehr konkret)

### 2. Hierarchical Search Engine (Python)

```python
def search(query, max_depth=6):
    results = {}
    filter = None  # Start ohne Filter
    
    for level in [Bibliothek, Kategorie, Regal, Buch, Kapitel, Seite]:
        # 1. Embed Query für DIESE Ebene (Kontext wichtig!)
        query_vec = embed_for_level(query, level, context=results)
        
        # 2. Suche Top-K in DB (MIT Filter von vorheriger Ebene!)
        candidates = vector_search(
            table=level,
            vec=query_vec,
            filter=filter,  # ← Das ist der Trick!
            top_k=K[level]
        )
        
        # 3. Update Filter für nächste Ebene
        results[level] = candidates
        filter = {parent_fk: [c.id for c in candidates]}
    
    return results[Seite]  # Final: Nur relevante Seiten!
```

**Performance-Magie:**
- Ohne Filter: 10M Seiten scannen → 5000ms
- Mit Cascade Filter: 10 + 100 + 500 + 2000 + 10K + 50K = 62K Vektoren → 150ms
- **Speedup: 33x!** (und das skaliert!)

### 3. Bruce Integration (C++)

```cpp
// Bruce's 7D State mapped zu Hierarchie
struct HierarchicalPath {
    uint32_t bibliothek_id;  // Von State.vec[0] abgeleitet
    uint32_t kategorie_id;   // Von State.vec[1] abgeleitet
    uint32_t regal_id;       // Von State.vec[2] abgeleitet
    // ...
    uint32_t vektoren_id;    // Pointer zu 64D Embedding
};

// Bruce validiert Pfade (Guard!)
class HierarchicalGuard {
    bool allow_path(HierarchicalPath path);
    bool allow_budget(float buecher_mb, uint32_t seiten_count);
};
```

**Bruce bleibt der Wächter** - er entscheidet was erlaubt ist, aber navigiert nicht selbst!

---

## 🚀 Deine ersten 7 Tage (Task-by-Task)

### TAG 1: PostgreSQL Setup (2-3h)

**Ziel:** Datenbank läuft mit allen Tabellen + Seed Data

**Tasks:**

1. **Start PostgreSQL + pgvector via Docker**
   ```bash
   docker run -d \
     --name bruce-postgres \
     -e POSTGRES_DB=bruce_knowledge \
     -e POSTGRES_USER=bruce \
     -e POSTGRES_PASSWORD=dev_secret \
     -p 5433:5433 \
     pgvector/pgvector:pg16
   ```

2. **Run Migration**
   ```bash
   # Die Migration ist in IMPLEMENTATION_PLAN_HIERARCHICAL.md
   psql -h localhost -U bruce -d bruce_knowledge -f knowledge/migrations/002_hierarchical_library_schema.sql
   ```
   
   **Wichtig:** Die Migration erstellt:
   - 7 Tabellen (bibliotheken, kategorien, regale, buecher, kapitel, seiten, vektoren)
   - Seed Data (1 kompletter Pfad: Programming → Python → Advanced → Lambda Guide → Chapter 1 → Page 1)
   - Materialized View (wissens_pfade - für schnelle Navigation)

3. **Verify Setup**
   ```sql
   -- Check Tabellen
   \dt
   -- Sollte zeigen: bibliotheken, kategorien, regale, buecher, kapitel, seiten, vektoren
   
   -- Check Seed Data
   SELECT * FROM wissens_pfade;
   -- Sollte 1 Zeile zeigen mit komplettem Pfad
   
   -- Check Vektor-Funktion
   SELECT id, ebene FROM vektoren;
   -- Sollte 6 Zeilen (je 1 pro Ebene) zeigen
   ```

**Success Criteria:**
- ✅ PostgreSQL läuft
- ✅ 7 Tabellen existieren
- ✅ `wissens_pfade` View zeigt 1 Pfad
- ✅ Keine SQL Errors

**Was wenn es nicht klappt?**
- Error: "extension vector does not exist" → Docker Image falsch, nutze `pgvector/pgvector:pg16`
- Error: Migration fails → Check ob alle DDL Statements korrekt sind
- Seed Data empty → Check ob `DO $$` Block gelaufen ist

---

### TAG 2: Hierarchical Embedder (Python, 3-4h)

**Ziel:** Service der Texte → 64D Vektoren macht (für jede Ebene anders!)

**Files zu erstellen:**

1. **`knowledge/services/hierarchical_embedder.py`**
   - Copy vollständigen Code aus IMPLEMENTATION_PLAN_HIERARCHICAL.md
   - Funktionen:
     ```python
     embed_bibliothek(name: str) -> List[int]  # 64D int16
     embed_kategorie(bib_name: str, kat_name: str) -> List[int]
     embed_regal(kat_kontext: str, regal_name: str) -> List[int]
     embed_buch(regal_kontext: str, titel: str) -> List[int]
     embed_kapitel(buch_kontext: str, kap_titel: str) -> List[int]
     embed_seite(kap_kontext: str, inhalt: str) -> List[int]
     ```

2. **Install Dependencies**
   ```bash
   pip install ollama numpy psycopg2-binary
   ```

3. **Setup Ollama**
   ```bash
   # Install Ollama
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Pull Embedding Model
   ollama pull nomic-embed-text
   
   # Test
   ollama run nomic-embed-text "test embedding"
   ```

4. **Test Embedder**
   ```python
   # knowledge/tests/test_embedder.py
   from services.hierarchical_embedder import HierarchicalEmbedder
   
   def test_embedder():
       embedder = HierarchicalEmbedder()
       
       # Test Bibliothek Embedding
       vec = embedder.embed_bibliothek("Programming", "Software Development")
       assert len(vec) == 64
       assert all(isinstance(x, int) for x in vec)
       assert all(-32767 <= x <= 32767 for x in vec)
       print(f"✓ Bibliothek Vector: {vec[:5]}...")
       
       # Test Kategorie Embedding (mit Kontext!)
       vec_kat = embedder.embed_kategorie("Programming", "Python")
       assert len(vec_kat) == 64
       print(f"✓ Kategorie Vector: {vec_kat[:5]}...")
       
       # Important: Vektoren sollten unterschiedlich sein!
       assert vec != vec_kat, "Vectors should differ!"
       
   if __name__ == "__main__":
       test_embedder()
       print("\n✅ Embedder tests passed!")
   ```

**Success Criteria:**
- ✅ Ollama läuft lokal
- ✅ Alle 6 Embedding-Funktionen implementiert
- ✅ Test generiert 64D int16 Vektoren
- ✅ Bibliothek-Vec ≠ Kategorie-Vec (unterschiedliche Semantik!)

**Querdenker-Check:** Warum brauchen wir 6 verschiedene Embedding-Funktionen?
- **Antwort:** Weil **Kontext** wichtig ist!
  - "Python" alleine → generisches Embedding
  - "Python im Kontext von Programming" → spezifischer
  - "Lambda Functions im Kontext von Python Advanced Features" → sehr spezifisch
- Das erlaubt bessere Matches auf jeder Ebene!

---

### TAG 3: Hierarchical Search Engine - MVP (4-5h)

**Ziel:** Cascade Filtering funktioniert (erstmal nur 3 Ebenen als MVP)

**Simplification:** Starte mit 3 Ebenen (Bibliothek → Kategorie → Seite) statt 6
- Weniger Komplexität für ersten Test
- Konzept-Beweis wichtiger als Vollständigkeit
- Später auf 6 erweitern

**File:** `knowledge/services/hierarchical_search_mvp.py`

```python
"""
Hierarchical Search MVP - Nur 3 Ebenen als Proof-of-Concept
"""

from typing import List, Dict
from dataclasses import dataclass
import psycopg2
import numpy as np
from hierarchical_embedder import HierarchicalEmbedder


@dataclass
class SearchResult:
    id: int
    name: str
    similarity: float


class HierarchicalSearchMVP:
    """Simplified 3-Level Search"""
    
    def __init__(self, db_connection, embedder: HierarchicalEmbedder):
        self.db = db_connection
        self.embedder = embedder
    
    def _cosine_similarity(self, vec_a: List[int], vec_b: List[int]) -> float:
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        return float(dot / (norm_a * norm_b)) if norm_a and norm_b else 0.0
    
    def search(self, query_text: str) -> Dict:
        """3-Level Cascade Search"""
        import time
        start = time.time()
        
        # ============================================
        # LEVEL 1: BIBLIOTHEK
        # ============================================
        
        query_vec_bib = self.embedder.embed_bibliothek(query_text)
        
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT b.id, b.name, v.dims
            FROM bibliotheken b
            JOIN vektoren v ON b.vektor_id = v.id
        """)
        
        bibliotheken = []
        for row in cursor.fetchall():
            bib_id, bib_name, dims = row
            sim = self._cosine_similarity(query_vec_bib, dims)
            bibliotheken.append(SearchResult(bib_id, bib_name, sim))
        
        bibliotheken.sort(key=lambda b: b.similarity, reverse=True)
        top_bib = bibliotheken[0]  # Nehme beste Bibliothek
        
        print(f"Level 1 (Bibliothek): {top_bib.name} (sim={top_bib.similarity:.3f})")
        
        # ============================================
        # LEVEL 2: KATEGORIE (gefiltert!)
        # ============================================
        
        query_vec_kat = self.embedder.embed_kategorie(top_bib.name, query_text)
        
        cursor.execute("""
            SELECT k.id, k.name, v.dims
            FROM kategorien k
            JOIN vektoren v ON k.vektor_id = v.id
            WHERE k.bibliothek_id = %s
        """, (top_bib.id,))  # ← Hier das Filtering!
        
        kategorien = []
        for row in cursor.fetchall():
            kat_id, kat_name, dims = row
            sim = self._cosine_similarity(query_vec_kat, dims)
            kategorien.append(SearchResult(kat_id, kat_name, sim))
        
        kategorien.sort(key=lambda k: k.similarity, reverse=True)
        top_kat = kategorien[0] if kategorien else None
        
        if not top_kat:
            return {"error": "Keine Kategorie gefunden"}
        
        print(f"Level 2 (Kategorie): {top_kat.name} (sim={top_kat.similarity:.3f})")
        
        # ============================================
        # LEVEL 3: SEITEN (gefiltert!)
        # ============================================
        
        # Hole alle Seiten in dieser Kategorie (via JOINs)
        cursor.execute("""
            SELECT s.id, s.inhalt, v.dims
            FROM seiten s
            JOIN kapitel kap ON s.kapitel_id = kap.id
            JOIN buecher bu ON kap.buch_id = bu.id
            JOIN regale r ON bu.regal_id = r.id
            WHERE r.kategorie_id = %s
            LIMIT 100  # Safety
        """, (top_kat.id,))
        
        query_vec_seite = self.embedder.embed_seite(top_kat.name, query_text)
        
        seiten = []
        for row in cursor.fetchall():
            seite_id, inhalt, dims = row
            sim = self._cosine_similarity(query_vec_seite, dims)
            seiten.append({
                "id": seite_id,
                "inhalt": inhalt,
                "similarity": sim
            })
        
        seiten.sort(key=lambda s: s['similarity'], reverse=True)
        top_seiten = seiten[:5]  # Top-5
        
        end = time.time()
        
        return {
            "query": query_text,
            "pfad": {
                "bibliothek": top_bib.name,
                "kategorie": top_kat.name if top_kat else None
            },
            "seiten": top_seiten,
            "anzahl": len(top_seiten),
            "dauer_ms": int((end - start) * 1000)
        }


# ============================================
# TEST
# ============================================

if __name__ == "__main__":
    import psycopg2
    
    db_conn = psycopg2.connect(
        "postgresql://bruce:dev_secret@localhost:5433/bruce_knowledge"
    )
    embedder = HierarchicalEmbedder()
    search = HierarchicalSearchMVP(db_conn, embedder)
    
    # Test Search
    results = search.search("Python Lambda Functions")
    
    print(f"\n=== SEARCH RESULTS ===")
    print(f"Query: {results['query']}")
    print(f"Duration: {results['dauer_ms']}ms")
    print(f"Path: {results['pfad']['bibliothek']} → {results['pfad']['kategorie']}")
    print(f"\nTop Seiten:")
    for i, seite in enumerate(results['seiten'][:3], 1):
        print(f"{i}. {seite['inhalt'][:100]}... (sim={seite['similarity']:.3f})")
```

**Test Script:** `knowledge/scripts/test_search_mvp.sh`

```bash
#!/bin/bash
set -e

echo "=== Testing Hierarchical Search MVP ==="

# 1. Check DB Connection
echo "1. Checking PostgreSQL..."
psql -h localhost -U bruce -d bruce_knowledge -c "SELECT COUNT(*) FROM bibliotheken;" || exit 1

# 2. Check Ollama
echo "2. Checking Ollama..."
ollama list | grep nomic-embed-text || exit 1

# 3. Run Search Test
echo "3. Running Search..."
python knowledge/services/hierarchical_search_mvp.py

echo ""
echo "✅ All tests passed!"
```

**Success Criteria:**
- ✅ Search findet "Programming" Bibliothek
- ✅ Dann "Python" Kategorie (gefiltert!)
- ✅ Dann relevante Seiten (gefiltert!)
- ✅ Latenz < 500ms
- ✅ Console output zeigt Cascade (Level 1 → 2 → 3)

---

### TAG 4: Bruce C++ Integration - Guard (3-4h)

**Ziel:** Bruce validiert Hierarchie-Pfade

**Files:**

1. **`include/bruce/knowledge/hierarchical_guard.hpp`**
   - Copy aus IMPLEMENTATION_PLAN_HIERARCHICAL.md
   - Key Klassen:
     - `HierarchicalPath` (7 Ebenen als struct)
     - `HierarchicalManifest` (Query + Constraints)
     - `HierarchicalGuard` (Rule Validator)

2. **`src/hierarchical_guard.cpp`**
   ```cpp
   #include "bruce/knowledge/hierarchical_guard.hpp"
   #include <sstream>
   
   namespace bruce::knowledge {
   
   std::string HierarchicalManifest::to_json() const {
       std::ostringstream oss;
       oss << "{\n";
       oss << "  \"query_id\": \"" << query_id << "\",\n";
       oss << "  \"query_text\": \"" << query_text << "\",\n";
       oss << "  \"allowed_bibliothek_ids\": [";
       for (size_t i = 0; i < allowed_bibliothek_ids.size(); ++i) {
           if (i > 0) oss << ", ";
           oss << allowed_bibliothek_ids[i];
       }
       oss << "],\n";
       oss << "  \"max_buecher_mb\": " << max_buecher_mb << ",\n";
       oss << "  \"max_seiten\": " << max_seiten << ",\n";
       oss << "  \"max_depth\": " << max_depth << "\n";
       oss << "}\n";
       return oss.str();
   }
   
   } // namespace bruce::knowledge
   ```

3. **`tests/test_hierarchical_guard.cpp`**
   - Copy aus IMPLEMENTATION_PLAN_HIERARCHICAL.md
   - Tests:
     - Bibliothek Whitelist funktioniert
     - Budget-Limit wird enforced
     - State Mapping funktioniert

4. **Update `CMakeLists.txt`**
   ```cmake
   # Add Hierarchical Knowledge Library
   add_library(bruce_hierarchical_knowledge
       src/hierarchical_guard.cpp
   )
   target_include_directories(bruce_hierarchical_knowledge PUBLIC include)
   target_link_libraries(bruce_hierarchical_knowledge PRIVATE bruce_core)
   
   # Test
   add_executable(test_hierarchical_guard
       tests/test_hierarchical_guard.cpp
   )
   target_link_libraries(test_hierarchical_guard PRIVATE bruce_hierarchical_knowledge)
   ```

**Build & Test:**
```bash
cmake -S . -B out/build/x64-Debug -G Ninja
cmake --build out/build/x64-Debug
./out/build/x64-Debug/test_hierarchical_guard
```

**Success Criteria:**
- ✅ Code kompiliert ohne Warnings
- ✅ Alle Tests passen (5 Tests)
- ✅ Guard blockiert ungültige Bibliothek
- ✅ Guard blockiert Budget-Überschreitung
- ✅ State wird korrekt zu Path gemappt

---

### TAG 5: IPC Bridge - C++ ↔ Python (3h)

**Ziel:** Bruce (C++) kann Python Search Service aufrufen

**Approach:** Unix Domain Socket (einfachste Variante für MVP)

**Python Server:** `knowledge/services/socket_server.py`

```python
import socket
import json
import os
from hierarchical_search_mvp import HierarchicalSearchMVP, HierarchicalEmbedder
import psycopg2

SOCKET_PATH = "/tmp/bruce_hierarchical_search.sock"

def main():
    # Remove old socket
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)
    
    # Setup
    db_conn = psycopg2.connect(
        "postgresql://bruce:dev_secret@localhost:5433/bruce_knowledge"
    )
    embedder = HierarchicalEmbedder()
    search_engine = HierarchicalSearchMVP(db_conn, embedder)
    
    # Create socket
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(SOCKET_PATH)
    sock.listen(5)
    
    print(f"✓ Listening on {SOCKET_PATH}")
    
    while True:
        conn, _ = sock.accept()
        
        try:
            # Receive request
            data = conn.recv(65536).decode('utf-8')
            request = json.loads(data)
            
            query_text = request.get('query_text', '')
            
            # Search
            results = search_engine.search(query_text)
            
            # Send response
            response = json.dumps(results)
            conn.sendall(response.encode('utf-8'))
            
        except Exception as e:
            error_response = json.dumps({"error": str(e)})
            conn.sendall(error_response.encode('utf-8'))
        
        finally:
            conn.close()

if __name__ == "__main__":
    main()
```

**C++ Client Test:** `tests/test_ipc_hierarchical.cpp`

```cpp
#include "bruce/knowledge/ipc_client.hpp"  // Nutze existing IPC Client
#include "bruce/io/minijson.hpp"
#include <iostream>

int main() {
    try {
        // Connect
        bruce::knowledge::UnixSocketClient client("/tmp/bruce_hierarchical_search.sock");
        
        // Build Request
        std::string request = R"({
            "query_text": "Python Lambda Functions"
        })";
        
        // Send
        std::cout << "Sending query...\n";
        std::string response_str = client.send_request(request);
        
        // Parse Response
        auto response = bruce::io::minijson::parse(response_str);
        
        std::cout << "\n=== RESPONSE ===\n";
        std::cout << "Query: " << response.at("query").s << "\n";
        std::cout << "Duration: " << response.at("dauer_ms").i << "ms\n";
        std::cout << "Seiten found: " << response.at("anzahl").i << "\n";
        
        // Path
        auto pfad = response.at("pfad");
        std::cout << "Path: " << pfad.at("bibliothek").s << " → " 
                  << pfad.at("kategorie").s << "\n";
        
        // Top Seiten
        auto seiten = response.at("seiten");
        std::cout << "\nTop Seiten:\n";
        for (size_t i = 0; i < std::min(size_t(3), seiten.a.size()); ++i) {
            auto& seite = seiten.a[i];
            std::cout << "  " << (i+1) << ". " 
                      << seite.at("inhalt").s.substr(0, 80) << "...\n"
                      << "     Similarity: " << seite.at("similarity").i << "\n";
        }
        
        std::cout << "\n✅ IPC Test passed!\n";
        return 0;
        
    } catch (const std::exception& e) {
        std::cerr << "❌ Error: " << e.what() << "\n";
        return 1;
    }
}
```

**Test:**
```bash
# Terminal 1: Start Python Server
python knowledge/services/socket_server.py

# Terminal 2: Run C++ Client
./out/build/x64-Debug/test_ipc_hierarchical
```

**Success Criteria:**
- ✅ Socket Server läuft
- ✅ C++ Client verbindet sich
- ✅ Request wird gesendet (JSON)
- ✅ Response kommt zurück (Seiten!)
- ✅ Latenz < 1000ms (inkl. IPC Overhead)

---

### TAG 6-7: End-to-End Integration (6-8h)

**Ziel:** Kompletter Flow: User Query → Bruce → Search → Response

**File:** `tests/test_e2e_hierarchical.cpp`

```cpp
#include "bruce/knowledge/hierarchical_guard.hpp"
#include "bruce/knowledge/ipc_client.hpp"
#include "bruce/core/state/state_store.hpp"
#include "bruce/io/minijson.hpp"
#include <iostream>
#include <cassert>

using namespace bruce::knowledge;
using namespace bruce::core;

int main() {
    std::cout << "=== END-TO-END HIERARCHICAL TEST ===\n\n";
    
    // ============================================
    // SETUP
    // ============================================
    
    // 1. Bruce State Store
    StateStore store;
    store.create(1, {7000, 6000, 0, 0, 4000, 0, 6000}, "bruce_v6");
    
    // 2. Hierarchical Guard mit Rules
    HierarchicalGuard guard;
    guard.add_rule(std::make_unique<BibliothekWhitelistRule>(
        std::vector<std::uint32_t>{1}  // Nur "Programming" erlaubt
    ));
    guard.add_rule(std::make_unique<BudgetLimitRule>(
        100.0f,  // Max 100MB
        20       // Max 20 Seiten
    ));
    
    // 3. IPC Client
    UnixSocketClient ipc_client("/tmp/bruce_hierarchical_search.sock");
    
    // ============================================
    // USER QUERY
    // ============================================
    
    std::string user_query = "Schreib mir Python Code für Lambda Functions";
    std::cout << "User Query: \"" << user_query << "\"\n\n";
    
    // ============================================
    // BRUCE: COMPILE MANIFEST
    // ============================================
    
    // Map Query zu State (vereinfacht: nehme ersten State)
    const auto* state = store.get(1);
    assert(state != nullptr);
    
    // Map State zu Hierarchical Path
    HierarchicalPath path = StateToHierarchyMapper::map(*state);
    std::cout << "Bruce mapped to: " << path.to_string() << "\n";
    
    // Build Manifest
    HierarchicalManifest manifest;
    manifest.query_id = "test-e2e-001";
    manifest.query_text = user_query;
    manifest.allowed_bibliothek_ids = {*path.bibliothek_id};
    manifest.max_buecher_mb = 50.0f;
    manifest.max_seiten = 10;
    manifest.max_depth = 3;  // MVP: Nur 3 Ebenen
    
    // Validate
    assert(guard.validate_manifest(manifest));
    std::cout << "✓ Manifest validated by Guard\n\n";
    
    // ============================================
    // SEARCH: FETCH KNOWLEDGE
    // ============================================
    
    std::cout << "Sending to Search Service...\n";
    
    std::string search_request = R"({
        "query_text": ")" + user_query + R"("
    })";
    
    std::string response_str = ipc_client.send_request(search_request);
    auto response = bruce::io::minijson::parse(response_str);
    
    std::cout << "✓ Got response in " << response.at("dauer_ms").i << "ms\n\n";
    
    // ============================================
    // RESULTS
    // ============================================
    
    auto pfad = response.at("pfad");
    std::cout << "Search Path:\n";
    std::cout << "  Bibliothek: " << pfad.at("bibliothek").s << "\n";
    std::cout << "  Kategorie:  " << pfad.at("kategorie").s << "\n\n";
    
    auto seiten = response.at("seiten");
    int anzahl = response.at("anzahl").i;
    
    std::cout << "Found " << anzahl << " Seiten:\n";
    for (int i = 0; i < std::min(3, (int)seiten.a.size()); ++i) {
        auto& seite = seiten.a[i];
        std::cout << "\n" << (i+1) << ". Seite ID " << seite.at("id").i << ":\n";
        std::cout << "   " << seite.at("inhalt").s.substr(0, 150) << "...\n";
        std::cout << "   Similarity: " << seite.at("similarity").i << "\n";
    }
    
    // ============================================
    // VERIFY
    // ============================================
    
    // Check: Anzahl im Budget?
    assert(anzahl <= manifest.max_seiten);
    std::cout << "\n✓ Budget respected (" << anzahl << " <= " << manifest.max_seiten << ")\n";
    
    // Check: Path erlaubt?
    assert(pfad.at("bibliothek").s == "Programming");  // Nur Programming erlaubt
    std::cout << "✓ Path within allowed bibliothek\n";
    
    // Check: Latenz OK?
    assert(response.at("dauer_ms").i < 1000);
    std::cout << "✓ Latency OK (" << response.at("dauer_ms").i << "ms < 1000ms)\n";
    
    std::cout << "\n🎉 END-TO-END TEST PASSED! 🎉\n";
    return 0;
}
```

**Success Criteria:**
- ✅ Query läuft durch alle Komponenten
- ✅ Bruce validated Manifest
- ✅ Search liefert Seiten
- ✅ Budget wird eingehalten
- ✅ Latenz < 1000ms
- ✅ Results sind deterministisch (wiederholbar)

---

## 📊 Was du nach 7 Tagen hast

### Funktional
✅ PostgreSQL mit 6-Level Hierarchie  
✅ Python Search Engine (3-Level MVP)  
✅ Bruce Guard validiert Pfade  
✅ IPC Bridge (C++ ↔ Python)  
✅ End-to-End Flow funktioniert  

### Non-Funktional
✅ Latenz < 1000ms (bereits gute Baseline)  
✅ Deterministisch (gleiche Query → gleiche Results)  
✅ Offline (keine API Calls)  
✅ Auditierbar (Query Log)  

### Architektur
✅ Klare Modul-Grenzen  
✅ Bruce bleibt < 12k LoC  
✅ PostgreSQL als Single Source of Truth  
✅ Testbar (5+ Unit Tests, 3+ Integration Tests)  

---

## 🔥 Wichtige Prinzipien (nie vergessen!)

### 1. Cascade Filtering ist der Schlüssel
```
❌ FALSCH: Alle Ebenen parallel suchen
✅ RICHTIG: Level-by-Level mit Filter

Warum? Weil jede Ebene die nächste um Faktor 10-100 reduziert!
```

### 2. Kontext ist essentiell
```
❌ FALSCH: Gleiche Query-Embedding für alle Ebenen
✅ RICHTIG: Ebenen-spezifische Embeddings mit Kontext

Bibliothek: "Programming" (abstrakt)
Kategorie: "Python im Kontext von Programming" (spezifischer)
Seite: "Lambda Functions im Kontext von Python Advanced" (sehr spezifisch)
```

### 3. Budget early, budget often
```
❌ FALSCH: Erst alle Seiten holen, dann filtern
✅ RICHTIG: Budget auf Buch-Ebene prüfen

Warum? Weil wir nicht 10GB Content holen wollen nur um dann 100MB zu nutzen!
```

### 4. Bruce bleibt dumm
```
❌ FALSCH: Bruce macht Vektor-Suche selbst
✅ RICHTIG: Bruce validiert nur (Guard!)

Bruce sagt "erlaubt" oder "verboten", aber sucht nicht selbst.
Python Service macht die eigentliche Arbeit.
```

---

## 🤔 Wenn du stuck bist...

### Problem: "Vektor-Search findet nichts!"
**Debug:**
```sql
-- Check: Sind Vektoren in DB?
SELECT COUNT(*) FROM vektoren;  -- Sollte > 0 sein

-- Check: Sind Vektoren nicht NULL?
SELECT COUNT(*) FROM bibliotheken WHERE vektor_id IS NULL;  -- Sollte 0 sein

-- Check: Embeddings sind unterschiedlich?
SELECT DISTINCT dims FROM vektoren LIMIT 5;  -- Sollte verschiedene Arrays zeigen
```

**Fix:** Re-run Seed Data mit echten Ollama Embeddings (nicht Dummy-Vektoren)

### Problem: "Latenz > 5 Sekunden!"
**Debug:**
```sql
EXPLAIN ANALYZE
SELECT k.id, v.dims
FROM kategorien k
JOIN vektoren v ON k.vektor_id = v.id
WHERE k.bibliothek_id = 1;
```

**Fix:** Fehlende Indices! Check `IMPLEMENTATION_PLAN_HIERARCHICAL.md` für alle Indices.

### Problem: "IPC Connection refused!"
**Debug:**
```bash
# Check: Läuft Socket Server?
ps aux | grep socket_server

# Check: Socket existiert?
ls -la /tmp/bruce_hierarchical_search.sock

# Check: Permissions OK?
chmod 777 /tmp/bruce_hierarchical_search.sock
```

---

## 🎯 Nächste Schritte (nach Tag 7)

### Woche 2: Von 3 auf 6 Ebenen erweitern
- Füge Regal/Buch/Kapitel hinzu
- Update Search Engine
- Performance-Tests

### Woche 3: Indexer Pipeline
- Automatisches Dokument-Chunking
- Hierarchical Classification
- Review Queue

### Woche 4: Production-Readiness
- Multi-Tenant
- Monitoring
- Deployment Automation

---

## 📚 Ressourcen

### Dokumentation (in diesem Repo)
- `ROADMAP_HIERARCHICAL.md` - Big Picture & Phasen
- `IMPLEMENTATION_PLAN_HIERARCHICAL.md` - Alle technischen Details
- `README.md` - Bruce Core Dokumentation

### External Docs
- [PostgreSQL pgvector](https://github.com/pgvector/pgvector)
- [Ollama Embeddings](https://ollama.com/library/nomic-embed-text)
- [Bruce Original Paper](project/meta/README.md)

---

## 💬 Communication Protocol

### Daily Standups (mit dir selbst oder Team)
Schreibe jeden Tag:
1. Was ich gestern gemacht habe
2. Was ich heute mache
3. Blocker/Fragen

**Format:**
```
TAG 2 - Hierarchical Embedder
✅ Gestern: PostgreSQL Setup, Seed Data läuft
🚧 Heute: Embedder implementieren + testen
❓ Frage: Sollen wir 64D oder 128D Vektoren nutzen?
```

### Wenn du Hilfe brauchst
1. **Beschreibe das Problem konkret**
   - ❌ "Es geht nicht"
   - ✅ "PostgreSQL Connection refused, Error: FATAL: password authentication failed"

2. **Zeige was du versucht hast**
   ```python
   # Tried this:
   conn = psycopg2.connect("postgresql://localhost/bruce")
   # Error: ...
   
   # Also tried:
   conn = psycopg2.connect("postgresql://bruce:secret@localhost/bruce_knowledge")
   # Still fails with: ...
   ```

3. **Stelle eine spezifische Frage**
   - ❌ "Wie mache ich das?"
   - ✅ "Sollte ich pgBouncer für Connection Pooling nutzen oder reicht psycopg2 Pool?"

---

## 🎬 Final Pep Talk

Du baust nicht "noch eine Vector DB" - du baust **die erste hierarchisch navigierbare Wissens-Bibliothek** die sowohl strukturiert (IDs) als auch intelligent (Vektoren) ist!

**Library of Congress** brauchte 200 Jahre um ihr System zu entwickeln. Du hast es in 7 Tagen implementiert. Mit Vektoren. Offline. Und deterministisch.

Das ist **Next-Level Architecture**.

**Jetzt mach's einfach.** 🚀

---

*"Eine Bibliothek ist kein Stapel Bücher. Sie ist ein navigierbares Universum."*
