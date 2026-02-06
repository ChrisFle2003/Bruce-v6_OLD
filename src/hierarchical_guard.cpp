/*
  Hierarchical Guard Implementation
  ==================================

  Implements validation rules and state-to-path mapping for Bruce knowledge system.
*/

#include "bruce/knowledge/hierarchical_guard.hpp"
#include <sstream>
#include <algorithm>
#include <cmath>

namespace bruce::knowledge {

// ============================================================
// HierarchicalPath
// ============================================================

std::string HierarchicalPath::to_string() const {
  std::ostringstream oss;
  oss << "Path{";

  if (bibliothek_id.has_value()) oss << "bib=" << bibliothek_id.value();
  if (kategorie_id.has_value()) oss << (bibliothek_id.has_value() ? "," : "") << "kat=" << kategorie_id.value();
  if (regal_id.has_value()) oss << (kategorie_id.has_value() ? "," : "") << "reg=" << regal_id.value();
  if (buch_id.has_value()) oss << (regal_id.has_value() ? "," : "") << "buc=" << buch_id.value();
  if (kapitel_id.has_value()) oss << (buch_id.has_value() ? "," : "") << "kap=" << kapitel_id.value();
  if (seite_id.has_value()) oss << (kapitel_id.has_value() ? "," : "") << "sei=" << seite_id.value();
  if (vektoren_id.has_value()) oss << (seite_id.has_value() ? "," : "") << "vec=" << vektoren_id.value();

  oss << "}";
  return oss.str();
}

// ============================================================
// HierarchicalManifest
// ============================================================

std::string HierarchicalManifest::to_json() const {
  std::ostringstream oss;
  oss << "{\n";
  oss << "  \"query_id\": \"" << query_id << "\",\n";
  oss << "  \"query_text\": \"" << query_text << "\",\n";
  oss << "  \"allowed_bibliothek_ids\": [";

  for (size_t i = 0; i < allowed_bibliothek_ids.size(); ++i) {
    if (i > 0) oss << ", ";
    oss << allowed_bibliothek_ids[i];
  }

  oss << "],\n";
  oss << "  \"max_buecher_mb\": " << max_buecher_mb << ",\n";
  oss << "  \"max_seiten\": " << max_seiten << ",\n";
  oss << "  \"max_depth\": " << max_depth << "\n";
  oss << "}\n";

  return oss.str();
}

// ============================================================
// BibliothekWhitelistRule
// ============================================================

bool BibliothekWhitelistRule::allows(const HierarchicalPath& path, const HierarchicalManifest& manifest) const {
  // If no bibliothek_id in path, allow (might be abstract query)
  if (!path.bibliothek_id.has_value()) {
    return true;
  }

  // Check if bibliothek_id is in whitelist
  return is_allowed(path.bibliothek_id.value());
}

bool BibliothekWhitelistRule::is_allowed(uint32_t id) const {
  return std::find(allowed_ids.begin(), allowed_ids.end(), id) != allowed_ids.end();
}

// ============================================================
// BudgetLimitRule
// ============================================================

bool BudgetLimitRule::allows(const HierarchicalPath& path, const HierarchicalManifest& manifest) const {
  // Check if manifest respects our budget limits
  if (manifest.max_buecher_mb > max_buecher_mb) {
    return false;
  }

  if (manifest.max_seiten > max_seiten) {
    return false;
  }

  return true;
}

// ============================================================
// DepthLimitRule
// ============================================================

bool DepthLimitRule::allows(const HierarchicalPath& path, const HierarchicalManifest& manifest) const {
  // Check if manifest respects depth limit
  if (manifest.max_depth > max_depth) {
    return false;
  }

  // Also check how many levels are set in the path
  uint32_t depth = 0;
  if (path.bibliothek_id.has_value()) depth++;
  if (path.kategorie_id.has_value()) depth++;
  if (path.regal_id.has_value()) depth++;
  if (path.buch_id.has_value()) depth++;
  if (path.kapitel_id.has_value()) depth++;
  if (path.seite_id.has_value()) depth++;
  if (path.vektoren_id.has_value()) depth++;

  return depth <= max_depth;
}

// ============================================================
// HierarchicalGuard
// ============================================================

bool HierarchicalGuard::validate_manifest(const HierarchicalManifest& manifest) const {
  // First check if manifest itself is valid
  if (!manifest.is_valid()) {
    return false;
  }

  // Empty path (abstract query) - check rules that apply
  HierarchicalPath empty_path;
  return validate_path(empty_path, manifest);
}

bool HierarchicalGuard::validate_path(const HierarchicalPath& path, const HierarchicalManifest& manifest) const {
  if (rules.empty()) {
    // No rules = allow by default
    return true;
  }

  if (strict_mode) {
    // ALL rules must pass
    for (const auto& rule : rules) {
      if (!rule->allows(path, manifest)) {
        return false;
      }
    }
    return true;
  } else {
    // ANY rule can pass (or-logic)
    for (const auto& rule : rules) {
      if (rule->allows(path, manifest)) {
        return true;
      }
    }
    return false;
  }
}

std::vector<std::string> HierarchicalGuard::rule_names() const {
  std::vector<std::string> names;
  for (const auto& rule : rules) {
    names.push_back(rule->name());
  }
  return names;
}

// ============================================================
// StateToHierarchyMapper
// ============================================================

uint32_t StateToHierarchyMapper::value_to_id(val_t value) {
  // Map int16_t to uint32_t ID
  // int16 range: [-32767, 32767]
  // We add 32768 to shift to [0, 65535] range, then cast to uint32_t

  // Clamp to int16 range
  val_t clamped = value;
  if (clamped < -32767) clamped = -32767;
  if (clamped > 32767) clamped = 32767;

  // Shift to positive range
  // -32767 → 1, 0 → 32768, 32767 → 65535
  uint32_t id = static_cast<uint32_t>(clamped + 32768);

  return id;
}

bool StateToHierarchyMapper::is_valid_id_value(val_t value) {
  // Check if value can be safely converted to ID
  return value >= -32767 && value <= 32767;
}

HierarchicalPath StateToHierarchyMapper::map(const State& state) {
  HierarchicalPath path;

  // Bruce's 7D state should have exactly 7 dimensions
  if (state.vec.size() >= 1 && is_valid_id_value(state.vec[0])) {
    path.bibliothek_id = value_to_id(state.vec[0]);
  }

  if (state.vec.size() >= 2 && is_valid_id_value(state.vec[1])) {
    path.kategorie_id = value_to_id(state.vec[1]);
  }

  if (state.vec.size() >= 3 && is_valid_id_value(state.vec[2])) {
    path.regal_id = value_to_id(state.vec[2]);
  }

  if (state.vec.size() >= 4 && is_valid_id_value(state.vec[3])) {
    path.buch_id = value_to_id(state.vec[3]);
  }

  if (state.vec.size() >= 5 && is_valid_id_value(state.vec[4])) {
    path.kapitel_id = value_to_id(state.vec[4]);
  }

  if (state.vec.size() >= 6 && is_valid_id_value(state.vec[5])) {
    path.seite_id = value_to_id(state.vec[5]);
  }

  if (state.vec.size() >= 7 && is_valid_id_value(state.vec[6])) {
    path.vektoren_id = value_to_id(state.vec[6]);
  }

  return path;
}

std::optional<HierarchicalPath> StateToHierarchyMapper::map_safe(const State& state) {
  // Validate state before mapping
  if (state.vec.size() != 7) {
    return std::nullopt;  // Wrong dimension count
  }

  // Check all values are valid
  for (const auto& val : state.vec) {
    if (!is_valid_id_value(val)) {
      return std::nullopt;  // Invalid value
    }
  }

  return map(state);
}

}  // namespace bruce::knowledge
