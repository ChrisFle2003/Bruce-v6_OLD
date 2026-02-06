/*
  Unit Tests for Hierarchical Guard
  ==================================

  Tests state validation, path mapping, and guard rules.
*/

#include "bruce/knowledge/hierarchical_guard.hpp"
#include <cassert>
#include <iostream>
#include <vector>

using namespace bruce;
using namespace bruce::knowledge;
using namespace bruce::core;

// ============================================================
// Test Utilities
// ============================================================

void assert_true(bool condition, const std::string& message) {
  if (!condition) {
    std::cerr << "[FAIL] " << message << std::endl;
    exit(1);
  }
  std::cout << "[OK] " << message << std::endl;
}

void assert_equal(const std::string& a, const std::string& b, const std::string& message) {
  if (a != b) {
    std::cerr << "[FAIL] " << message << std::endl;
    std::cerr << "  Expected: " << b << std::endl;
    std::cerr << "  Got: " << a << std::endl;
    exit(1);
  }
  std::cout << "[OK] " << message << std::endl;
}

// ============================================================
// Test 1: State to Path Mapping
// ============================================================

void test_state_to_path_mapping() {
  std::cout << "\nTest 1: State to Path Mapping\n";

  // Create a 7D state
  State state;
  state.id = 1;
  state.core_id = 100;
  state.vec = {1000, 2000, 3000, 4000, 5000, 6000, 7000};

  // Map to path
  HierarchicalPath path = StateToHierarchyMapper::map(state);

  assert_true(path.bibliothek_id.has_value(), "bibliothek_id should be set");
  assert_true(path.kategorie_id.has_value(), "kategorie_id should be set");
  assert_true(path.is_complete(), "Path should be complete");
  assert_true(path.is_partial(), "Path should be partial");

  std::cout << "  Path: " << path.to_string() << std::endl;
}

// ============================================================
// Test 2: Safe Path Mapping (with validation)
// ============================================================

void test_safe_path_mapping() {
  std::cout << "\nTest 2: Safe Path Mapping\n";

  // Valid 7D state
  State valid_state;
  valid_state.vec = {0, 100, -100, 1000, -1000, 32767, -32767};

  auto result = StateToHierarchyMapper::map_safe(valid_state);
  assert_true(result.has_value(), "Valid state should map successfully");

  // Invalid state (wrong dimension count)
  State invalid_state;
  invalid_state.vec = {1000, 2000, 3000};  // Only 3D

  result = StateToHierarchyMapper::map_safe(invalid_state);
  assert_true(!result.has_value(), "Invalid dimension count should fail");

  std::cout << "  Safe mapping validation working correctly\n";
}

// ============================================================
// Test 3: Bibliothek Whitelist Rule
// ============================================================

void test_bibliothek_whitelist_rule() {
  std::cout << "\nTest 3: Bibliothek Whitelist Rule\n";

  // Create rule allowing only bibliotheken 1, 2, 3
  std::vector<uint32_t> whitelist = {1, 2, 3};
  auto rule = std::make_unique<BibliothekWhitelistRule>(whitelist);

  // Test whitelist check
  assert_true(rule->is_allowed(1), "ID 1 should be allowed");
  assert_true(rule->is_allowed(2), "ID 2 should be allowed");
  assert_true(!rule->is_allowed(5), "ID 5 should not be allowed");

  // Test rule in context of path
  HierarchicalPath allowed_path;
  allowed_path.bibliothek_id = 1;

  HierarchicalPath denied_path;
  denied_path.bibliothek_id = 5;

  HierarchicalManifest manifest;
  manifest.query_id = "test";
  manifest.allowed_bibliothek_ids = {1, 2, 3};

  assert_true(rule->allows(allowed_path, manifest), "Allowed path should pass");
  assert_true(!rule->allows(denied_path, manifest), "Denied path should fail");

  std::cout << "  Whitelist rule working correctly\n";
}

// ============================================================
// Test 4: Budget Limit Rule
// ============================================================

void test_budget_limit_rule() {
  std::cout << "\nTest 4: Budget Limit Rule\n";

  // Create rule limiting to 50MB and 100 items
  auto rule = std::make_unique<BudgetLimitRule>(50.0f, 100);

  HierarchicalPath path;
  path.bibliothek_id = 1;

  // Manifest within budget
  HierarchicalManifest within_budget;
  within_budget.query_id = "test1";
  within_budget.max_buecher_mb = 30.0f;
  within_budget.max_seiten = 50;

  // Manifest exceeding budget
  HierarchicalManifest exceeding_budget;
  exceeding_budget.query_id = "test2";
  exceeding_budget.max_buecher_mb = 100.0f;  // Exceeds 50MB limit
  exceeding_budget.max_seiten = 50;

  assert_true(rule->allows(path, within_budget), "Within-budget manifest should pass");
  assert_true(!rule->allows(path, exceeding_budget), "Over-budget manifest should fail");

  std::cout << "  Budget limit rule working correctly\n";
}

// ============================================================
// Test 5: Depth Limit Rule
// ============================================================

void test_depth_limit_rule() {
  std::cout << "\nTest 5: Depth Limit Rule\n";

  // Create rule limiting to 3-level depth
  auto rule = std::make_unique<DepthLimitRule>(3);

  // Shallow path (2 levels)
  HierarchicalPath shallow_path;
  shallow_path.bibliothek_id = 1;
  shallow_path.kategorie_id = 1;

  // Deep path (5 levels)
  HierarchicalPath deep_path;
  deep_path.bibliothek_id = 1;
  deep_path.kategorie_id = 1;
  deep_path.regal_id = 1;
  deep_path.buch_id = 1;
  deep_path.kapitel_id = 1;

  HierarchicalManifest manifest;
  manifest.query_id = "test";
  manifest.max_depth = 3;

  assert_true(rule->allows(shallow_path, manifest), "Shallow path should pass");
  assert_true(!rule->allows(deep_path, manifest), "Deep path should fail");

  std::cout << "  Depth limit rule working correctly\n";
}

// ============================================================
// Test 6: Hierarchical Guard (All Rules)
// ============================================================

void test_hierarchical_guard() {
  std::cout << "\nTest 6: Hierarchical Guard\n";

  // Create guard with multiple rules
  HierarchicalGuard guard;
  guard.add_rule(std::make_unique<BibliothekWhitelistRule>(std::vector<uint32_t>{1, 2}));
  guard.add_rule(std::make_unique<BudgetLimitRule>(100.0f, 100));
  guard.add_rule(std::make_unique<DepthLimitRule>(3));

  assert_true(guard.rule_count() == 3, "Guard should have 3 rules");

  // Valid manifest
  HierarchicalManifest valid;
  valid.query_id = "test1";
  valid.query_text = "valid query";
  valid.allowed_bibliothek_ids = {1};
  valid.max_buecher_mb = 50.0f;
  valid.max_seiten = 50;
  valid.max_depth = 3;

  assert_true(valid.is_valid(), "Manifest should be valid");
  assert_true(guard.validate_manifest(valid), "Valid manifest should pass guard");

  // Invalid manifest (no bibliotheken allowed)
  HierarchicalManifest invalid;
  invalid.query_id = "test2";
  invalid.query_text = "invalid query";
  invalid.allowed_bibliothek_ids = {};  // Empty!
  invalid.max_buecher_mb = 50.0f;
  invalid.max_seiten = 50;
  invalid.max_depth = 3;

  assert_true(!invalid.is_valid(), "Invalid manifest should fail validation");

  std::cout << "  Guard validation working correctly\n";
}

// ============================================================
// Test 7: Manifest Serialization
// ============================================================

void test_manifest_serialization() {
  std::cout << "\nTest 7: Manifest Serialization\n";

  HierarchicalManifest manifest;
  manifest.query_id = "query_001";
  manifest.query_text = "search for something";
  manifest.allowed_bibliothek_ids = {1, 2, 3};
  manifest.max_buecher_mb = 100.0f;
  manifest.max_seiten = 50;
  manifest.max_depth = 3;

  std::string json = manifest.to_json();

  assert_true(json.find("\"query_id\": \"query_001\"") != std::string::npos, "JSON should contain query_id");
  assert_true(json.find("\"max_buecher_mb\": 100") != std::string::npos, "JSON should contain max_buecher_mb");
  assert_true(json.find("\"allowed_bibliothek_ids\"") != std::string::npos, "JSON should contain whitelist");

  std::cout << "  Manifest serialization working correctly\n";
  std::cout << "  JSON preview:\n" << json << std::endl;
}

// ============================================================
// Test 8: Path Serialization
// ============================================================

void test_path_serialization() {
  std::cout << "\nTest 8: Path Serialization\n";

  HierarchicalPath path;
  path.bibliothek_id = 1;
  path.kategorie_id = 2;
  path.regal_id = 3;

  std::string str = path.to_string();

  assert_true(str.find("bib=1") != std::string::npos, "Path should contain bib=1");
  assert_true(str.find("kat=2") != std::string::npos, "Path should contain kat=2");
  assert_true(str.find("reg=3") != std::string::npos, "Path should contain reg=3");
  assert_true(!path.is_complete(), "Path should not be complete");
  assert_true(path.is_partial(), "Path should be partial");

  std::cout << "  Path string: " << str << std::endl;
}

// ============================================================
// Test 9: Guard Rule Names
// ============================================================

void test_guard_rule_names() {
  std::cout << "\nTest 9: Guard Rule Names\n";

  HierarchicalGuard guard;
  guard.add_rule(std::make_unique<BibliothekWhitelistRule>(std::vector<uint32_t>{1}));
  guard.add_rule(std::make_unique<BudgetLimitRule>(100.0f, 100));
  guard.add_rule(std::make_unique<DepthLimitRule>(6));

  auto names = guard.rule_names();

  assert_true(names.size() == 3, "Should have 3 rule names");
  assert_true(names[0] == "BibliothekWhitelist", "First rule name should match");
  assert_true(names[1] == "BudgetLimit", "Second rule name should match");
  assert_true(names[2] == "DepthLimit", "Third rule name should match");

  std::cout << "  Rule names: ";
  for (size_t i = 0; i < names.size(); ++i) {
    if (i > 0) std::cout << ", ";
    std::cout << names[i];
  }
  std::cout << std::endl;
}

// ============================================================
// Test 10: Complex State Mapping
// ============================================================

void test_complex_state_mapping() {
  std::cout << "\nTest 10: Complex State Mapping\n";

  // Test with boundary values
  State state;
  state.vec = {-32767, 0, 32767, 1000, -1000, 100, -100};

  HierarchicalPath path = StateToHierarchyMapper::map(state);

  assert_true(path.bibliothek_id.has_value(), "All dimensions should map");
  assert_true(path.kategorie_id.has_value(), "");
  assert_true(path.regal_id.has_value(), "");
  assert_true(path.is_complete(), "Path should be complete");

  std::cout << "  Mapped complex state: " << path.to_string() << std::endl;

  // Verify IDs are reasonable
  auto bib_id = path.bibliothek_id.value();
  assert_true(bib_id >= 0 && bib_id <= 65535, "ID should be in valid range");

  std::cout << "  ID mapping working correctly\n";
}

// ============================================================
// Main Test Runner
// ============================================================

int main() {
  std::cout << "============================================================\n";
  std::cout << "Hierarchical Guard Unit Tests\n";
  std::cout << "============================================================\n";

  try {
    test_state_to_path_mapping();
    test_safe_path_mapping();
    test_bibliothek_whitelist_rule();
    test_budget_limit_rule();
    test_depth_limit_rule();
    test_hierarchical_guard();
    test_manifest_serialization();
    test_path_serialization();
    test_guard_rule_names();
    test_complex_state_mapping();

    std::cout << "\n============================================================\n";
    std::cout << "[SUCCESS] All 10 tests passed!\n";
    std::cout << "============================================================\n";

    return 0;

  } catch (const std::exception& e) {
    std::cerr << "[ERROR] Test exception: " << e.what() << std::endl;
    return 1;
  }
}
