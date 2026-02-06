# Bruce Hierarchical Knowledge System

Implementation of a 6-level hierarchical knowledge library for Bruce v6 semantic computation engine.

## Architecture

The hierarchical knowledge system provides:
- **Deterministic semantic search** with cascade filtering
- **Fixed-point vector embeddings** (64D int16)
- **PostgreSQL backend** with pgvector extension
- **Python services** for embeddings and search
- **C++ integration** with Bruce core via Unix sockets

## Project Structure

```
knowledge/
├── migrations/           # PostgreSQL schema migrations
│   ├── 001_base_schema.sql
│   └── 002_hierarchical_library_schema.sql
├── services/            # Python service implementations
│   ├── hierarchical_embedder.py    # Vector generation
│   └── hierarchical_search_mvp.py  # Cascade filtering search
├── tests/               # Python unit tests
│   └── test_embedder.py
├── scripts/             # Setup and maintenance scripts
│   ├── init_db.sh       # Database initialization
│   └── test_search_mvp.sh
├── config/              # Configuration files
└── requirements.txt     # Python dependencies
```

## Quick Start

### 1. Start Services

```bash
# Start PostgreSQL and Ollama
docker-compose up -d

# Wait for PostgreSQL to be ready
sleep 10
```

### 2. Initialize Database

```bash
# Run migrations and seed data
bash knowledge/scripts/init_db.sh

# Verify schema
psql -h localhost -U bruce -d bruce_knowledge -c "\dt"
```

### 3. Setup Python Environment

```bash
# Install dependencies
pip install -r knowledge/requirements.txt

# Pull embedding model (in Ollama container)
docker-compose exec ollama ollama pull nomic-embed-text
```

### 4. Run Tests

```bash
# Test embedder
python -m pytest knowledge/tests/test_embedder.py -v

# Test search engine
bash knowledge/scripts/test_search_mvp.sh
```

## 7-Day Implementation Plan

- **Day 1**: PostgreSQL setup + schema ✓ (in progress)
- **Day 2**: Hierarchical embedder (Python)
- **Day 3**: Search engine MVP (3-level cascade)
- **Day 4**: Bruce C++ Guard
- **Day 5**: IPC Bridge (C++ ↔ Python)
- **Day 6-7**: End-to-end integration

## Key Concepts

### Hierarchical Levels

1. **Bibliothek** (Library/Domain) - e.g., "Programming"
2. **Kategorie** (Category) - e.g., "Python"
3. **Regal** (Shelf/Topic) - e.g., "Advanced Features"
4. **Buch** (Book/Document) - e.g., "Lambda Functions Guide"
5. **Kapitel** (Chapter) - e.g., "Introduction"
6. **Seite** (Page/Content) - e.g., "Lambda syntax example"

### Cascade Filtering

Each level filters the search space:
```
10M pages (flat search) → 1000ms
→ 10 libs (filtered) → 100 cats → 500 shelves → 2k books → 10k chapters → 50k pages
→ 150ms (33x speedup!)
```

### Fixed-Point Vectors

All embeddings are 64-dimensional int16 values (range: -32767 to 32767). This ensures:
- Deterministic computation
- No floating-point precision issues
- Efficient PostgreSQL storage (int16[64] arrays)

## Database Schema

Main tables:
- `vektoren` - Vector pool (64D embeddings)
- `bibliotheken` - Top-level domains
- `kategorien` - Categories (filtered by bibliothek_id)
- `regale` - Shelves (filtered by kategorie_id)
- `buecher` - Books/Documents (filtered by regal_id)
- `kapitel` - Chapters (filtered by buch_id)
- `seiten` - Pages/Content (filtered by kapitel_id)
- `wissens_pfade` - Materialized view for fast navigation

## Configuration

Edit `.env` to customize:
- Database credentials
- Ollama model and dimensions
- Service ports
- Logging level

See `.env.example` for all available options.

./out/build/x64-Release/test_e2e_hierarchical
## Testing

Run comprehensive tests:

```bash
# PostgreSQL connectivity
psql -h localhost -U bruce -d bruce_knowledge -c "SELECT COUNT(*) FROM bibliotheken;"

# Embedding generation
python knowledge/services/hierarchical_embedder.py

# Search engine MVP
python knowledge/services/hierarchical_search_mvp.py

# End-to-end (after Day 5)
./out/build/x64-Release/test_e2e_hierarchical
```

## Performance Targets

- **Search latency**: < 500ms (3-level MVP)
- **Embedding generation**: < 100ms per vector
- **Cascade filtering**: 10-100x reduction per level
- **Result consistency**: 100% deterministic

## Integration with Bruce Core

Bruce v6 state vectors (7D) map to hierarchical levels:

```
State.vec[0] → BibliothekID
State.vec[1] → KategorieID
State.vec[2] → RegalID
State.vec[3] → BuchID
State.vec[4] → KapitelID
State.vec[5] → SeiteID
State.vec[6] → VektorenID (pointer to 64D embedding)
```

The `HierarchicalGuard` in Bruce core validates paths without performing search itself.

## Documentation References

- `CLAUDE_CODE_PROMPT_HIERARCHICAL.md` - 7-day task breakdown
- `IMPLEMENTATION_PLAN_HIERARCHICAL.md` - Detailed technical specifications
- `ROADMAP_HIERARCHICAL.md` - Long-term vision and phases

## Troubleshooting

### PostgreSQL connection fails
```bash
# Check if container is running
docker-compose ps

# View logs
docker-compose logs postgres

# Restart
docker-compose restart postgres
```

### Ollama not responding
```bash
# Check if container is running
docker-compose ps

# Pull model manually
docker-compose exec ollama ollama pull nomic-embed-text

# Test
docker-compose exec ollama ollama run nomic-embed-text "test"
```

### Python import errors
```bash
# Reinstall dependencies
pip install --force-reinstall -r knowledge/requirements.txt

# Check Python version (3.10+)
python --version
```

## Contributing

When adding new functionality:
1. Add migrations for schema changes
2. Update tests for new services
3. Document in README
4. Run full test suite before committing
5. Update progress in task list
