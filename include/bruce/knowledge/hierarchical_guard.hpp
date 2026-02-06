/*
  Hierarchical Knowledge Guard for Bruce v6
  ==========================================

  Validates hierarchical knowledge access based on Bruce's 7D state vector.

  Architecture:
  - Maps Bruce's 7D state to hierarchical path (Bibliothek → Kategorie → ... → Seite)
  - Enforces access rules (whitelists, budgets)
  - Guards prevent unauthorized knowledge access
  - Deterministic validation (no randomness)

  Key Insight:
  > Bruce remains the "traffic cop" - validates paths but doesn't perform search
*/

#pragma once

#include "bruce/types.hpp"
#include "bruce/core/state/state.hpp"
#include <vector>
#include <string>
#include <memory>
#include <optional>
#include <cstdint>

namespace bruce::knowledge {

using namespace bruce::core;

/*
  Hierarchical Path Mapping
  =========================

  Bruce's 7D state vector maps directly to knowledge hierarchy:
  - vec[0] → BibliothekID (Library domain)
  - vec[1] → KategorieID  (Category)
  - vec[2] → RegalID      (Shelf)
  - vec[3] → BuchID       (Book)
  - vec[4] → KapitelID    (Chapter)
  - vec[5] → SeiteID      (Page)
  - vec[6] → VektorenID   (64D embedding pointer)

  Each value is int16_t in range [-32767, 32767].
  We map to uint32_t IDs for database lookups.
*/

struct HierarchicalPath {
  std::optional<uint32_t> bibliothek_id;
  std::optional<uint32_t> kategorie_id;
  std::optional<uint32_t> regal_id;
  std::optional<uint32_t> buch_id;
  std::optional<uint32_t> kapitel_id;
  std::optional<uint32_t> seite_id;
  std::optional<uint32_t> vektoren_id;

  // Convert to string for logging
  std::string to_string() const;

  // Check if path is complete (all levels set)
  bool is_complete() const {
    return bibliothek_id.has_value() &&
           kategorie_id.has_value() &&
           regal_id.has_value() &&
           buch_id.has_value() &&
           kapitel_id.has_value() &&
           seite_id.has_value() &&
           vektoren_id.has_value();
  }

  // Check if path is partial (at least one level set)
  bool is_partial() const {
    return bibliothek_id.has_value() ||
           kategorie_id.has_value() ||
           regal_id.has_value() ||
           buch_id.has_value() ||
           kapitel_id.has_value() ||
           seite_id.has_value() ||
           vektoren_id.has_value();
  }
};

/*
  Search Manifest
  ===============

  Describes a knowledge search request with constraints.
  Passed to Guard for validation before execution.
*/

struct HierarchicalManifest {
  // Query metadata
  std::string query_id;
  std::string query_text;

  // Access constraints
  std::vector<uint32_t> allowed_bibliothek_ids;  // Whitelist
  float max_buecher_mb = 100.0f;                  // Max data to fetch
  uint32_t max_seiten = 100;                      // Max results
  uint32_t max_depth = 3;                         // Max levels to traverse

  // Convert to JSON string for logging
  std::string to_json() const;

  // Validate manifest is well-formed
  bool is_valid() const {
    return !query_id.empty() &&
           !allowed_bibliothek_ids.empty() &&
           max_buecher_mb > 0 &&
           max_seiten > 0 &&
           max_depth > 0 &&
           max_depth <= 6;
  }
};

/*
  Guard Rules
  ===========

  Abstract base for validation rules.
  Each rule enforces one constraint category.
*/

class GuardRule {
public:
  virtual ~GuardRule() = default;

  // Check if rule allows the given path and manifest
  virtual bool allows(const HierarchicalPath& path, const HierarchicalManifest& manifest) const = 0;

  // Get rule name for logging
  virtual std::string name() const = 0;
};

// Rule 1: Bibliothek Whitelist
// Only allows searches in whitelisted libraries
class BibliothekWhitelistRule : public GuardRule {
private:
  std::vector<uint32_t> allowed_ids;

public:
  explicit BibliothekWhitelistRule(std::vector<uint32_t> ids)
      : allowed_ids(std::move(ids)) {}

  bool allows(const HierarchicalPath& path, const HierarchicalManifest& manifest) const override;
  std::string name() const override { return "BibliothekWhitelist"; }

  // Check if bibliothek_id is in whitelist
  bool is_allowed(uint32_t id) const;
};

// Rule 2: Budget Limit
// Enforces max data size and result count
class BudgetLimitRule : public GuardRule {
private:
  float max_buecher_mb;
  uint32_t max_seiten;

public:
  BudgetLimitRule(float mb, uint32_t seiten)
      : max_buecher_mb(mb), max_seiten(seiten) {}

  bool allows(const HierarchicalPath& path, const HierarchicalManifest& manifest) const override;
  std::string name() const override { return "BudgetLimit"; }
};

// Rule 3: Depth Limit
// Prevents traversing too deep in hierarchy
class DepthLimitRule : public GuardRule {
private:
  uint32_t max_depth;

public:
  explicit DepthLimitRule(uint32_t depth) : max_depth(depth) {}

  bool allows(const HierarchicalPath& path, const HierarchicalManifest& manifest) const override;
  std::string name() const override { return "DepthLimit"; }
};

/*
  Hierarchical Guard
  ==================

  Main guard class that validates knowledge access.
  Keeps a collection of rules and validates all of them.
*/

class HierarchicalGuard {
private:
  std::vector<std::unique_ptr<GuardRule>> rules;
  bool strict_mode = false;  // If true, ALL rules must pass; if false, ANY rule can pass

public:
  HierarchicalGuard() = default;

  // Add a validation rule
  void add_rule(std::unique_ptr<GuardRule> rule) {
    rules.push_back(std::move(rule));
  }

  // Set validation mode
  void set_strict_mode(bool strict) { strict_mode = strict; }

  // Validate manifest (check all rules)
  bool validate_manifest(const HierarchicalManifest& manifest) const;

  // Validate path (check all rules)
  bool validate_path(const HierarchicalPath& path, const HierarchicalManifest& manifest) const;

  // Get number of rules
  size_t rule_count() const { return rules.size(); }

  // Get rule names for logging
  std::vector<std::string> rule_names() const;
};

/*
  State-to-Path Mapper
  ====================

  Converts Bruce's State vector to HierarchicalPath.
  Handles mapping from int16_t values to uint32_t IDs.
*/

class StateToHierarchyMapper {
public:
  // Map a Bruce State to HierarchicalPath
  static HierarchicalPath map(const State& state);

  // Map with validation (ensures state is valid 7D vector)
  static std::optional<HierarchicalPath> map_safe(const State& state);

private:
  // Convert int16_t value to uint32_t ID (with range checking)
  static uint32_t value_to_id(val_t value);

  // Check if value is in valid range for ID mapping
  static bool is_valid_id_value(val_t value);
};

}  // namespace bruce::knowledge
