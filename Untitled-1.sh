cd C:\Users\chris\Desktop\Bruce_v6-main-backup\Bruce_v6-main_v2\Bruce_main_raw

docker-compose up -d
bash knowledge/scripts/init_db.sh
pip install -r knowledge/requirements.txt

# Development cycle
cmake --build out/build/x64-Debug          # Rebuild C++
python -m pytest knowledge/tests -v        # Run Python tests
./out/build/x64-Debug/test_core            # Run C++ tests

# Testing specific components
./out/build/x64-Debug/test_hierarchical_guard  # Guard validation
python -m pytest knowledge/tests/test_e2e_integration.py -v  # End-to-end

# Profiling
python knowledge/tests/test_6_level_cascade.py  # Cascade efficiency
python -c "from hierarchical_search_mvp import HierarchicalSearchMVP; ..."

# Database inspection
psql -h localhost -U bruce -d bruce_knowledge -c "\dt"      # List tables
psql -h localhost -U bruce -d bruce_knowledge -c "SELECT COUNT(*) FROM seiten;"  # Count pages

# Infrastructure
docker-compose ps           # Check running containers
docker-compose logs -f      # Stream logs (Ctrl+C to exit)