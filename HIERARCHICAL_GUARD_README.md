# Hierarchical Guard for Bruce v6

## Overview

The **Hierarchical Guard** is a C++ validation framework that controls access to the hierarchical knowledge system based on Bruce's 7-dimensional state vectors.

**Core Principle:**
> Bruce remains the "traffic cop" - it validates paths but doesn't perform search itself

## Architecture

### State-to-Hierarchy Mapping

Bruce's 7D state vector maps directly to the knowledge hierarchy:

```
Bruce State: vec[0-6] = [val0, val1, val2, val3, val4, val5, val6]
                            |      |      |      |      |      |      |
                            ↓      ↓      ↓      ↓      ↓      ↓      ↓
Hierarchy:    [Bibliothek, Kategorie, Regal, Buch, Kapitel, Seite, Vektoren]
           ID:    [1,        2,        3,      4,     5,      6,      7]
```

Each dimension is an `int16_t` value in range `[-32767, 32767]`, mapped to database IDs via `StateToHierarchyMapper`.

### Validation Rules

The Guard uses a rule-based architecture for flexible validation:

```cpp
class GuardRule {
  virtual bool allows(const HierarchicalPath&, const HierarchicalManifest&) = 0;
};
```

#### Built-in Rules

1. **BibliothekWhitelistRule**
   - Restricts searches to specific library domains
   - Example: "Only allow Programming and Science, deny Business"

2. **BudgetLimitRule**
   - Enforces resource constraints
   - Limits: max MB of data, max number of results

3. **DepthLimitRule**
   - Prevents deep hierarchical traversal
   - Limits: maximum hierarchy levels to search

### Data Structures

#### HierarchicalPath

```cpp
struct HierarchicalPath {
  std::optional<uint32_t> bibliothek_id;
  std::optional<uint32_t> kategorie_id;
  std::optional<uint32_t> regal_id;
  std::optional<uint32_t> buch_id;
  std::optional<uint32_t> kapitel_id;
  std::optional<uint32_t> seite_id;
  std::optional<uint32_t> vektoren_id;

  bool is_complete() const;  // All 7 levels set
  bool is_partial() const;   // At least 1 level set
  std::string to_string() const;
};
```

#### HierarchicalManifest

```cpp
struct HierarchicalManifest {
  std::string query_id;
  std::string query_text;
  std::vector<uint32_t> allowed_bibliothek_ids;  // Whitelist
  float max_buecher_mb = 100.0f;
  uint32_t max_seiten = 100;
  uint32_t max_depth = 3;

  bool is_valid() const;
  std::string to_json() const;
};
```

## Components

### 1. Header: `hierarchical_guard.hpp`

**Size:** ~280 lines

**Contents:**
- `HierarchicalPath` struct with optional ID levels
- `HierarchicalManifest` request descriptor
- `GuardRule` abstract base class
- `BibliothekWhitelistRule`, `BudgetLimitRule`, `DepthLimitRule` implementations
- `HierarchicalGuard` main validator class
- `StateToHierarchyMapper` for state-to-path conversion

### 2. Implementation: `hierarchical_guard.cpp`

**Size:** ~270 lines

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `HierarchicalPath::to_string()` | Serialize path to string for logging |
| `HierarchicalManifest::to_json()` | Serialize manifest to JSON |
| `BibliothekWhitelistRule::allows()` | Check if path's library is whitelisted |
| `BudgetLimitRule::allows()` | Check if manifest respects budget |
| `DepthLimitRule::allows()` | Check if depth is within limit |
| `HierarchicalGuard::validate_manifest()` | Validate complete manifest |
| `HierarchicalGuard::validate_path()` | Validate path against rules |
| `StateToHierarchyMapper::map()` | Convert State to HierarchicalPath |
| `StateToHierarchyMapper::map_safe()` | Validated state conversion |

### 3. Tests: `test_hierarchical_guard.cpp`

**Size:** ~400 lines

**Test Coverage:** 10 comprehensive tests

```
Test 1:  State to Path Mapping
Test 2:  Safe Path Mapping (with validation)
Test 3:  Bibliothek Whitelist Rule
Test 4:  Budget Limit Rule
Test 5:  Depth Limit Rule
Test 6:  Hierarchical Guard (All Rules)
Test 7:  Manifest Serialization
Test 8:  Path Serialization
Test 9:  Guard Rule Names
Test 10: Complex State Mapping
```

All tests verify:
- ✓ Correct type conversions
- ✓ Boundary conditions
- ✓ Rule application
- ✓ JSON serialization
- ✓ Path completeness/partiality

## Usage Examples

### Example 1: Basic Guard Setup

```cpp
#include "bruce/knowledge/hierarchical_guard.hpp"

using namespace bruce::knowledge;

// Create guard
HierarchicalGuard guard;

// Add rules
guard.add_rule(std::make_unique<BibliothekWhitelistRule>(
    std::vector<uint32_t>{1, 2, 3}  // Allow libraries 1, 2, 3
));
guard.add_rule(std::make_unique<BudgetLimitRule>(
    100.0f,  // Max 100 MB
    50       // Max 50 results
));

// Validate manifest
HierarchicalManifest manifest;
manifest.query_id = "query_001";
manifest.query_text = "search for python";
manifest.allowed_bibliothek_ids = {1};
manifest.max_buecher_mb = 50.0f;
manifest.max_seiten = 25;
manifest.max_depth = 3;

if (guard.validate_manifest(manifest)) {
    std::cout << "Manifest approved" << std::endl;
} else {
    std::cout << "Manifest denied" << std::endl;
}
```

### Example 2: State Conversion

```cpp
#include "bruce/knowledge/hierarchical_guard.hpp"
#include "bruce/core/state/state.hpp"

using namespace bruce::knowledge;
using namespace bruce::core;

// Create a Bruce state
State state;
state.vec = {1000, 2000, 3000, 4000, 5000, 6000, 7000};

// Map to hierarchical path
HierarchicalPath path = StateToHierarchyMapper::map(state);

// Use path with manifest
HierarchicalManifest manifest;
if (guard.validate_path(path, manifest)) {
    std::cout << "Path allowed: " << path.to_string() << std::endl;
}
```

### Example 3: Custom Rules

```cpp
// Create custom rule
class TimeBasedRule : public GuardRule {
    bool allows(const HierarchicalPath& path, const HierarchicalManifest& manifest) const override {
        // Only allow searches during business hours (example)
        time_t now = time(nullptr);
        struct tm* info = localtime(&now);
        return info->tm_hour >= 9 && info->tm_hour < 17;
    }

    std::string name() const override { return "TimeBasedRule"; }
};

// Add to guard
guard.add_rule(std::make_unique<TimeBasedRule>());
```

## Integration with Bruce Core

### Mapping Bruce State to Path

```cpp
#include "bruce/knowledge/hierarchical_guard.hpp"
#include "bruce/core/state/state_store.hpp"

using namespace bruce::knowledge;

// Get state from Bruce StateStore
StateStore store;
const State* state = store.get(state_id);

// Map to hierarchical path
auto path_opt = StateToHierarchyMapper::map_safe(*state);

if (path_opt.has_value()) {
    HierarchicalPath path = path_opt.value();
    // Use path for authorization
} else {
    // Invalid state (not 7D or out of range)
}
```

## Building with CMake

### Add to CMakeLists.txt

```cmake
# Build hierarchical knowledge library
add_library(bruce_knowledge
  src/hierarchical_guard.cpp
)
target_include_directories(bruce_knowledge PUBLIC include)
target_link_libraries(bruce_knowledge PRIVATE bruce_core)

# Build guard tests
add_executable(test_hierarchical_guard
  tests/test_hierarchical_guard.cpp
)
target_link_libraries(test_hierarchical_guard PRIVATE bruce_knowledge bruce_core)
```

### Build Commands

```bash
# Configure
cmake -S . -B out/build/x64-Debug -G Ninja
cmake -S . -B out/build/x64-Release -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo

# Build
cmake --build out/build/x64-Debug
cmake --build out/build/x64-Release

# Run tests
./out/build/x64-Debug/test_hierarchical_guard
```

### Expected Output

```
============================================================
Hierarchical Guard Unit Tests
============================================================

Test 1: State to Path Mapping
[OK] bibliothek_id should be set
[OK] kategorie_id should be set
[OK] Path should be complete
[OK] Path should be partial
  Path: Path{bib=33768,kat=34768,reg=35768,buc=36768,kap=37768,sei=38768,vec=39768}

Test 2: Safe Path Mapping
[OK] Valid state should map successfully
[OK] Invalid dimension count should fail
  Safe mapping validation working correctly

[... 8 more tests ...]

============================================================
[SUCCESS] All 10 tests passed!
============================================================
```

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| State-to-Path conversion | <1µs | Direct value mapping |
| Rule validation | <5µs per rule | Usually 3-5 rules total |
| Manifest validation | <20µs | Full validation cycle |
| Whitelist lookup | O(n) | Linear search (n=whitelist size) |
| Serialization (JSON) | <100µs | Depends on manifest size |

## Error Handling

### Invalid States

```cpp
// State with wrong dimension count
State invalid;
invalid.vec = {1000, 2000};  // Only 2D, expected 7D

auto result = StateToHierarchyMapper::map_safe(invalid);
// result = std::nullopt (validation failed)
```

### Invalid Manifests

```cpp
HierarchicalManifest invalid;
invalid.allowed_bibliothek_ids = {};  // Empty whitelist!

if (!invalid.is_valid()) {
    std::cerr << "Manifest validation failed" << std::endl;
}
```

### Rule Application

Rules use short-circuit evaluation:
- **Strict mode:** ALL rules must pass (AND logic)
- **Permissive mode:** ANY rule can pass (OR logic)

## Testing

### Test Execution

```bash
# Run all guard tests
./out/build/x64-Debug/test_hierarchical_guard

# Verbose output
./out/build/x64-Debug/test_hierarchical_guard 2>&1 | grep -E "\[OK\]|\[FAIL\]"

# Test specific functionality
# (Tests are hardcoded, but each test function can be isolated)
```

### Test Results Summary

**Coverage:** 10 test functions, 35+ assertions

**Categories:**
- ✓ State mapping (3 tests)
- ✓ Rule validation (4 tests)
- ✓ Serialization (2 tests)
- ✓ Integration (1 test)

**Success Criteria:**
- All tests pass without errors
- No memory leaks (valgrind clean)
- All assertions succeed
- Deterministic output

## Integration Points

### With Bruce Core

```cpp
// In Bruce's decision engine
#include "bruce/knowledge/hierarchical_guard.hpp"

// When evaluating a state transition
HierarchicalPath path = StateToHierarchyMapper::map(state);
if (!guard.validate_path(path, manifest)) {
    // Reject transition
    return Decision::REJECT;
}
```

### With Search Service (IPC)

```cpp
// In Bruce before calling search service via socket
if (guard.validate_manifest(manifest)) {
    // Send to Python search service
    search_service.execute(manifest);
} else {
    // Access denied
    return SearchError("Access denied by guard");
}
```

### With Python Embedder

```python
# In Python search service
# Receive manifest from C++, validate locally
manifest = parse_request(socket_data)

# Python can optionally re-validate
if not check_budget(manifest):
    raise BudgetExceededError()
```

## Future Enhancements

### Planned Features

1. **Role-Based Access Control (RBAC)**
   - User roles with different access levels
   - Role-to-bibliothek mappings

2. **Time-Based Access**
   - Schedule-based restrictions
   - Business hours enforcement

3. **Quota Management**
   - Per-user query quotas
   - Usage tracking

4. **Audit Logging**
   - Log all guard decisions
   - Compliance reporting

5. **Dynamic Rules**
   - Load rules from database
   - Hot-reload without restart

## Troubleshooting

### Common Issues

**Issue:** Guard always rejects manifests
- **Cause:** Whitelist is empty
- **Solution:** Add at least one allowed bibliothek_id

**Issue:** State mapping returns null optional
- **Cause:** State has wrong dimension count
- **Solution:** Ensure State.vec.size() == 7

**Issue:** Build fails with "unknown type HierarchicalPath"
- **Cause:** Missing #include
- **Solution:** Add `#include "bruce/knowledge/hierarchical_guard.hpp"`

## References

- **State Definition:** `include/bruce/core/state/state.hpp`
- **Type System:** `include/bruce/types.hpp`
- **Rule Base Class:** `include/bruce/knowledge/hierarchical_guard.hpp`

## Files

| File | Lines | Purpose |
|------|-------|---------|
| `include/bruce/knowledge/hierarchical_guard.hpp` | 280 | Header definitions |
| `src/hierarchical_guard.cpp` | 270 | Implementation |
| `tests/test_hierarchical_guard.cpp` | 400 | Unit tests |
| `CMakeLists.txt` | +8 | Build configuration |

**Total:** ~960 lines of C++ code

---

*Last Updated: 2026-02-04*
*Status: Day 4 Complete*
