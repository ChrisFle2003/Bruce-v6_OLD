# CLI.md

Command-line interface documentation for Bruce v4 - Deterministischer semantischer Rechenkern (Deterministic Semantic Computation Engine)

## Building the CLI

### Debug Build

```bash
# Configure CMake for debug build (with debugging symbols)
cmake -S . -B out/build/x64-Debug -G Ninja

# Build all targets including brucev4 CLI
cmake --build out/build/x64-Debug

# Executable location
./out/build/x64-Debug/brucev4.exe
```

**Debug Build Characteristics:**
- Full debugging symbols
- No optimizations (slower execution)
- Better for development and error diagnosis
- Larger executable size

### Release Build

```bash
# Configure CMake for release build (with optimizations)
cmake -S . -B out/build/x64-Release -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo

# Build all targets including brucev4 CLI
cmake --build out/build/x64-Release

# Executable location
./out/build/x64-Release/brucev4.exe
```

**Release Build Characteristics:**
- Optimized execution (-O3 level)
- Minimal debugging symbols (RelWithDebInfo retains some)
- Faster performance (determinism guaranteed)
- Smaller executable size

## Basic Usage

All commands require the `--project` flag pointing to a project directory:

```bash
brucev4 --project <project_path> <command> [arguments]
```

**Required Project Structure:**

```
project/
├── axes/
│   └── axes.json              # Axis definitions with bounds
├── cores/
│   └── [core definitions]      # Core group definitions
├── states/
│   └── *.json                  # Initial state definitions
├── rules/
│   └── rules.json              # Baseline transition rules
├── changes/
│   └── patches.jsonl           # Append-only event log
├── fields/                     # Field definitions (2D projections)
├── projections/                # Computed projections
├── meta/
│   └── viewer.json             # 2D viewer configuration
├── logs/                       # Query/operation logs
└── [other dirs]
```

## Commands

### 1. Project Information

#### `info`
Display project overview: axes, state count, rule count, field info.

```bash
brucev4 --project ./project info
```

**Output:**
```
Project: ./project
Axes: 7 dimensions
  analyse ↔ execution : <count>
  abstract ↔ concrete : <count>
  [additional axes...]
States: 145 total
Rules: 12 defined
Fields: 5 available
```

#### `validate`
Validate project structure and integrity. Checks:
- Schema validity
- Foreign key references
- Vector value ranges
- Rule definitions

```bash
brucev4 --project ./project validate
```

**Output:**
```
[OK] Axes loaded
[OK] States loaded
[OK] Rules loaded
[OK] All validations passed
```

---

### 2. State Management

#### `list-states`
List all states in the project with IDs and core associations.

```bash
brucev4 --project ./project list-states
```

**Output:**
```
State ID    Core ID    Dims    Status
0           1          7       [initial]
1           1          7       [imported]
2           2          7       [imported]
...
```

#### `show-state <state_id>`
Display detailed information about a single state.

```bash
brucev4 --project ./project show-state 42
```

**Arguments:**
- `state_id` (integer): The state ID to display

**Output:**
```
State 42 (Core 1)
analyse ↔ execution : 150
abstract ↔ concrete : -200
emotional ↔ rational : 50
[additional dimensions...]
```

#### `new-state <core_id> <v1> <v2> ... <vN>`
Create a new state and append to event log. Values are automatically clamped to axis bounds.

```bash
brucev4 --project ./project new-state 1 100 -200 50 0 25 -150 300
```

**Arguments:**
- `core_id` (integer): Group ID for the new state
- `v1, v2, ..., vN` (integers): Vector values for each dimension

**Output:**
```
[OK] State created with ID: 1001
[OK] Event appended to patches.jsonl
```

**Notes:**
- New states get monotonically increasing IDs
- Values outside axis bounds are clamped
- Changes are append-only (immutable)
- State ID is printed to output

---

### 3. Vector Operations

#### `mix <state_id_A> <state_id_B>`
Average two states element-wise with clamping to axis bounds.

```bash
brucev4 --project ./project mix 0 1
```

**Arguments:**
- `state_id_A`, `state_id_B` (integers): IDs of states to mix

**Output:**
```
Mix(State 0, State 1):
analyse ↔ execution : 75
abstract ↔ concrete : -100
[average of each dimension...]
```

**Formula:** `result[i] = (stateA[i] + stateB[i]) / 2` (clamped to bounds)

#### `distance <state_id_A> <state_id_B>`
Calculate Manhattan (L1) distance between two states.

```bash
brucev4 --project ./project distance 0 1
```

**Arguments:**
- `state_id_A`, `state_id_B` (integers): IDs of states

**Output:**
```
Distance (L1): 1250
```

**Formula:** `sum(|stateA[i] - stateB[i]|)` for all dimensions

---

### 4. Rule Management

#### `learn-add-rule <name> <d1> <d2> ... <dN>`
Define a new transition rule. Each parameter specifies max delta per dimension.

```bash
brucev4 --project ./project learn-add-rule "conservative" 50 50 25 100 10 200 50
```

**Arguments:**
- `name` (string): Human-readable rule name
- `d1, d2, ..., dN` (integers): Max allowed change per dimension

**Output:**
```
[OK] Rule 'conservative' created with ID: 5
[OK] Event appended to patches.jsonl
```

**Notes:**
- Rule defines "allowed transitions": |state_from[i] - state_to[i]| <= d[i]
- New rules get monotonically increasing IDs
- Append-only (immutable)

#### `allowed <from_state_id> <to_state_id>`
Check if a state transition is allowed by any defined rule.

```bash
brucev4 --project ./project allowed 0 1
```

**Arguments:**
- `from_state_id`, `to_state_id` (integers): State IDs

**Output:**
```
Transition allowed: YES
  Rule: "conservative" (max deltas: 50 50 25 100 10 200 50)
  Actual deltas: 10 5 2 15 1 30 5
```

or

```
Transition allowed: NO
  Violates all rules
```

---

### 5. Field & Projection Management

#### `fields list`
List all available 2D projection fields.

```bash
brucev4 --project ./project fields list
```

**Output:**
```
Field ID    Name                Axes
0           "Analysis Space"    analyse ↔ execution vs abstract ↔ concrete
1           "Social-Technical"  social ↔ technical vs emotional ↔ rational
[additional fields...]
```

#### `fields build <field_id>`
Compute 2D projections for a specific field across all states.

```bash
brucev4 --project ./project fields build 0
```

**Arguments:**
- `field_id` (integer): Field ID to compute

**Output:**
```
[OK] Computing projections for field 0 (Analysis Space)
[OK] 145 states projected
[OK] Results written to projections/field_0.json
```

#### `dataset fields-check`
Validate field definitions and check projection consistency.

```bash
brucev4 --project ./project dataset fields-check
```

**Output:**
```
[OK] 5 fields loaded
[OK] All field axes valid
[OK] Projection metadata consistent
```

---

### 6. Data Export

#### `dump --out <output_file>`
Export complete project snapshot including:
- All states with vectors
- All rules with definitions
- Computed 2D projections
- Metadata and configuration
- Allowed transition analysis

```bash
brucev4 --project ./project dump --out backup.json
```

**Arguments:**
- `--out <path>`: Output file path (required)

**Output:**
```
[OK] Dumping project to backup.json
[OK] States: 145 exported
[OK] Rules: 12 exported
[OK] Projections: 5 computed
[OK] Dump complete: 2.3 MB
```

**Output Format:**
```json
{
  "metadata": {
    "timestamp": "2026-02-04T21:00:00Z",
    "dimensions": 7,
    "state_count": 145,
    "rule_count": 12
  },
  "axes": [...],
  "states": [...],
  "rules": [...],
  "view2d": {...},
  "allowed": {...}
}
```

---

## Common Workflows

### Workflow 1: Explore Project State Space

```bash
# 1. Validate project integrity
brucev4 --project ./project validate

# 2. Show project overview
brucev4 --project ./project info

# 3. List all states
brucev4 --project ./project list-states

# 4. Examine a specific state
brucev4 --project ./project show-state 42

# 5. Check distances between states
brucev4 --project ./project distance 0 42
brucev4 --project ./project distance 0 1
```

### Workflow 2: Test State Transitions

```bash
# 1. Check if transition is allowed
brucev4 --project ./project allowed 0 1

# 2. Check another transition
brucev4 --project ./project allowed 1 5

# 3. View rule that allows the transition
# (output shows matching rule details)
```

### Workflow 3: Create and Test New State

```bash
# 1. Create a new state
brucev4 --project ./project new-state 1 100 50 -25 0 150 200 -100

# 2. Note the returned ID (e.g., 1001)
# 3. Show the new state
brucev4 --project ./project show-state 1001

# 4. Test transitions from/to new state
brucev4 --project ./project allowed 0 1001
brucev4 --project ./project allowed 1001 1

# 5. Compare with existing states
brucev4 --project ./project distance 0 1001
brucev4 --project ./project distance 1 1001
```

### Workflow 4: Add Custom Rule

```bash
# 1. Add a new transition rule
brucev4 --project ./project learn-add-rule "aggressive" 500 500 200 300 100 400 200

# 2. Test transitions with the new rule
brucev4 --project ./project allowed 0 10

# 3. List states and check which rule allows what
```

### Workflow 5: Generate Visualizations

```bash
# 1. Validate existing fields
brucev4 --project ./project fields list

# 2. Rebuild all 2D projections
brucev4 --project ./project fields build 0
brucev4 --project ./project fields build 1
# ... for each field

# 3. Export complete snapshot with projections
brucev4 --project ./project dump --out visualization_snapshot.json

# 4. Use visualization_snapshot.json in viewer
```

### Workflow 6: Full Project Backup

```bash
# 1. Validate before export
brucev4 --project ./project validate

# 2. Export complete snapshot
brucev4 --project ./project dump --out backups/backup_$(date +%Y%m%d_%H%M%S).json

# 3. Verify export
brucev4 --project ./project info
```

---

## Project Directory Structure Details

### `axes/axes.json`

Defines the N-dimensional vector space with axis ranges and labels.

```json
{
  "scale": {
    "min": -10000,
    "max": 10000
  },
  "axes": [
    {
      "negative": "analyse",
      "positive": "execution"
    },
    {
      "negative": "abstract",
      "positive": "concrete"
    }
  ]
}
```

**Note:** All vector values are clamped to the range [min, max].

### `cores/`

Contains core group definitions. Each core represents a semantic domain or category.

```json
{
  "core_id": 1,
  "name": "Thinking Patterns",
  "description": "..."
}
```

### `states/*.json`

Individual state definitions. Format:

```json
{
  "id": 0,
  "core_id": 1,
  "version": "v1",
  "vec": [100, -200, 50, 0, 25, -150, 300]
}
```

### `rules/rules.json`

Defines allowed state transitions. Example:

```json
{
  "rules": [
    {
      "name": "conservative",
      "max_deltas": [50, 50, 25, 100, 10, 200, 50]
    }
  ]
}
```

Transition from `state_A` to `state_B` is allowed if:
```
|state_A[i] - state_B[i]| <= max_deltas[i]  for all i
```

### `changes/patches.jsonl`

Append-only event log. Each line is a JSON object recording state/rule additions.

```json
{"type": "state_added", "id": 1001, "core_id": 1, "vec": [...]}
{"type": "rule_added", "name": "aggressive", "deltas": [...]}
```

### `fields/`

Field definitions for 2D projections (viewer-specific).

```json
{
  "field_id": 0,
  "name": "Analysis Space",
  "x_axis": 0,
  "y_axis": 1
}
```

### `projections/`

Computed 2D projections for all states. Auto-generated by `fields build <id>`.

### `meta/viewer.json`

Configuration for 2D visualization (observer-only, not used by core).

---

## Tips & Troubleshooting

### Project Not Found

**Error:** `cannot load project: <path>`

**Solution:**
- Verify path exists: `ls <path>`
- Ensure project structure is complete
- Check file permissions

```bash
# Debug: List project directory
ls -la ./project/
```

### Invalid State ID

**Error:** `State <id> not found`

**Solution:**
- List valid state IDs first: `brucev4 --project ./project list-states`
- Note: State IDs range from 0 to (count-1) for initial states
- New states have higher IDs (monotonically increasing)

### Vector Dimension Mismatch

**Error:** `Expected 7 values, got 5`

**Solution:**
- Check axes count: `brucev4 --project ./project info`
- Provide exactly N values (one per dimension)

```bash
# Correct: 7 dimensions
brucev4 --project ./project new-state 1 100 50 -25 0 150 200 -100

# Incorrect: only 5 values
brucev4 --project ./project new-state 1 100 50 -25 0 150
```

### Values Out of Bounds

**Note:** Values are automatically clamped, not rejected.

```bash
# If axes.json has min=-10000, max=10000:
brucev4 --project ./project new-state 1 50000 50 -25 0 150 200 -100

# Result: first dimension clamped to 10000 (the max)
```

To verify: `brucev4 --project ./project show-state <id>`

### Transition Not Allowed

**Problem:** `brucev4 --project ./project allowed A B` returns NO

**Solution:**
1. Check distance: `brucev4 --project ./project distance A B`
2. Check rules: `brucev4 --project ./project info` (shows rules)
3. Review each rule's max_deltas

```bash
# Example: if distance is 1500 but all rules only allow 500 per dimension
# on average, the transition won't be allowed
```

### Projections Not Generated

**Problem:** Field commands fail or no projections found

**Solution:**
```bash
# Rebuild all projections
brucev4 --project ./project fields list      # Check field IDs
brucev4 --project ./project fields build 0   # Build field 0
brucev4 --project ./project fields build 1   # Build field 1
# ... repeat for all fields
```

### Large Dump Files

**Tip:** Dumps include all states and computed projections. For large projects (10K+ states), export files can be 50+ MB.

```bash
# Use compression if available
brucev4 --project ./project dump --out backup.json
gzip backup.json  # Reduces size significantly
```

---

## Performance Notes

### Determinism Guarantee

All operations are **100% deterministic**:
- Same project + same command = identical output every time
- No floating-point precision issues (uses fixed int16 arithmetic internally)
- Suitable for test comparisons and audit trails

### Scalability

- **States:** Tested with 10,000+ states
- **Rules:** Each rule adds minimal overhead
- **Fields:** Projection computation is O(n) per field (fast)
- **Distances:** O(n) where n = dimension count (always 7-10)

### Memory Usage

- State storage: ~28 bytes per state (7 int32 values)
- Rule storage: ~112 bytes per rule (7 int32 deltas + metadata)
- Projection storage: ~16 bytes per state per field (2 float32 values)

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Project not found |
| 2 | Invalid command |
| 3 | Validation failed |
| 4 | State/rule not found |
| 5 | Invalid arguments |

---

## Example: Complete Session

```bash
# Setup: Configure and build
cmake -S . -B out/build/x64-Debug -G Ninja
cmake --build out/build/x64-Debug

# Use the CLI
cd out/build/x64-Debug

# Explore
./brucev4 --project ../../project info
./brucev4 --project ../../project list-states
./brucev4 --project ../../project show-state 0

# Test transitions
./brucev4 --project ../../project distance 0 1
./brucev4 --project ../../project allowed 0 1

# Create new state
./brucev4 --project ../../project new-state 1 100 -200 50 0 25 -150 300
# Returns: State created with ID: 1001

# Test new state
./brucev4 --project ../../project show-state 1001
./brucev4 --project ../../project distance 0 1001

# Add rule and test
./brucev4 --project ../../project learn-add-rule "permissive" 500 500 500 500 500 500 500
./brucev4 --project ../../project allowed 0 1001

# Export snapshot
./brucev4 --project ../../project dump --out snapshot.json
```

---

## Related Documentation

- **CLAUDE.md**: High-level architecture and project overview
- **IMPLEMENTATION_STATUS.md**: Project completion status and metrics
- **project/**: Example project with 7D axes and sample states
