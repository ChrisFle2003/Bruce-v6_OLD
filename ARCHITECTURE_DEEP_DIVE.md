# Architecture Deep Dive: How Bruce v6 Works

Complete technical reference explaining the architecture, data flows, and design patterns in Bruce v6.

---

## Part 1: System Overview

### Mission

Bruce v6 is a **deterministic semantic computation engine** with integrated hierarchical knowledge. It provides:

1. **State Management**: 7-dimensional immutable state vectors
2. **Computation**: Vector operations, rule-based decisions, state mixing
3. **Knowledge System**: 6-level hierarchical cascade search
4. **Reproducibility**: 100% deterministic results (int16 fixed-point arithmetic)

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Application                         │
└──────────────────────────────┬──────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
        ┌───────────▼─────────┐  ┌──────────────────┐
        │ Bruce Core (C++)    │  │ Hierarchical     │
        │ ═════════════════   │  │ Knowledge System │
        │                     │  │ ════════════════ │
        │ • State vectors     │  │                  │
        │ • Vector math       │  │ • 6-level cascade│
        │ • Rule engine       │  │ • Guard rules    │
        │ • Axes & bounds     │  │ • IPC client     │
        └─────────────────────┘  └──────┬───────────┘
                                        │
                         ┌──────────────┴────────────┐
                         │                           │
                 ┌───────▼────────┐        ┌────────▼────────┐
                 │ Python Service │        │ PostgreSQL      │
                 │ ══════════════ │        │ + pgvector      │
                 │                │        │                 │
                 │ • Embedder     │        │ • Vectors       │
                 │ • Search MVP   │        │ • Hierarchy     │
                 │ • Socket Server│        │ • Indices       │
                 └────────────────┘        └─────────────────┘
```

---

## Part 2: Core Engine (C++)

### 2.1 Type System

All core types are defined in `include/bruce/types.hpp`:

```cpp
using val_t       = std::int16_t;      // State values: [-32767, 32767]
using dim_t       = std::uint32_t;     // Dimension index
using state_id_t  = std::uint64_t;     // State identifier
using rule_id_t   = std::uint64_t;     // Rule identifier
using core_id_t   = std::uint32_t;     // Core grouping
```

**Key Insight**: Using `int16_t` ensures:
- No floating-point precision issues
- Deterministic computation (same input → same output always)
- Efficient storage (16-bit vs 32-bit or 64-bit)
- PostgreSQL int16[] array compatibility

### 2.2 State Structure

A state is an **immutable 7-dimensional vector**:

```cpp
struct State {
    state_id_t id{};              // Unique identifier
    core_id_t core_id{};          // Which core system owns this state
    std::string core_version{};   // Version identifier
    std::vector<val_t> vec;       // 7D vector: [d0, d1, d2, d3, d4, d5, d6]

    // State never changes after creation
    // All operations create NEW states
};
```

**Example State Vector:**

```
Dimension 0 (analyse ↔ execution):      7000
Dimension 1 (abstract ↔ concrete):      6000
Dimension 2 (emotional ↔ rational):        0
Dimension 3 (social ↔ technical):          0
Dimension 4 (unstable ↔ stable):       4000
Dimension 5 (risky ↔ safe):               0
Dimension 6 (slow ↔ fast):              6000
```

Each dimension has metadata in the **AxisRegistry**:

```cpp
struct Axis {
    std::string name;              // "analyse↔execution"
    std::string label_negative;    // "analyse"
    std::string label_positive;    // "execution"
    val_t min_value{};            // Minimum allowed (typically -32768)
    val_t max_value{};            // Maximum allowed (typically 32767)
    std::string description{};     // "How analytical vs practical"
};
```

### 2.3 Core Operations

#### mix_into() - State Blending

Combines two states by averaging their vectors:

```cpp
State mix_into(const State& a, const State& b) {
    State result;
    result.vec.resize(a.vec.size());

    for (size_t i = 0; i < a.vec.size(); ++i) {
        // Average the two values
        result.vec[i] = (a.vec[i] + b.vec[i]) / 2;
    }

    return result;
}
```

**Example:**
```
State A: [7000,  6000,    0,    0, 4000,   0, 6000]
State B: [6000,  5000, 2000, 1000, 3000, 500, 5000]
         ──────────────────────────────────────────────
Result:  [6500, 5500, 1000, 500, 3500, 250, 5500]
```

#### l1_distance() - Manhattan Distance

Measures dissimilarity between states:

```cpp
int32_t l1_distance(const State& a, const State& b) {
    int32_t distance = 0;
    for (size_t i = 0; i < a.vec.size(); ++i) {
        distance += std::abs(a.vec[i] - b.vec[i]);
    }
    return distance;
}
```

**Example:**
```
State A: [7000, 6000]
State B: [6000, 5000]
         ─────────────
L1:      |7000-6000| + |6000-5000| = 1000 + 1000 = 2000
```

#### collapse_to_neutral() - Energy Score

Computes a single scalar representing "distance from neutral":

```cpp
double collapse_to_neutral(const State& state) {
    // Compute L2 norm / max possible
    double sum_squares = 0;
    for (val_t v : state.vec) {
        sum_squares += v * v;
    }

    double norm = std::sqrt(sum_squares);
    double max_norm = state.vec.size() * 32767;  // Max possible

    return norm / max_norm;  // Normalized [0, 1]
}
```

**Example:**
```
State: [7000, 6000, 0, 0, 4000, 0, 6000]
Norm: sqrt(7000² + 6000² + 0² + 0² + 4000² + 0² + 6000²)
    = sqrt(49M + 36M + 0 + 0 + 16M + 0 + 36M)
    = sqrt(137M) ≈ 11704.7
Collapse: 11704.7 / (7 * 32767) ≈ 0.051 (low energy state)
```

### 2.4 Rule System

Rules define allowed state transitions. A rule is a condition + action:

```cpp
struct Rule {
    rule_id_t id{};
    std::string name{};
    std::vector<Condition> conditions{};  // When rule applies
    std::vector<Effect> effects{};        // What happens
};
```

**Example Rule:**

```cpp
Rule goal_driven {
    .id = 1,
    .name = "Goal-Driven Action",
    .conditions = {
        {"energy > 50%", "State has sufficient energy"},
        {"analysis_bias < 30%", "Not too analytical"}
    },
    .effects = {
        {"set execution_bias = 80%", "Shift to execution"},
        {"reduce stability = -1000", "Accept more risk"}
    }
};
```

The engine evaluates which rules apply to each state and applies their effects.

### 2.5 Axes Registry

Central registry of all dimensions:

```cpp
class AxisRegistry {
private:
    std::vector<Axis> axes_;  // 7 axes for Bruce v6

public:
    void register_axis(const Axis& axis);
    const Axis& get_axis(dim_t id) const;
    val_t clamp(dim_t axis_id, val_t value) const;
};
```

**Typical Registry:**

```
Axis 0: analyse ↔ execution   (range: -32768 to 32767)
Axis 1: abstract ↔ concrete   (range: -32768 to 32767)
Axis 2: emotional ↔ rational  (range: -32768 to 32767)
Axis 3: social ↔ technical    (range: -32768 to 32767)
Axis 4: unstable ↔ stable     (range: -32768 to 32767)
Axis 5: risky ↔ safe          (range: -32768 to 32767)
Axis 6: slow ↔ fast           (range: -32768 to 32767)
```

---

## Part 3: Hierarchical Knowledge System

### 3.1 6-Level Hierarchy

The knowledge system organizes information in 6 nested levels:

```
Level 1: Bibliothek (Library)
├── Programming
├── Mathematics
└── Philosophy

    Level 2: Kategorie (Category)
    ├── Python
    ├── JavaScript
    └── C++

        Level 3: Regal (Shelf/Topic)
        ├── Advanced Features
        ├── Basics
        └── Performance Tuning

            Level 4: Buch (Book/Document)
            ├── Lambda Functions Guide
            ├── Decorators Tutorial
            └── Async/Await Reference

                Level 5: Kapitel (Chapter/Section)
                ├── Introduction
                ├── Basic Syntax
                └── Advanced Examples

                    Level 6: Seite (Page/Content)
                    ├── "Lambda syntax: lambda x: x * 2"
                    ├── "Usage: map(lambda x: x*2, numbers)"
                    └── "Performance: faster than def"
```

### 3.2 Cascade Filtering Algorithm

Each level filters the next level's search space:

**Step 1: Embed the query**
```
Query: "Python Lambda Functions"
↓
Embedder generates 64D int16 vector
```

**Step 2: Level 1 - Find best Bibliothek**
```
SELECT TOP 1 FROM bibliotheken
WHERE similarity(query_vector, bibliothek_vector) > threshold
Result: "Programming" (similarity: 0.85)
```

**Step 3: Level 2 - Filter by Level 1 result**
```
SELECT TOP 3 FROM kategorien
WHERE bibliothek_id = 1  ← FILTERED by Level 1
ORDER BY similarity DESC
Results: ["Python", "JavaScript", "C++"]
```

**Step 4: Level 3 - Filter by Level 2 results**
```
SELECT TOP 5 FROM regale
WHERE kategorie_id IN (1, 2, 3)  ← FILTERED by Level 2
ORDER BY similarity DESC
Results: ["Advanced Features", "Basics", ...]
```

**Step 5-6: Continue cascading through Buch, Kapitel, Seite**

**Performance Benefit:**

```
Without filtering:  10M items → 5000ms (full scan)
With cascade:       10M → 100K → 10K → 1K → 100 → 10 items → 7ms
Speedup:            5000ms / 7ms ≈ 700x faster!
```

### 3.3 State-to-Hierarchy Mapping

Bruce's 7D state vector maps to hierarchy IDs:

```cpp
class StateToHierarchyMapper {
public:
    static HierarchicalPath map(const State& state) {
        HierarchicalPath path;

        // Each dimension maps to a hierarchy ID
        path.bibliothek_id = map_to_id(state.vec[0]);      // Dim 0
        path.kategorie_id = map_to_id(state.vec[1]);       // Dim 1
        path.regal_id = map_to_id(state.vec[2]);           // Dim 2
        path.buch_id = map_to_id(state.vec[3]);            // Dim 3
        path.kapitel_id = map_to_id(state.vec[4]);         // Dim 4
        path.seite_id = map_to_id(state.vec[5]);           // Dim 5
        path.vektor_id = state.vec[6];                     // Dim 6

        return path;
    }

private:
    // Convert int16 [-32767, 32767] to uint32 ID
    static uint32_t map_to_id(val_t value) {
        // Shift to [0, 65535] range, then mod to get ID
        return (static_cast<uint32_t>(value) + 32768) % 65536;
    }
};
```

**Mapping Example:**

```
State vector: [7000, 6000, 5000, 4000, 3000, 2000, 1000]
                  ↓      ↓      ↓      ↓      ↓      ↓      ↓
        Hierarchy: Bib    Kat    Reg    Buch   Kap    Sei    Vec
                   39768  38768  37768  36768  35768  34768  33768
```

### 3.4 Hierarchical Guard

Validates access to knowledge system before query:

```cpp
class HierarchicalGuard {
public:
    bool validate(const HierarchicalPath& path,
                  const HierarchicalManifest& manifest) {

        // Check Rule 1: Bibliothek Whitelist
        if (!whitelist_rule_.validate(path.bibliothek_id, manifest)) {
            return false;  // Access denied
        }

        // Check Rule 2: Budget Limit
        if (!budget_rule_.validate(manifest)) {
            return false;  // Over budget
        }

        // Check Rule 3: Depth Limit
        if (!depth_rule_.validate(path)) {
            return false;  // Too deep
        }

        return true;  // All checks passed
    }
};
```

**Rule 1: BibliothekWhitelistRule**
```
Allowed libraries: {1, 2, 3}
Query library ID:  2
Result: ALLOW ✓
```

**Rule 2: BudgetLimitRule**
```
Max results: 50
Max data size: 100MB
Current usage: 20MB, 10 results
Result: ALLOW ✓
```

**Rule 3: DepthLimitRule**
```
Max depth: 3 levels
Current query depth: 2 (Bib → Kat → Reg)
Result: ALLOW ✓
```

### 3.5 IPC Protocol

C++ and Python communicate via **TCP localhost** (cross-platform compatible):

**Connection:**
```
C++: UnixSocketClient("127.0.0.1:5555")
Python: SocketServer(host="127.0.0.1", port=5555)
```

**Request (JSON):**
```json
{
    "query_text": "Python Lambda Functions",
    "trace_id": "req_12345"
}
```

**Response (JSON):**
```json
{
    "query": "Python Lambda Functions",
    "trace_id": "req_12345",
    "duration_ms": 7,
    "bibliothek": {
        "id": 1,
        "name": "Programming",
        "similarity": 0.850
    },
    "kategorien": [
        {"id": 11, "name": "Python", "similarity": 0.823},
        {"id": 12, "name": "JavaScript", "similarity": 0.712}
    ],
    "regale": [
        {"id": 111, "name": "Advanced Features", "similarity": 0.797}
    ],
    "buecher": [
        {"id": 1111, "name": "Lambda Functions Guide", "similarity": 0.765}
    ],
    "kapitel": [
        {"id": 11111, "name": "Introduction", "similarity": 0.067}
    ],
    "seiten": [
        {
            "id": 111111,
            "name": "Lambda syntax example",
            "content": "lambda x: x * 2",
            "similarity": 0.057
        }
    ],
    "seiten_count": 1
}
```

---

## Part 4: Python Services

### 4.1 Hierarchical Embedder

Generates 64-dimensional int16 embeddings for each hierarchy level:

```python
class HierarchicalEmbedder:
    def embed_bibliothek(self, name: str) -> np.ndarray:
        """Generate embedding for library level."""
        # Use Ollama or mock mode
        float32_embedding = self.get_embedding(name)

        # Quantize to int16 [-32767, 32767]
        int16_embedding = self.quantize_to_int16(float32_embedding)

        return int16_embedding  # 64D int16 vector

    def embed_kategorie(self, name: str, parent: str) -> np.ndarray:
        """Generate embedding for category with parent context."""
        context = f"{parent} > {name}"  # Include hierarchy context
        return self.embed(context)

    # ... similar methods for regal, buch, kapitel, seite ...

    def quantize_to_int16(self, float_vec: np.ndarray) -> np.ndarray:
        """Convert float32 to int16."""
        # 1. Normalize float vector
        float_vec = float_vec / (np.linalg.norm(float_vec) + 1e-8)

        # 2. Scale to int16 range [-32767, 32767]
        # 3. Clamp and convert
        int16_vec = np.clip(float_vec * 32767, -32767, 32767).astype(np.int16)

        return int16_vec
```

**Example Embedding Process:**

```
Query: "Python Lambda Functions"

Step 1: Generate 64D float32 via Ollama
[0.123, 0.456, -0.789, ..., 0.234]  (float32)

Step 2: Normalize to unit vector
[0.089, 0.331, -0.575, ..., 0.170]

Step 3: Scale and quantize to int16
[2914, 10830, -18823, ..., 5568]  (int16)
```

### 4.2 Hierarchical Search MVP

Implements the 6-level cascade search:

```python
class HierarchicalSearchMVP:
    def search(self, query_text: str) -> dict:
        """Execute 6-level cascade search."""

        start_time = time.time()

        # Step 1: Embed query
        query_embedding = self.embedder.embed_query(query_text)

        # Step 2: Level 1 - Find best Bibliothek
        bibliotheken = self._search_bibliotheken(query_embedding)
        if not bibliotheken:
            return {"error": "No results"}

        # Step 3: Level 2 - Find Kategorien in those Bibliotheken
        kategorien = self._search_kategorien(query_embedding,
                                            bibliotheken_ids=[b['id'] for b in bibliotheken])

        # Step 4: Level 3 - Find Regale in those Kategorien
        regale = self._search_regale(query_embedding,
                                    kategorie_ids=[k['id'] for k in kategorien])

        # Step 5: Level 4 - Find Buecher
        buecher = self._search_buecher(query_embedding,
                                      regal_ids=[r['id'] for r in regale])

        # Step 6: Level 5 - Find Kapitel
        kapitel = self._search_kapitel(query_embedding,
                                      buch_ids=[b['id'] for b in buecher])

        # Step 7: Level 6 - Find Seiten
        seiten = self._search_seiten(query_embedding,
                                    kapitel_ids=[k['id'] for k in kapitel])

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "query": query_text,
            "duration_ms": elapsed_ms,
            "bibliothek": bibliotheken[0] if bibliotheken else None,
            "kategorien": kategorien,
            "regale": regale,
            "buecher": buecher,
            "kapitel": kapitel,
            "seiten": seiten,
            "seiten_count": len(seiten)
        }

    def _search_bibliotheken(self, embedding: np.ndarray, top_k: int = 1):
        """Level 1: Find best libraries."""
        sql = """
            SELECT id, name, vektor_id,
                   cosine_distance(embedding, %s) as similarity
            FROM bibliotheken
            ORDER BY similarity DESC
            LIMIT %s
        """
        results = self.db.execute(sql, (embedding, top_k))
        return [{"id": r[0], "name": r[1], "similarity": r[3]} for r in results]

    # ... similar methods for each level ...
```

### 4.3 Socket Server

Listens for IPC requests and returns search results:

```python
class SocketServer:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.search = HierarchicalSearchMVP()

    def start(self):
        """Start listening on TCP socket."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)

        print(f"Listening on {self.host}:{self.port}")

        while True:
            client_socket, addr = server_socket.accept()
            self.handle_client(client_socket, addr)

    def handle_client(self, client_socket, addr):
        """Process single client request."""
        try:
            # Receive JSON request
            data = client_socket.recv(4096).decode('utf-8')
            request = json.loads(data)

            # Execute search
            query_text = request.get("query_text")
            response = self.search.search(query_text)

            # Send JSON response
            response_json = json.dumps(response)
            client_socket.sendall(response_json.encode('utf-8'))
        finally:
            client_socket.close()
```

---

## Part 5: PostgreSQL Database

### 5.1 Schema

Seven tables form the hierarchical structure:

```sql
-- Vector pool (central embeddings storage)
CREATE TABLE vektoren (
    id SERIAL PRIMARY KEY,
    ebene VARCHAR UNIQUE,      -- Level name
    dims INT2[64]              -- 64D int16 vector array
);

-- Hierarchical tables (each filtered by parent)
CREATE TABLE bibliotheken (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    vektor_id INT REFERENCES vektoren(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE kategorien (
    id SERIAL PRIMARY KEY,
    bibliothek_id INT NOT NULL REFERENCES bibliotheken(id),
    name VARCHAR NOT NULL,
    vektor_id INT REFERENCES vektoren(id)
);

CREATE TABLE regale (
    id SERIAL PRIMARY KEY,
    kategorie_id INT NOT NULL REFERENCES kategorien(id),
    name VARCHAR NOT NULL,
    vektor_id INT REFERENCES vektoren(id)
);

CREATE TABLE buecher (
    id SERIAL PRIMARY KEY,
    regal_id INT NOT NULL REFERENCES regale(id),
    name VARCHAR NOT NULL,
    vektor_id INT REFERENCES vektoren(id)
);

CREATE TABLE kapitel (
    id SERIAL PRIMARY KEY,
    buch_id INT NOT NULL REFERENCES buecher(id),
    name VARCHAR NOT NULL,
    vektor_id INT REFERENCES vektoren(id)
);

CREATE TABLE seiten (
    id SERIAL PRIMARY KEY,
    kapitel_id INT NOT NULL REFERENCES kapitel(id),
    name VARCHAR NOT NULL,
    content TEXT,
    vektor_id INT REFERENCES vektoren(id)
);

-- Fast navigation view
CREATE MATERIALIZED VIEW wissens_pfade AS
    SELECT b.id as bib_id, k.id as kat_id, r.id as reg_id,
           bu.id as buch_id, ka.id as kap_id, s.id as sei_id,
           concat(b.name, ' > ', k.name, ' > ', r.name, ...) as full_path
    FROM bibliotheken b
    JOIN kategorien k ON k.bibliothek_id = b.id
    JOIN regale r ON r.kategorie_id = k.id
    ...
    JOIN seiten s ON s.kapitel_id = ka.id;
```

### 5.2 Indices

Indices enable fast filtering at each cascade level:

```sql
-- Foreign key indices (cascade filtering)
CREATE INDEX idx_kategorien_bibliothek_id ON kategorien(bibliothek_id);
CREATE INDEX idx_regale_kategorie_id ON regale(kategorie_id);
CREATE INDEX idx_buecher_regal_id ON buecher(regal_id);
CREATE INDEX idx_kapitel_buch_id ON kapitel(buch_id);
CREATE INDEX idx_seiten_kapitel_id ON seiten(kapitel_id);

-- Name lookups
CREATE INDEX idx_bibliotheken_name ON bibliotheken(name);
CREATE INDEX idx_kategorien_name ON kategorien(name);

-- Vector ID lookups
CREATE INDEX idx_bibliotheken_vektor_id ON bibliotheken(vektor_id);
CREATE INDEX idx_kategorien_vektor_id ON kategorien(vektor_id);
```

### 5.3 Example Data

```sql
-- Seed data showing complete hierarchy path

INSERT INTO vektoren VALUES
  (1, 'bibliothek', '{1000, 2000, 3000, ..., 100}'),  -- 64 int16 values
  (2, 'kategorie', '{1100, 2100, 3100, ..., 101}'),
  (3, 'regal', '{1200, 2200, 3200, ..., 102}'),
  (4, 'buch', '{1300, 2300, 3300, ..., 103}'),
  (5, 'kapitel', '{1400, 2400, 3400, ..., 104}'),
  (6, 'seite', '{1500, 2500, 3500, ..., 105}');

INSERT INTO bibliotheken VALUES
  (1, 'Programming', 1, NOW());

INSERT INTO kategorien VALUES
  (1, 1, 'Python', 2, NOW());

INSERT INTO regale VALUES
  (1, 1, 'Advanced Features', 3, NOW());

INSERT INTO buecher VALUES
  (1, 1, 'Lambda Functions Guide', 4, NOW());

INSERT INTO kapitel VALUES
  (1, 1, 'Introduction', 5, NOW());

INSERT INTO seiten VALUES
  (1, 1, 'Lambda Syntax', 'lambda x: x * 2', 6, NOW());
```

---

## Part 6: Complete Data Flow

### From User Query to Results

```
1. USER INPUT
   ↓
   Query: "Python Lambda Functions"
   State: [7000, 6000, 5000, 4000, 3000, 2000, 1000]

2. C++ GUARD VALIDATION
   ↓
   HierarchicalGuard.validate(state → path)
   - Check whitelist: library_id=1 allowed? ✓
   - Check budget: 100MB, 50 results limit? ✓
   - Check depth: max 3 levels? ✓
   → APPROVED

3. IPC REQUEST (TCP localhost:5555)
   ↓
   C++: UnixSocketClient.send_request({
       "query_text": "Python Lambda Functions"
   })

4. PYTHON EMBEDDING
   ↓
   HierarchicalEmbedder.embed_query(text)
   → 64D int16 vector

5. LEVEL 1 CASCADE - BIBLIOTHEK
   ↓
   SELECT TOP 1 FROM bibliotheken
   ORDER BY similarity(embedding, vektor) DESC
   → Result: Programming (similarity=0.85)

6. LEVEL 2 CASCADE - KATEGORIE
   ↓
   SELECT TOP 3 FROM kategorien
   WHERE bibliothek_id = 1
   ORDER BY similarity DESC
   → Results: Python, JavaScript, C++

7. LEVEL 3 CASCADE - REGAL
   ↓
   SELECT TOP 5 FROM regale
   WHERE kategorie_id IN (1, 2, 3)
   ORDER BY similarity DESC
   → Results: Advanced Features, Basics, ...

8. LEVEL 4 CASCADE - BUCH
   ↓
   SELECT TOP 5 FROM buecher
   WHERE regal_id IN (selected regal IDs)
   → Results: Lambda Guide, Decorators Tutorial, ...

9. LEVEL 5 CASCADE - KAPITEL
   ↓
   SELECT TOP 10 FROM kapitel
   WHERE buch_id IN (selected buch IDs)
   → Results: Introduction, Basic Syntax, ...

10. LEVEL 6 CASCADE - SEITE
    ↓
    SELECT TOP 10 FROM seiten
    WHERE kapitel_id IN (selected kapitel IDs)
    → Final Results: Lambda syntax example, Usage examples, ...

11. IPC RESPONSE (JSON)
    ↓
    Python: send_response({
        "seiten": [
            {"id": 111, "name": "Lambda syntax", "content": "...", "similarity": 0.057}
        ],
        "duration_ms": 7
    })

12. C++ RESULT PARSING
    ↓
    UnixSocketClient.receive_data()
    → Parse JSON response
    → Return to application

13. APPLICATION OUTPUT
    ↓
    Found 1 page in 7ms
    Title: Lambda syntax example
    Content: lambda x: x * 2
```

---

## Part 7: Key Design Patterns

### Pattern 1: Immutability

All state is immutable:
- States never change
- Operations create new states
- Thread-safe by design

```cpp
// No mutation
State s1 = ...;
State s2 = mix_into(s1, s3);  // s1 unchanged, new State returned
```

### Pattern 2: Separation of Concerns

Three independent layers:

```
Core (C++)
├─ Knows: States, vectors, rules
├─ Doesn't know: Storage, embeddings
└─ Responsibility: Deterministic computation

↓ TCP IPC

Knowledge (Python)
├─ Knows: Embeddings, search, hierarchy
├─ Doesn't know: State machines, rules
└─ Responsibility: Fast retrieval

↓ SQL

Storage (PostgreSQL)
├─ Knows: Persistence, indices, queries
├─ Doesn't know: Algorithms, embeddings
└─ Responsibility: Data durability
```

### Pattern 3: Cascade Filtering

Each level filters the next:

```
10M items → 1M items → 100K → 10K → 1K → 100 → 10
(filtered via foreign keys + indices)
Result: 100x-1000x speedup vs flat search
```

### Pattern 4: Fixed-Point Arithmetic

All values are int16:

```
Benefits:
✓ Deterministic (no float precision)
✓ Reproducible (same query always same result)
✓ Efficient (16-bit storage)
✓ PostgreSQL native (int16[] arrays)
```

---

## Part 8: Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Create state | <1μs | In-memory, deterministic |
| Mix two states | ~1μs | Simple vector averaging |
| L1 distance | ~1μs | Vector iteration |
| collapse_to_neutral | ~5μs | Sqrt computation |
| Generate embedding (Ollama) | 50-150ms | Neural network inference |
| Generate embedding (mock) | <1μs | Hash-based deterministic |
| Single DB query (cascaded) | <5ms | With indices |
| 6-level cascade (total) | 7ms avg | 6 queries + filtering |
| **Full query latency** | **~100-200ms** | Ollama mode, includes embedding time |
| **Full query latency** | **~7ms** | Mock mode (testing) |

---

## Summary Table

| Component | Language | Purpose | Dependency |
|-----------|----------|---------|-----------|
| **bruce_core** | C++20 | State vectors, rules, operations | None |
| **bruce_io** | C++20 | Project loading, JSON export | bruce_core |
| **bruce_knowledge** | C++20 | Guard, IPC client | bruce_core |
| **brucev4** | C++20 | CLI executable | bruce_core, bruce_io |
| **hierarchical_embedder** | Python | Generate embeddings | Ollama, psycopg2 |
| **hierarchical_search_mvp** | Python | 6-level cascade search | psycopg2 |
| **socket_server** | Python | IPC listener | hierarchical_search_mvp |
| **PostgreSQL** | SQL | Persistent storage | pgvector extension |

---

