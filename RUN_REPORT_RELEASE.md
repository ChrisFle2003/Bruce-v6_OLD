# Release Build and Runtime Report

Date: 2026-02-04  
Host: Windows (PowerShell, MSVC 2022 Build Tools)

## 1) Requested Release Configure/Build Commands

Attempted exactly as requested:

```powershell
cmake -S . -B out/build/x64-Release -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build out/build/x64-Release
```

Result:
- Configure failed because `Ninja` is not installed (`CMAKE_MAKE_PROGRAM` missing).
- Build could not proceed with Ninja generator.

## 2) Windows Fallback Used to Complete Release Build

Used Visual Studio generator in the same build directory:

```powershell
cmake -S . -B out/build/x64-Release -G "Visual Studio 17 2022" -A x64
cmake --build out/build/x64-Release --config RelWithDebInfo --target brucev4 test_core test_v6 bench_mix_v4
```

Built successfully:
- `out/build/x64-Release/RelWithDebInfo/brucev4.exe`
- `out/build/x64-Release/RelWithDebInfo/test_core.exe`
- `out/build/x64-Release/RelWithDebInfo/test_v6.exe`
- `out/build/x64-Release/RelWithDebInfo/bench_mix_v4.exe`

Known build blocker:
- `test_hierarchical_guard` fails on Windows because `src/ipc_client.cpp` includes `sys/socket.h` (Unix-only).

## 3) Bruce Runtime Execution (Release)

Executed and passed:
- `brucev4 --project project info`
- `brucev4 --project project validate`
- `brucev4 --project project list-states`
- `brucev4 --project project show-state 1`
- `brucev4 --project project mix 1 2`
- `brucev4 --project project distance 1 2`
- `brucev4 --project project allowed 1 2`
- `brucev4 --project project fields list`
- `brucev4 --project project dataset fields-check`
- `brucev4 --project project fields build 1`
- `brucev4 --project project route --text "do now"`
- `brucev4 --project project dump --out out/build/x64-Release/RelWithDebInfo/project_dump.json`

Additional binaries:
- `test_core.exe` passed (exit code `0`)
- `test_v6.exe` passed (exit code `0`)
- `bench_mix_v4.exe` passed and reported: `mix loops=200000 dims=7 : 1098 us`

## 4) Python Knowledge Tests

Command:

```powershell
python -m pytest knowledge/tests -q
```

Result: `19 passed, 4 failed, 7 warnings`
- 3 failures due to missing `socket.AF_UNIX` on Windows in `knowledge/services/socket_server.py`.
- 1 failure due to missing `SearchServiceClient` export in `socket_server.py`.

## 5) knowledge/README.md Workflow Execution (Windows)

I read `knowledge/README.md` and executed the relevant steps that are available on this Windows host:

1. Start services

```powershell
docker compose up -d
docker compose ps
```

Status:
- `bruce-postgres` running and healthy on `5433`.

2. Verify DB schema

```powershell
docker exec bruce-postgres psql -U bruce -d bruce_knowledge -c "\dt"
```

Result:
- Tables present: `bibliotheken`, `kategorien`, `regale`, `buecher`, `kapitel`, `seiten`, `vektoren`.

3. Python dependency install

```powershell
pip install -r knowledge/requirements.txt
```

Result:
- Failed on Python `3.14.0` because `psycopg2-binary==2.9.9` attempted source build and required `pg_config`.

4. README test/runtime commands

```powershell
python -m pytest knowledge/tests/test_embedder.py -v
python knowledge/services/hierarchical_search_mvp.py
python knowledge/services/hierarchical_embedder.py
python -m pytest knowledge/tests -q
```

Results:
- `test_embedder.py`: passed (`10/10`).
- `hierarchical_search_mvp.py`: passed, connected to PostgreSQL and Ollama, produced cascade-search results.
- `hierarchical_embedder.py`: mostly runs, then fails on Windows console encoding (`UnicodeEncodeError` for `≠`).
- full `knowledge/tests`: partial pass (`19 passed, 4 failed`) with AF_UNIX and missing `SearchServiceClient` issues.
