# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bruce v6 is a deterministic semantic computation engine with an integrated hierarchical knowledge system. The core engine implements state transitions, vector operations, and rule-based decision making. The hierarchical knowledge system adds 6-level cascade-filtering search over a semantic library.

**Key Characteristics:**
- Pure C++20 deterministic core with no external dependencies
- PostgreSQL + pgvector backend for hierarchical knowledge
- Python services for embeddings and cascade search
- Unix domain socket IPC between C++ and Python
- Fixed-point int16 arithmetic (no floating-point precision issues)
- All operations reproducible and deterministic

## Architecture

### High-Level System Design

```
User Query (Text)
    ↓
Bruce C++ Core
├─ StateToHierarchyMapper: Map 7D state to hierarchy IDs
├─ HierarchicalGuard: Validate path (whitelist, budget, depth)
└─ IPC Client: Send query via Unix socket
    ↓
Python Search Service
├─ HierarchicalEmbedder: Generate 64D int16 embeddings
│  └─ 6 context-aware levels (Bib→Kat→Regal→Buch→Kap→Seite)
├─ HierarchicalSearchMVP: 6-level cascade filtering
│  └─ Each level filters next by 10-100x
└─ SocketServer: Listen on Unix socket for requests
    ↓
PostgreSQL + pgvector
├─ 6 hierarchical tables (one per level)
├─ Materialized views for fast navigation
└─ Deterministic cascade queries via JOINs
    ↓
Results (Top-K pages with full path tracking)
```

### Hierarchical Levels

The knowledge system organizes content in 6 levels, each filtering the next:

1. **Bibliothek** (Library/Domain) - e.g., "Programming"
2. **Kategorie** (Category) - e.g., "Python"
3. **Regal** (Shelf/Topic) - e.g., "Advanced Features"
4. **Buch** (Book/Document) - e.g., "Lambda Functions Guide"
5. **Kapitel** (Chapter/Section) - e.g., "Introduction"
6. **Seite** (Page/Content) - e.g., "Lambda syntax example"

**Cascade Filtering:** Query → Level 1 (1 match) → Level 2 (3 matches) → Level 3 (5 matches) → ... → Final results. Each level reduces search space by 10-100x, totaling 100x+ reduction vs flat search.

### Core Libraries

| Library | Role | Key Files |
|---------|------|-----------|
| **bruce_core** | Vector operations, state management, rules | `src/core_*.cpp`, `include/bruce/core/` |
| **bruce_io** | Project loading, JSON export | `src/io_*.cpp` |
| **bruce_knowledge** | Hierarchical guard, IPC client | `src/hierarchical_*.cpp`, `src/ipc_client.cpp` |
| **Python Services** | Embeddings, cascade search, socket server | `knowledge/services/*.py` |

## Development Setup

### Build Commands

```bash
# Configure with Ninja (preferred on Windows)
cmake -S . -B out/build/x64-Debug -G Ninja

# Build all targets
cmake --build out/build/x64-Debug

# Release build with optimizations
cmake -S . -B out/build/x64-Release -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build out/build/x64-Release
```

### Run Tests

```bash
# Core engine tests
./out/build/x64-Debug/test_core.exe

# Decision engine tests
./out/build/x64-Debug/test_v6.exe

# Hierarchical guard tests (knowledge system)
./out/build/x64-Debug/test_hierarchical_guard.exe

# Python integration tests (requires PostgreSQL + Ollama running)
cd knowledge
python -m pytest tests/ -v
python tests/test_e2e_integration.py          # Full 6-level flow test
python tests/test_6_level_cascade.py          # Cascade efficiency test
```

### Python Development

```bash
# Install dependencies
pip install -r knowledge/requirements.txt

# Run Python services directly (for debugging)
python knowledge/services/hierarchical_embedder.py      # Test embeddings
python knowledge/services/hierarchical_search_mvp.py    # Test search
python knowledge/services/socket_server.py              # Start IPC server

# Run individual Python tests
python -m pytest knowledge/tests/test_e2e_integration.py::test_complete_flow -v
python -m pytest knowledge/tests/test_6_level_cascade.py::analyze_cascade_filtering -v
```

### PostgreSQL & Docker

```bash
# Start PostgreSQL + Ollama (required for knowledge system)
docker-compose up -d

# Initialize database (schema + seed data)
bash knowledge/scripts/init_db.sh

# Connect to database directly
psql -h localhost -U bruce -d bruce_knowledge

# View database structure
psql -h localhost -U bruce -d bruce_knowledge -c "\dt"

# Stop services
docker-compose down
```

## Project Structure

```
src/                          # C++ implementation
├── core_*.cpp                # Core state/vector/rule operations
├── io_*.cpp                  # JSON I/O and project loading
├── cli_main.cpp              # CLI executable entry point
├── hierarchical_guard.cpp    # Hierarchical guard validation
└── ipc_client.cpp            # Unix socket client

include/bruce/                # C++ headers
├── core/                     # Core engine APIs
├── io/                       # I/O interfaces
├── knowledge/                # Hierarchical system headers
│   ├── hierarchical_guard.hpp
│   └── ipc_client.hpp

tests/                        # C++ unit tests
├── test_core.cpp            # Core operations
├── test_v6.cpp              # Decision engine
└── test_hierarchical_guard.cpp

bench/                        # Performance benchmarks
└── bench_mix_v4.cpp         # Mixed operation benchmarks

knowledge/                    # Hierarchical knowledge system
├── migrations/
│   └── 002_hierarchical_library_schema.sql  # Database schema
├── services/
│   ├── hierarchical_embedder.py             # Vector generation
│   ├── hierarchical_search_mvp.py           # Cascade search (6-level)
│   └── socket_server.py                     # IPC server
├── tests/
│   ├── test_e2e_integration.py              # End-to-end flow
│   ├── test_6_level_cascade.py              # 6-level verification
│   ├── test_embedder.py                     # Embedding tests
│   ├── test_ipc_mock.py                     # IPC tests
│   └── test_socket_server.py                # Socket tests
├── CASCADE_EVOLUTION.md                      # 3-level → 6-level evolution
├── SESSION_SUMMARY.md                       # Implementation summary
├── IMPLEMENTATION_CHECKLIST.md               # Completion status
└── README.md                                # Quick start guide

CMakeLists.txt               # Build configuration
docker-compose.yml           # PostgreSQL + Ollama setup
IMPLEMENTATION_STATUS.md     # Project status and metrics
```

## Key Implementation Details

### Fixed-Point Arithmetic

All embeddings are stored as **int16_t** (signed 16-bit integers) in the range [-32767, 32767]. This ensures:
- **Determinism**: No floating-point precision variations
- **Reproducibility**: Same query always produces identical results
- **Efficiency**: 64 int16 values = 128 bytes per embedding
- **PostgreSQL compatibility**: Direct int16[64] array storage

The Python embedder converts float32 embeddings to int16 via quantization (normalization + scaling).

### Cascade Filtering Algorithm

Each search level:
1. **Generates embedding** with parent context (e.g., "Python > Advanced Features")
2. **Computes similarities** using cosine distance on int16 vectors
3. **Selects top-K** matches based on similarity score
4. **Filters next level** to only items belonging to selected parents

**Performance:**
- Level 1: 1 match from ~10 options (1:10)
- Level 2: 3 matches from ~100 options (3:100)
- Level 3: 5 matches from ~1K options (5:1K)
- ... cascading to final results
- **Total:** 1M → ~1K items scanned (1000x reduction)

### State-to-Hierarchy Mapping

Bruce's 7D state vector maps directly to hierarchy IDs:

```cpp
State.vec[0] (int16) → BibliothekID (uint32)
State.vec[1] (int16) → KategorieID (uint32)
State.vec[2] (int16) → RegalID (uint32)
State.vec[3] (int16) → BuchID (uint32)
State.vec[4] (int16) → KapitelID (uint32)
State.vec[5] (int16) → SeiteID (uint32)
State.vec[6] (int16) → VektorenID (pointer to 64D embedding)
```

Conversion formula: `ID = (state_value + 32768) % 65536`

## Performance Characteristics

| Operation | Latency | Notes |
|-----------|---------|-------|
| Single embedding | 50-150ms | Via Ollama (mock: <1ms) |
| 6-level search | 3-14ms avg | Including DB queries |
| Cascade filtering | 7ms avg | 5 queries tested |
| Vector similarity | <1ms | Cosine on int16 |
| Database cascade JOINs | <1ms | With indices |

**Determinism:** 100% - same query always produces identical results within ±1ms variance.

## Guard System Design

The `HierarchicalGuard` in Bruce core validates knowledge system access without performing search:

```cpp
HierarchicalPath path = StateToHierarchyMapper::map(state);
HierarchicalManifest manifest = /* guard rules */;

// Validates:
// - BibliothekWhitelistRule: only allowed libraries
// - BudgetLimitRule: max MB and result count
// - DepthLimitRule: query depth restrictions

if (guard.validate(path, manifest)) {
  // Safe to query knowledge system
  results = ipc_client.search(query_text);
}
```

## IPC Protocol

Communication between C++ and Python via Unix domain socket:

**Request (JSON):**
```json
{"query_text": "Python Lambda Functions"}
```

**Response (JSON):**
```json
{
  "query": "Python Lambda Functions",
  "duration_ms": 7,
  "seiten_count": 1,
  "bibliothek": {"id": 1, "name": "Programming"},
  "kategorien": [...],
  "regale": [...],
  "buecher": [...],
  "kapitel": [...],
  "seiten": [...]
}
```

## Common Development Tasks

### Adding a New Search Query Type

1. Add embedding method to `HierarchicalEmbedder` if needed
2. Extend cascade filtering in `HierarchicalSearchMVP.search()`
3. Add test case to `test_e2e_integration.py`
4. Verify latency stays under 1000ms

### Modifying Database Schema

1. Create new migration in `knowledge/migrations/`
2. Update migration number (e.g., `003_*.sql`)
3. Test with `bash knowledge/scripts/init_db.sh`
4. Verify cascade queries still work via `test_6_level_cascade.py`

### Profiling Search Performance

```bash
# Run benchmark with timing details
python -c "
import time, sys, os
sys.path.insert(0, 'knowledge/services')
from hierarchical_search_mvp import HierarchicalSearchMVP

search = HierarchicalSearchMVP(use_mock_embeddings=True)
queries = ['Python Lambda', 'Advanced Programming', 'Function Definitions']

for q in queries:
    start = time.time()
    results = search.search(q)
    print(f'{q}: {(time.time()-start)*1000:.1f}ms')
"
```

## Important Notes

### Database Initialization

Always initialize PostgreSQL before running Python tests:
```bash
docker-compose up -d
bash knowledge/scripts/init_db.sh
```

The database must have the 6-level schema and seed data, or cascade queries will fail.

### Mock vs Ollama Mode

Python services support two embedding modes:

```python
# Mock mode (deterministic, <1ms, for testing)
search = HierarchicalSearchMVP(use_mock_embeddings=True)

# Ollama mode (realistic embeddings, requires container, 50-150ms)
search = HierarchicalSearchMVP(use_mock_embeddings=False)
```

Mock mode is ideal for rapid testing; Ollama mode for production.

### Unicode Encoding on Windows

All test output uses ASCII-safe characters (no Unicode arrows). If adding new test output, avoid Unicode and use ASCII equivalents:
- ✓ → [OK]
- ✗ → [FAIL]
- → → ->

### Build Targets

| Target | Purpose | Command |
|--------|---------|---------|
| `bruce_core` | Core library | (built automatically) |
| `bruce_knowledge` | Knowledge integration library | (built automatically) |
| `brucev4` | CLI executable | `cmake --build ... --target brucev4` |
| `test_core` | Core unit tests | `cmake --build ... --target test_core` |
| `test_hierarchical_guard` | Guard validation tests | `cmake --build ... --target test_hierarchical_guard` |
| `bench_mix_v4` | Performance benchmarks | `cmake --build ... --target bench_mix_v4` |

## References

- **Architecture**: `IMPLEMENTATION_STATUS.md` (high-level overview)
- **Evolution**: `CASCADE_EVOLUTION.md` (3-level → 6-level progression)
- **Completion**: `IMPLEMENTATION_CHECKLIST.md` (feature checklist)
- **Quick Start**: `knowledge/README.md` (service setup)
- **Guard System**: `HIERARCHICAL_GUARD_README.md` (validation rules)
