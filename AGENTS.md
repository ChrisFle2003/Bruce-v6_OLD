# Repository Guidelines

## Project Structure & Module Organization
- `src/`: C++ implementation (`core_*`, `io_*`, `hierarchical_guard`, CLI entrypoint).
- `include/bruce/`: Public headers grouped by domain (`core/`, `io/`, `knowledge/`, `observer/`).
- `tests/`: C++ executable-style tests (`test_core.cpp`, `test_v6.cpp`, `test_hierarchical_guard.cpp`).
- `knowledge/`: Python knowledge services, DB migrations, and Python tests.
- `project/`: Runtime JSON data (axes, states, rules, router, manifests).
- `io/schema/`: JSON schemas; `demo/` contains sample dataset variants.
- `out/`: build artifacts (generated; do not commit manual edits).

## Build, Test, and Development Commands
- Configure debug build: `cmake -S . -B out/build/x64-Debug -G Ninja -DCMAKE_BUILD_TYPE=Debug`
- Build all C++ targets: `cmake --build out/build/x64-Debug`
- Run CLI: `./out/build/x64-Debug/brucev4 --project project info`
- Run C++ tests:
  - `./out/build/x64-Debug/test_core`
  - `./out/build/x64-Debug/test_v6`
  - `./out/build/x64-Debug/test_hierarchical_guard`
- Python setup: `pip install -r knowledge/requirements.txt`
- Python tests: `python -m pytest knowledge/tests -v`
- Start local DB for knowledge services: `docker-compose up -d`

## Coding Style & Naming Conventions
- C++: C++20, 2-space indentation, braces on new lines in CLI/core code, `snake_case` for files/functions, `PascalCase` for types.
- Python: PEP 8 style, `snake_case` modules/functions, test classes prefixed with `Test`.
- Keep domain prefixes in filenames (for example, `core_ops.cpp`, `io_fields.cpp`) to preserve module clarity.

## Testing Guidelines
- Add C++ tests in `tests/test_<feature>.cpp` with deterministic assertions (`assert(...)`).
- Add Python tests in `knowledge/tests/test_<feature>.py` using `pytest`.
- Prefer mock/deterministic paths for embedding and IPC tests when external services are optional.
- Validate both layers when changing interfaces: C++ guard/IPC + Python services.

## Commit & Pull Request Guidelines
- This backup does not include `.git` history; use Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`) in imperative mood.
- Keep commits focused (code + tests + docs for one change).
- PRs should include: purpose, touched paths, test commands run, and sample CLI output/screenshots when behavior changes.

## Security & Configuration Tips
- Copy `.env.example` to `.env`; never commit secrets.
- Treat `project/` JSON as source-of-truth data; update matching manifests when adding/removing files.
