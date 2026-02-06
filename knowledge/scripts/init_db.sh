#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Bruce Hierarchical Knowledge DB Initialization ===${NC}\n"

# Check if PostgreSQL is running
echo "1. Checking PostgreSQL connection..."
if ! psql -h localhost -U bruce -d bruce_knowledge -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${RED}❌ PostgreSQL not found at localhost:5433${NC}"
    echo "Ensure docker-compose is running:"
    echo "  docker-compose up -d"
    exit 1
fi
echo -e "${GREEN}✓ PostgreSQL connected${NC}\n"

# Run migrations
echo "2. Running migrations..."
if [ -f ./knowledge/migrations/001_base_schema.sql ]; then
    echo "   Running 001_base_schema.sql..."
    psql -h localhost -U bruce -d bruce_knowledge -f ./knowledge/migrations/001_base_schema.sql > /dev/null 2>&1
fi

if [ -f ./knowledge/migrations/002_hierarchical_library_schema.sql ]; then
    echo "   Running 002_hierarchical_library_schema.sql..."
    psql -h localhost -U bruce -d bruce_knowledge -f ./knowledge/migrations/002_hierarchical_library_schema.sql > /dev/null 2>&1
fi
echo -e "${GREEN}✓ Migrations completed${NC}\n"

# Verify schema
echo "3. Verifying schema..."
TABLES=$(psql -h localhost -U bruce -d bruce_knowledge -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';")
echo "   Tables found: $TABLES"

if [ "$TABLES" -ge 7 ]; then
    echo -e "${GREEN}✓ Schema verified (7+ tables)${NC}\n"
else
    echo -e "${RED}❌ Schema incomplete (expected 7+ tables, found $TABLES)${NC}\n"
    exit 1
fi

# Verify seed data
echo "4. Checking seed data..."
SEED_ROWS=$(psql -h localhost -U bruce -d bruce_knowledge -t -c "SELECT COUNT(*) FROM wissens_pfade;")
echo "   Seed paths found: $SEED_ROWS"

if [ "$SEED_ROWS" -ge 1 ]; then
    echo -e "${GREEN}✓ Seed data verified${NC}\n"
else
    echo -e "${YELLOW}⚠ No seed data found (expected after full migration)${NC}\n"
fi

# Check Vektoren table
echo "5. Checking vectors..."
VEC_COUNT=$(psql -h localhost -U bruce -d bruce_knowledge -t -c "SELECT COUNT(*) FROM vektoren;")
echo "   Vectors found: $VEC_COUNT"

if [ "$VEC_COUNT" -ge 1 ]; then
    echo -e "${GREEN}✓ Vector data present${NC}\n"
else
    echo -e "${YELLOW}⚠ No vectors found (expected after full migration)${NC}\n"
fi

echo -e "${GREEN}=== Database initialization complete ===${NC}\n"
echo "Next steps:"
echo "1. Install Python dependencies: pip install -r knowledge/requirements.txt"
echo "2. Start Ollama: docker-compose exec ollama ollama pull nomic-embed-text"
echo "3. Run Day 1 verification: bash knowledge/scripts/test_search_mvp.sh"
