#!/usr/bin/env python3
"""Daily self-improvement analysis for OpenClaw.

Analyzes .learnings/ entries and skill health, generates reports,
and optionally applies safe auto-fixes.

Usage:
    python3 scripts/daily_analysis.py [--workspace DIR] [--skills-dir DIR] [--dry-run] [--auto-fix]
"""

import argparse
import json
import os
import re
import stat
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
DEFAULT_SKILLS_DIR = "/projects/.openclaw/skills"
REPORT_SUBDIR = ".learnings/reports"
MAX_SKILL_TOKENS_ESTIMATE = 6000  # rough char/4 heuristic

# Gene-related defaults
GENES_SUBDIR = ".genes"
DEFAULT_GENE_DECAY_WINDOW = 90
GENE_FRESHNESS_ACTIVE = 0.5
GENE_FRESHNESS_STALE = 0.2

# Ecosystem tracking defaults
DEFAULT_OPENCLAW_CONFIG = "/projects/.openclaw/openclaw.json"
DEFAULT_MCP_CONFIG = os.path.expanduser("~/.openclaw/workspace/config/mcporter.json")
ECOSYSTEM_SNAPSHOT_FILE = ".learnings/ecosystem-snapshot.json"
SKILL_STALE_DAYS = 30  # days without usage before flagging


# ===================================================================
# Learnings parser
# ===================================================================

ENTRY_RE = re.compile(
    r"^##\s+\[(?P<id>(?:LRN|ERR|FEAT)-\d{8}-\w{3,})\]\s*(?P<category>\S.*)?$"
)
FIELD_RE = re.compile(
    r"^\*\*(?P<key>[A-Za-z][A-Za-z \-]+)\*\*:\s*(?P<value>.+)$"
)
METADATA_KV_RE = re.compile(
    r"^-\s+(?P<key>[A-Za-z][A-Za-z \-]+):\s*(?P<value>.+)$"
)


def parse_entries(filepath: Path) -> list[dict]:
    """Parse a .learnings markdown file into a list of entry dicts."""
    if not filepath.is_file():
        return []
    text = filepath.read_text(encoding="utf-8", errors="replace")
    entries: list[dict] = []
    current: dict | None = None

    for line in text.splitlines():
        m = ENTRY_RE.match(line)
        if m:
            if current is not None:
                entries.append(current)
            current = {
                "id": m.group("id"),
                "category": (m.group("category") or "").strip(),
                "fields": {},
                "metadata": {},
                "summary": "",
                "file": str(filepath),
            }
            continue

        if current is None:
            continue

        # Top-level bold fields (Priority, Status, Area, Logged)
        fm = FIELD_RE.match(line)
        if fm:
            current["fields"][fm.group("key").strip()] = fm.group("value").strip()
            continue

        # Metadata bullet items
        mm = METADATA_KV_RE.match(line)
        if mm:
            current["metadata"][mm.group("key").strip()] = mm.group("value").strip()
            continue

        # Capture summary (first non-empty line after ### Summary)
        if line.startswith("### Summary"):
            continue
        if not current.get("summary") and line.strip() and not line.startswith("#"):
            # Heuristic: first content line after header that isn't another section
            if "fields" in current and not line.startswith("**"):
                current["summary"] = line.strip()

    if current is not None:
        entries.append(current)

    return entries


# ===================================================================
# Learning analysis
# ===================================================================


def analyze_learnings(workspace: str) -> dict:
    """Analyze all .learnings/ files and return structured results."""
    learnings_dir = Path(workspace) / ".learnings"
    files = {
        "learnings": learnings_dir / "LEARNINGS.md",
        "errors": learnings_dir / "ERRORS.md",
        "features": learnings_dir / "FEATURE_REQUESTS.md",
    }

    all_entries: list[dict] = []
    counts = {}
    for key, path in files.items():
        entries = parse_entries(path)
        counts[key] = len(entries)
        all_entries.extend(entries)

    # Pending entries grouped by priority
    pending = [e for e in all_entries if e["fields"].get("Status", "").lower() == "pending"]
    by_priority: dict[str, list] = defaultdict(list)
    for e in pending:
        pri = e["fields"].get("Priority", "unknown").lower()
        by_priority[pri].append(e)

    # Pending entries grouped by category/area
    by_area: dict[str, list] = defaultdict(list)
    for e in pending:
        area = e["fields"].get("Area", "unknown").lower()
        by_area[area].append(e)

    # Promotion candidates: Pattern-Key with Recurrence >= 3 in 30-day window
    promotion_candidates: list[dict] = []
    for e in all_entries:
        recurrence = e["metadata"].get("Recurrence-Count", "0")
        try:
            recurrence_int = int(recurrence)
        except ValueError:
            recurrence_int = 0
        if recurrence_int < 3:
            continue
        # Check 30-day window
        last_seen = e["metadata"].get("Last-Seen", "")
        if last_seen:
            try:
                ls_date = datetime.strptime(last_seen[:10], "%Y-%m-%d")
                if (datetime.now() - ls_date) > timedelta(days=30):
                    continue
            except ValueError:
                pass
        pattern_key = e["metadata"].get("Pattern-Key", "")
        if pattern_key:
            promotion_candidates.append(e)

    # --- Promotion evaluation: cross-Area detection for promotion candidates ---
    # Group all entries by Pattern-Key to find distinct Areas per pattern
    pattern_key_areas: dict[str, set[str]] = defaultdict(set)
    pattern_key_entries: dict[str, list[dict]] = defaultdict(list)
    for e in all_entries:
        pk = e["metadata"].get("Pattern-Key", "")
        if not pk:
            continue
        area = e["fields"].get("Area", "").strip().lower()
        if area:
            pattern_key_areas[pk].add(area)
        pattern_key_entries[pk].append(e)

    # Build promotion evaluation results with cross-task and time window checks
    promotion_evaluation: list[dict] = []
    for candidate in promotion_candidates:
        pk = candidate["metadata"].get("Pattern-Key", "")
        if not pk:
            continue

        areas = pattern_key_areas.get(pk, set())
        cross_task = len(areas) >= 2

        # Time window: check First-Seen and Last-Seen are within 30 days
        first_seen = candidate["metadata"].get("First-Seen", "")
        last_seen = candidate["metadata"].get("Last-Seen", "")
        in_window = True
        if first_seen and last_seen:
            try:
                fs_date = datetime.strptime(first_seen[:10], "%Y-%m-%d")
                ls_date = datetime.strptime(last_seen[:10], "%Y-%m-%d")
                in_window = (ls_date - fs_date) <= timedelta(days=30)
            except ValueError:
                pass

        recurrence = candidate["metadata"].get("Recurrence-Count", "0")
        try:
            recurrence_int = int(recurrence)
        except ValueError:
            recurrence_int = 0

        # Determine promotion target based on pattern key prefix and area
        target = _suggest_promotion_target(pk, areas)

        # Generate a concise rule suggestion from the candidate summary
        summary = candidate.get("summary", candidate.get("category", ""))
        rule_suggestion = _suggest_promotion_rule(pk, summary)

        promotion_evaluation.append({
            "entry": candidate,
            "pattern_key": pk,
            "recurrence": recurrence_int,
            "areas": sorted(areas),
            "cross_task": cross_task,
            "in_window": in_window,
            "meets_all_criteria": recurrence_int >= 3 and cross_task and in_window,
            "target": target,
            "rule_suggestion": rule_suggestion,
        })

    # Promotable: resolved + high/critical, or See Also >= 2
    promotable: list[dict] = []
    for e in all_entries:
        status = e["fields"].get("Status", "").lower()
        pri = e["fields"].get("Priority", "").lower()
        see_also = e["metadata"].get("See Also", "")
        see_also_count = len([s.strip() for s in see_also.split(",") if s.strip()]) if see_also else 0

        if status == "resolved" and pri in ("high", "critical"):
            promotable.append(e)
        elif see_also_count >= 2:
            promotable.append(e)

    # Duplicate detection: keyword overlap in summaries
    potential_duplicates: list[tuple[dict, dict, float]] = []
    for i, a in enumerate(all_entries):
        for b in all_entries[i + 1:]:
            score = _summary_overlap(a.get("summary", ""), b.get("summary", ""))
            if score >= 0.5:
                potential_duplicates.append((a, b, score))

    # Error-to-skill pipeline: tags with >= 3 occurrences
    tag_counts: dict[str, list] = defaultdict(list)
    for e in all_entries:
        if not e["id"].startswith("ERR"):
            continue
        tags_str = e["metadata"].get("Tags", "")
        for tag in tags_str.split(","):
            tag = tag.strip().lower()
            if tag:
                tag_counts[tag].append(e)
    skill_suggestions: dict[str, int] = {}
    for tag, entries in tag_counts.items():
        if len(entries) >= 3:
            skill_suggestions[tag] = len(entries)

    return {
        "counts": counts,
        "total": len(all_entries),
        "pending": pending,
        "by_priority": dict(by_priority),
        "by_area": dict(by_area),
        "promotion_candidates": promotion_candidates,
        "promotion_evaluation": promotion_evaluation,
        "promotable": promotable,
        "potential_duplicates": potential_duplicates,
        "skill_suggestions": skill_suggestions,
    }


def _suggest_promotion_target(pattern_key: str, areas: set[str]) -> str:
    """Suggest the best promotion target file based on pattern key and areas."""
    pk_lower = pattern_key.lower()

    # Workflow/agent patterns → AGENTS.md
    if any(kw in pk_lower for kw in ("workflow", "agent", "delegate", "automat")):
        return "AGENTS.md"

    # Tool/integration patterns → TOOLS.md
    if any(kw in pk_lower for kw in ("tool", "git", "npm", "docker", "cli", "command")):
        return "TOOLS.md"

    # Behavioral patterns → SOUL.md
    if any(kw in pk_lower for kw in ("style", "tone", "communicat", "behav")):
        return "SOUL.md"

    # If areas include infra/config → TOOLS.md; tests → AGENTS.md
    if areas & {"infra", "config"}:
        return "TOOLS.md"
    if "tests" in areas:
        return "AGENTS.md"

    # Default to AGENTS.md for cross-area patterns (likely workflow improvements)
    if len(areas) >= 2:
        return "AGENTS.md"

    return "MEMORY.md"


def _suggest_promotion_rule(pattern_key: str, summary: str) -> str:
    """Generate a concise promotion rule suggestion from pattern key and summary."""
    if not summary:
        return f"Apply `{pattern_key}` pattern consistently"

    # Trim to first sentence and make it actionable
    first_sentence = summary.split("。")[0].split(". ")[0].strip()
    if len(first_sentence) > 80:
        first_sentence = first_sentence[:77] + "..."

    return first_sentence


def _summary_overlap(a: str, b: str) -> float:
    """Jaccard similarity of keyword sets from two summaries."""
    if not a or not b:
        return 0.0
    # Simple CJK-aware word splitting
    words_a = set(_tokenize(a))
    words_b = set(_tokenize(b))
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _tokenize(text: str) -> list[str]:
    """Split text into tokens, handling both CJK and Latin."""
    # Split on whitespace and punctuation, keep CJK chars as individual tokens
    tokens = re.findall(r"[\u4e00-\u9fff]|[a-zA-Z0-9_]+", text.lower())
    # Filter out very short tokens
    return [t for t in tokens if len(t) > 1 or "\u4e00" <= t <= "\u9fff"]


# ===================================================================
# Skill health check
# ===================================================================


def check_skill_health(skills_dir: str) -> list[dict]:
    """Scan skills directory and report health issues."""
    skills_path = Path(skills_dir)
    if not skills_path.is_dir():
        return [{"skill": "(root)", "issue": f"Skills directory not found: {skills_dir}"}]

    issues: list[dict] = []

    for entry in sorted(skills_path.iterdir()):
        # Skip non-directories and special files
        if not entry.is_dir() and not entry.is_symlink():
            continue
        skill_name = entry.name

        # Skip hidden dirs, zip files, etc.
        if skill_name.startswith(".") or skill_name.endswith(".zip"):
            continue

        # Handle symlinks
        if entry.is_symlink():
            target = os.readlink(entry)
            real = entry.resolve()
            if not real.is_dir():
                issues.append({"skill": skill_name, "issue": f"Symlink target missing: {target}"})
                continue
            # Symlinks are aliases, skip detailed checks (target will be checked)
            continue

        # Check .disabled
        if skill_name.endswith(".disabled"):
            issues.append({"skill": skill_name, "issue": "Skill is disabled"})
            continue

        skill_md = entry / "SKILL.md"

        # Check SKILL.md exists
        if not skill_md.is_file():
            issues.append({"skill": skill_name, "issue": "Missing SKILL.md"})
            continue

        # Check for README.md (violates Agent Skills spec)
        readme = entry / "README.md"
        if readme.is_file():
            issues.append({"skill": skill_name, "issue": "Contains README.md (violates Agent Skills spec)"})

        # Parse frontmatter
        content = skill_md.read_text(encoding="utf-8", errors="replace")
        fm = _parse_frontmatter(content)

        if fm is None:
            issues.append({"skill": skill_name, "issue": "Missing or malformed YAML frontmatter"})
            continue

        # Check name field
        fm_name = fm.get("name", "")
        if not fm_name:
            issues.append({
                "skill": skill_name,
                "issue": "Missing 'name' field in frontmatter",
                "auto_fix": "add_name",
            })
        elif fm_name != skill_name:
            # Allow name mismatches for now, just warn
            issues.append({"skill": skill_name, "issue": f"Name mismatch: frontmatter '{fm_name}' != dir '{skill_name}'"})

        # Check description
        desc = fm.get("description", "")
        if not desc:
            issues.append({"skill": skill_name, "issue": "Missing 'description' in frontmatter"})
        elif len(desc) < 20:
            issues.append({"skill": skill_name, "issue": f"Description too short ({len(desc)} chars)"})
        elif "TODO" in desc:
            issues.append({"skill": skill_name, "issue": "Description contains TODO placeholder"})

        # Check body content
        body = _strip_frontmatter(content)
        if len(body.strip()) < 50:
            issues.append({"skill": skill_name, "issue": "Body content too sparse (< 50 chars)"})

        # Token estimate (rough: chars / 4)
        token_est = len(content) // 4
        if token_est > MAX_SKILL_TOKENS_ESTIMATE:
            issues.append({"skill": skill_name, "issue": f"Large skill (~{token_est} tokens estimated)"})

        # Check script permissions
        scripts_dir = entry / "scripts"
        if scripts_dir.is_dir():
            for script in scripts_dir.iterdir():
                if script.suffix in (".sh", ".py") and script.is_file():
                    if not os.access(script, os.X_OK):
                        issues.append({
                            "skill": skill_name,
                            "issue": f"Script not executable: {script.name}",
                            "auto_fix": "chmod_x",
                            "fix_path": str(script),
                        })

    return issues


def _parse_frontmatter(content: str) -> dict | None:
    """Extract YAML frontmatter from SKILL.md content."""
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    fm_text = parts[1].strip()
    if not fm_text:
        return {}
    # Simple key-value parser (no pyyaml dependency)
    result = {}
    for line in fm_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            result[key] = value
    return result


def _strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter from content."""
    if not content.startswith("---"):
        return content
    parts = content.split("---", 2)
    return parts[2] if len(parts) >= 3 else content


# ===================================================================
# Gene analysis
# ===================================================================


def _parse_gene_yaml(filepath: Path) -> dict | None:
    """Parse a gene.yaml or variant YAML file into a dict.

    Extends the approach of _parse_frontmatter with support for:
    - Comment lines (# prefix)
    - Multi-line | block values (accumulated indented lines)
    - Comma-separated list fields
    """
    if not filepath.is_file():
        return None
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    result: dict = {}
    current_key: str | None = None
    multiline_buf: list[str] = []

    def _flush_multiline():
        if current_key and multiline_buf:
            result[current_key] = "\n".join(multiline_buf).rstrip()

    for raw_line in text.splitlines():
        stripped = raw_line.strip()

        # Skip empty lines and comments at top level
        if not stripped or stripped.startswith("#"):
            # Inside a multiline block, preserve empty lines
            if current_key and multiline_buf:
                multiline_buf.append("")
            continue

        # Check if this is a key: value line
        if ":" in stripped and not stripped.startswith("-"):
            # Could be a new key — check if current line starts at column 0
            # (not indented, meaning not part of a multiline block)
            if raw_line and not raw_line[0].isspace():
                _flush_multiline()
                current_key = None
                multiline_buf = []

                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip().strip('"').strip("'")

                if value == "|":
                    # Start multiline block
                    current_key = key
                    multiline_buf = []
                else:
                    result[key] = value
                continue

        # If we're in a multiline block, accumulate indented lines
        if current_key:
            multiline_buf.append(raw_line.rstrip())
            continue

    _flush_multiline()
    return result if result else None


def _load_gene_registry(workspace: str) -> dict:
    """Load .genes/registry.json, returning empty structure on missing/corrupt file."""
    registry_path = Path(workspace) / GENES_SUBDIR / "registry.json"
    if not registry_path.is_file():
        return {"genes": []}
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(data, dict):
            return {"genes": []}
        if "genes" not in data:
            data["genes"] = []
        return data
    except (json.JSONDecodeError, OSError):
        return {"genes": []}


def scan_genes(workspace: str) -> list[dict]:
    """Scan .genes/ directory and return list of parsed gene dicts."""
    genes_dir = Path(workspace) / GENES_SUBDIR
    if not genes_dir.is_dir():
        return []

    genes: list[dict] = []
    for entry in sorted(genes_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith(".") or entry.name == "registry.json":
            continue
        gene_yaml = entry / "gene.yaml"
        parsed = _parse_gene_yaml(gene_yaml)
        if parsed:
            parsed["_dir_name"] = entry.name
            parsed["_path"] = str(gene_yaml)
            genes.append(parsed)

    return genes


def calculate_freshness(
    last_used_str: str,
    decay_window_days: int = DEFAULT_GENE_DECAY_WINDOW,
) -> tuple[float, str]:
    """Calculate freshness score and decay status from last_used date.

    Returns:
        (freshness_score, decay_status) where status is active/stale/degraded.
    """
    if not last_used_str:
        # Never used — treat as moderately stale based on creation context
        return (0.5, "active")

    try:
        last_used = datetime.strptime(last_used_str[:10], "%Y-%m-%d")
    except ValueError:
        return (0.5, "active")

    days_since = (datetime.now() - last_used).days
    if days_since < 0:
        days_since = 0

    freshness = max(0.0, 1.0 - (days_since / decay_window_days))
    freshness = round(freshness, 3)

    if freshness > GENE_FRESHNESS_ACTIVE:
        status = "active"
    elif freshness > GENE_FRESHNESS_STALE:
        status = "stale"
    else:
        status = "degraded"

    return (freshness, status)


def analyze_genes(workspace: str) -> dict:
    """Analyze all genes and return structured results."""
    genes = scan_genes(workspace)
    registry = _load_gene_registry(workspace)

    # Group by decay status
    by_status: dict[str, list] = defaultdict(list)
    for g in genes:
        decay_window = int(g.get("decay_window_days", DEFAULT_GENE_DECAY_WINDOW) or DEFAULT_GENE_DECAY_WINDOW)
        freshness, status = calculate_freshness(g.get("last_used", ""), decay_window)
        g["_calc_freshness"] = freshness
        g["_calc_status"] = status
        by_status[status].append(g)

    # Registry consistency: genes on disk vs registry entries
    disk_names = {g["_dir_name"] for g in genes}
    registry_names = {e.get("name", "") for e in registry.get("genes", [])}

    missing_from_registry = disk_names - registry_names
    missing_from_disk = registry_names - disk_names

    # Quality issues
    missing_description = [
        g for g in genes
        if not g.get("description") or "TODO" in g.get("description", "")
    ]
    zero_usage = [g for g in genes if str(g.get("usage_count", "0")) == "0"]

    # Top genes by effectiveness
    scored = []
    for g in genes:
        try:
            score = float(g.get("effectiveness_score", 0.5))
        except (ValueError, TypeError):
            score = 0.5
        scored.append((score, g))
    scored.sort(key=lambda x: -x[0])
    top_genes = scored[:5]

    return {
        "total": len(genes),
        "genes": genes,
        "by_status": dict(by_status),
        "missing_from_registry": missing_from_registry,
        "missing_from_disk": missing_from_disk,
        "missing_description": missing_description,
        "zero_usage": zero_usage,
        "top_genes": top_genes,
    }


def update_gene_decay(workspace: str, dry_run: bool) -> list[str]:
    """Recalculate freshness for all genes and update gene.yaml + registry.json.

    Only runs when --auto-fix is active.
    Returns list of actions taken.
    """
    genes = scan_genes(workspace)
    if not genes:
        return []

    actions: list[str] = []
    registry_path = Path(workspace) / GENES_SUBDIR / "registry.json"
    registry = _load_gene_registry(workspace)
    registry_by_name = {e.get("name", ""): e for e in registry.get("genes", [])}

    for g in genes:
        decay_window = int(g.get("decay_window_days", DEFAULT_GENE_DECAY_WINDOW) or DEFAULT_GENE_DECAY_WINDOW)
        new_freshness, new_status = calculate_freshness(g.get("last_used", ""), decay_window)

        old_freshness = g.get("freshness_score", "")
        old_status = g.get("decay_status", "")

        # Check if update is needed
        try:
            old_f = float(old_freshness)
        except (ValueError, TypeError):
            old_f = -1.0

        if abs(old_f - new_freshness) < 0.001 and old_status == new_status:
            continue

        gene_name = g.get("_dir_name", g.get("name", "?"))
        gene_path = Path(g["_path"])

        if dry_run:
            actions.append(
                f"[DRY-RUN] Would update {gene_name}: "
                f"freshness {old_freshness} -> {new_freshness}, "
                f"status {old_status} -> {new_status}"
            )
        else:
            # Update gene.yaml in place
            try:
                content = gene_path.read_text(encoding="utf-8", errors="replace")
                # Replace freshness_score line
                content = re.sub(
                    r"^freshness_score:.*$",
                    f"freshness_score: {new_freshness}",
                    content,
                    flags=re.MULTILINE,
                )
                # Replace decay_status line
                content = re.sub(
                    r"^decay_status:.*$",
                    f"decay_status: {new_status}",
                    content,
                    flags=re.MULTILINE,
                )
                gene_path.write_text(content, encoding="utf-8")
                actions.append(
                    f"Updated {gene_name}: "
                    f"freshness {old_freshness} -> {new_freshness}, "
                    f"status {old_status} -> {new_status}"
                )
            except OSError as e:
                actions.append(f"Error updating {gene_name}: {e}")

            # Sync registry entry
            if gene_name in registry_by_name:
                registry_by_name[gene_name]["freshness_score"] = new_freshness
                registry_by_name[gene_name]["decay_status"] = new_status

    # Write updated registry if not dry-run and we made changes
    if not dry_run and actions:
        try:
            registry["genes"] = list(registry_by_name.values())
            registry_path.write_text(
                json.dumps(registry, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass

    return actions


# ===================================================================
# Ecosystem evolution tracking (skills + MCP)
# ===================================================================


def _load_ecosystem_snapshot(workspace: str) -> dict:
    """Load previous ecosystem snapshot for diff detection."""
    snap_path = Path(workspace) / ECOSYSTEM_SNAPSHOT_FILE
    if not snap_path.is_file():
        return {}
    try:
        return json.loads(snap_path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_ecosystem_snapshot(workspace: str, snapshot: dict, dry_run: bool) -> None:
    """Persist current ecosystem state for next run's diff."""
    if dry_run:
        return
    snap_path = Path(workspace) / ECOSYSTEM_SNAPSHOT_FILE
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        snap_path.write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def _get_dir_mtime(path: Path) -> str:
    """Get modification time of a directory as YYYY-MM-DD string."""
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except OSError:
        return ""


def scan_ecosystem(
    skills_dir: str,
    openclaw_config: str = DEFAULT_OPENCLAW_CONFIG,
    mcp_config: str = DEFAULT_MCP_CONFIG,
) -> dict:
    """Scan installed skills and MCP servers, return ecosystem inventory.

    Returns dict with:
      - skills: list of {name, install_date, has_skill_md, disabled, is_symlink}
      - mcp_servers: list of {name, type}  (type: local|remote)
      - mcp_skills: list of {name, enabled}  (from openclaw.json skills.entries)
      - knot_installed: list of names from knotInstalled
    """
    # --- Scan skills directory ---
    skills: list[dict] = []
    skills_path = Path(skills_dir)
    if skills_path.is_dir():
        for entry in sorted(skills_path.iterdir()):
            name = entry.name
            if name.startswith(".") or name.endswith(".zip"):
                continue
            # Skip non-directories (except symlinks to dirs)
            if not entry.is_dir() and not entry.is_symlink():
                continue
            if entry.is_symlink():
                target = entry.resolve()
                skills.append({
                    "name": name,
                    "install_date": _get_dir_mtime(entry),
                    "has_skill_md": False,
                    "disabled": False,
                    "is_symlink": True,
                    "symlink_target": str(os.readlink(entry)),
                })
                continue

            disabled = name.endswith(".disabled")
            skill_md = entry / "SKILL.md"
            skills.append({
                "name": name,
                "install_date": _get_dir_mtime(entry),
                "has_skill_md": skill_md.is_file(),
                "disabled": disabled,
                "is_symlink": False,
            })

    # --- Read openclaw.json for MCP-type skills ---
    mcp_skills: list[dict] = []
    knot_installed: list[str] = []
    oc_path = Path(openclaw_config)
    if oc_path.is_file():
        try:
            oc = json.loads(oc_path.read_text(encoding="utf-8", errors="replace"))
            entries = oc.get("skills", {}).get("entries", {})
            for sname, sconf in entries.items():
                mcp_skills.append({
                    "name": sname,
                    "enabled": sconf.get("enabled", False),
                })
            knot_installed = oc.get("skills", {}).get("knotInstalled", [])
        except (json.JSONDecodeError, OSError):
            pass

    # --- Read mcporter.json for MCP servers ---
    mcp_servers: list[dict] = []
    mcp_path = Path(mcp_config)
    if mcp_path.is_file():
        try:
            mc = json.loads(mcp_path.read_text(encoding="utf-8", errors="replace"))
            for srv_name, srv_conf in mc.get("mcpServers", {}).items():
                # Determine type: local (command-based) or remote (url/baseUrl)
                if srv_conf.get("command"):
                    srv_type = "local"
                elif srv_conf.get("url") or srv_conf.get("baseUrl"):
                    srv_type = "remote"
                else:
                    srv_type = "unknown"
                mcp_servers.append({"name": srv_name, "type": srv_type})
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "skills": skills,
        "mcp_servers": mcp_servers,
        "mcp_skills": mcp_skills,
        "knot_installed": knot_installed,
    }


def analyze_ecosystem(
    ecosystem: dict,
    workspace: str,
    dry_run: bool,
) -> dict:
    """Compare current ecosystem to previous snapshot, detect changes.

    Returns dict with:
      - skill_count, mcp_server_count, mcp_skill_count
      - new_skills, removed_skills (since last snapshot)
      - new_mcp_servers, removed_mcp_servers
      - new_mcp_skills, removed_mcp_skills
      - stale_skills (installed > SKILL_STALE_DAYS ago with no recent indicators)
      - disabled_skills
      - snapshot_date (previous)
    """
    prev = _load_ecosystem_snapshot(workspace)
    now_str = datetime.now().strftime("%Y-%m-%d")

    # Current sets
    cur_skill_names = {s["name"] for s in ecosystem["skills"] if not s.get("is_symlink")}
    cur_mcp_srv_names = {s["name"] for s in ecosystem["mcp_servers"]}
    cur_mcp_skill_names = {s["name"] for s in ecosystem["mcp_skills"]}

    # Previous sets
    prev_skills = set(prev.get("skill_names", []))
    prev_mcp_srvs = set(prev.get("mcp_server_names", []))
    prev_mcp_skills = set(prev.get("mcp_skill_names", []))
    prev_date = prev.get("date", "")

    # Diffs
    new_skills = sorted(cur_skill_names - prev_skills) if prev_skills else []
    removed_skills = sorted(prev_skills - cur_skill_names) if prev_skills else []
    new_mcp_servers = sorted(cur_mcp_srv_names - prev_mcp_srvs) if prev_mcp_srvs else []
    removed_mcp_servers = sorted(prev_mcp_srvs - cur_mcp_srv_names) if prev_mcp_srvs else []
    new_mcp_skills = sorted(cur_mcp_skill_names - prev_mcp_skills) if prev_mcp_skills else []
    removed_mcp_skills = sorted(prev_mcp_skills - cur_mcp_skill_names) if prev_mcp_skills else []

    # Stale skills: installed > N days ago, not a symlink
    stale_skills: list[dict] = []
    for s in ecosystem["skills"]:
        if s.get("is_symlink") or s.get("disabled"):
            continue
        install_date = s.get("install_date", "")
        if not install_date:
            continue
        try:
            idate = datetime.strptime(install_date, "%Y-%m-%d")
            days_old = (datetime.now() - idate).days
            if days_old > SKILL_STALE_DAYS:
                stale_skills.append({
                    "name": s["name"],
                    "install_date": install_date,
                    "days_old": days_old,
                })
        except ValueError:
            pass

    # Disabled skills
    disabled_skills = [s["name"] for s in ecosystem["skills"] if s.get("disabled")]

    # Save new snapshot
    new_snapshot = {
        "date": now_str,
        "skill_names": sorted(cur_skill_names),
        "mcp_server_names": sorted(cur_mcp_srv_names),
        "mcp_skill_names": sorted(cur_mcp_skill_names),
    }
    _save_ecosystem_snapshot(workspace, new_snapshot, dry_run)

    return {
        "skill_count": len([s for s in ecosystem["skills"] if not s.get("is_symlink")]),
        "mcp_server_count": len(ecosystem["mcp_servers"]),
        "mcp_skill_count": len(ecosystem["mcp_skills"]),
        "mcp_skill_enabled_count": len([s for s in ecosystem["mcp_skills"] if s.get("enabled")]),
        "knot_count": len(ecosystem["knot_installed"]),
        "new_skills": new_skills,
        "removed_skills": removed_skills,
        "new_mcp_servers": new_mcp_servers,
        "removed_mcp_servers": removed_mcp_servers,
        "new_mcp_skills": new_mcp_skills,
        "removed_mcp_skills": removed_mcp_skills,
        "stale_skills": stale_skills,
        "disabled_skills": disabled_skills,
        "snapshot_date": prev_date,
        "is_first_run": not prev_skills and not prev_mcp_srvs,
    }


# ===================================================================
# Auto-fix
# ===================================================================


def apply_fixes(skill_issues: list[dict], skills_dir: str, dry_run: bool) -> list[str]:
    """Apply safe auto-fixes and return list of actions taken."""
    actions: list[str] = []

    for issue in skill_issues:
        fix_type = issue.get("auto_fix")
        if not fix_type:
            continue

        if fix_type == "chmod_x":
            fix_path = issue.get("fix_path", "")
            if fix_path and os.path.isfile(fix_path):
                if dry_run:
                    actions.append(f"[DRY-RUN] Would chmod +x: {fix_path}")
                else:
                    st = os.stat(fix_path)
                    os.chmod(fix_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                    actions.append(f"Fixed: chmod +x {fix_path}")

        elif fix_type == "add_name":
            skill_name = issue["skill"]
            skill_md = Path(skills_dir) / skill_name / "SKILL.md"
            if skill_md.is_file():
                content = skill_md.read_text(encoding="utf-8", errors="replace")
                if dry_run:
                    actions.append(f"[DRY-RUN] Would add name: '{skill_name}' to {skill_md}")
                else:
                    # Insert name field after first ---
                    new_content = content.replace("---\n", f"---\nname: {skill_name}\n", 1)
                    if new_content != content:
                        skill_md.write_text(new_content, encoding="utf-8")
                        actions.append(f"Fixed: added name '{skill_name}' to {skill_md}")

    return actions


# ===================================================================
# Report generation
# ===================================================================


def generate_report(
    analysis: dict,
    skill_issues: list[dict],
    fix_actions: list[str],
    workspace: str,
    dry_run: bool,
    gene_analysis: dict | None = None,
    gene_decay_actions: list[str] | None = None,
    ecosystem_analysis: dict | None = None,
) -> str:
    """Generate markdown report and return it as a string."""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    lines: list[str] = []

    lines.append(f"# Self-Improvement Daily Report - {date_str}")
    lines.append(f"\nGenerated: {now.isoformat()}")
    lines.append("")

    # --- Learning summary ---
    lines.append("## Learning Summary")
    lines.append("")
    c = analysis["counts"]
    lines.append(f"| File | Entries |")
    lines.append(f"|------|--------|")
    lines.append(f"| LEARNINGS.md | {c.get('learnings', 0)} |")
    lines.append(f"| ERRORS.md | {c.get('errors', 0)} |")
    lines.append(f"| FEATURE_REQUESTS.md | {c.get('features', 0)} |")
    lines.append(f"| **Total** | **{analysis['total']}** |")
    lines.append("")

    # --- Ecosystem evolution ---
    if ecosystem_analysis is not None:
        ea = ecosystem_analysis
        lines.append("## Ecosystem Evolution Report")
        lines.append("")

        # Overview table
        lines.append("### Current Inventory")
        lines.append("")
        lines.append("| Component | Count |")
        lines.append("|-----------|-------|")
        lines.append(f"| Skills (installed) | {ea.get('skill_count', 0)} |")
        lines.append(f"| Skills (from ClawdHub) | {ea.get('knot_count', 0)} |")
        lines.append(f"| MCP Servers | {ea.get('mcp_server_count', 0)} |")
        lines.append(f"| MCP Skills (enabled/total) | {ea.get('mcp_skill_enabled_count', 0)}/{ea.get('mcp_skill_count', 0)} |")
        lines.append("")

        # Today's changes
        has_changes = (
            ea.get("new_skills") or ea.get("removed_skills")
            or ea.get("new_mcp_servers") or ea.get("removed_mcp_servers")
            or ea.get("new_mcp_skills") or ea.get("removed_mcp_skills")
        )

        if ea.get("is_first_run"):
            lines.append("*First run — baseline snapshot saved. Changes will appear from next run.*")
            lines.append("")
        elif has_changes:
            snap_date = ea.get("snapshot_date", "?")
            lines.append(f"### Changes Since {snap_date}")
            lines.append("")
            if ea["new_skills"]:
                lines.append(f"**New Skills** (+{len(ea['new_skills'])}):")
                for name in ea["new_skills"]:
                    lines.append(f"- `{name}`")
                lines.append("")
            if ea["removed_skills"]:
                lines.append(f"**Removed Skills** (-{len(ea['removed_skills'])}):")
                for name in ea["removed_skills"]:
                    lines.append(f"- `{name}`")
                lines.append("")
            if ea["new_mcp_servers"]:
                lines.append(f"**New MCP Servers** (+{len(ea['new_mcp_servers'])}):")
                for name in ea["new_mcp_servers"]:
                    lines.append(f"- `{name}`")
                lines.append("")
            if ea["removed_mcp_servers"]:
                lines.append(f"**Removed MCP Servers** (-{len(ea['removed_mcp_servers'])}):")
                for name in ea["removed_mcp_servers"]:
                    lines.append(f"- `{name}`")
                lines.append("")
            if ea["new_mcp_skills"]:
                lines.append(f"**New MCP Skills** (+{len(ea['new_mcp_skills'])}):")
                for name in ea["new_mcp_skills"]:
                    lines.append(f"- `{name}`")
                lines.append("")
            if ea["removed_mcp_skills"]:
                lines.append(f"**Removed MCP Skills** (-{len(ea['removed_mcp_skills'])}):")
                for name in ea["removed_mcp_skills"]:
                    lines.append(f"- `{name}`")
                lines.append("")
        else:
            lines.append("*No changes since last run.*")
            lines.append("")

        # Stale skills
        stale = ea.get("stale_skills", [])
        if stale:
            lines.append("### Stale Skills (长期未更新，考虑是否淘汰)")
            lines.append("")
            lines.append("| Skill | Installed | Days Ago |")
            lines.append("|-------|-----------|----------|")
            for s in sorted(stale, key=lambda x: -x["days_old"]):
                lines.append(f"| `{s['name']}` | {s['install_date']} | {s['days_old']} |")
            lines.append("")

        # Disabled skills
        disabled = ea.get("disabled_skills", [])
        if disabled:
            lines.append("### Disabled Skills (考虑是否彻底移除)")
            lines.append("")
            for name in disabled:
                lines.append(f"- `{name}`")
            lines.append("")

    # Pending by priority
    if analysis["pending"]:
        lines.append(f"### Pending Items ({len(analysis['pending'])})")
        lines.append("")
        for pri in ("critical", "high", "medium", "low", "unknown"):
            items = analysis["by_priority"].get(pri, [])
            if items:
                lines.append(f"**{pri.capitalize()}** ({len(items)}):")
                for e in items:
                    lines.append(f"- `{e['id']}` - {e.get('summary', e.get('category', '?'))}")
                lines.append("")

    # Promotion candidates
    if analysis["promotion_candidates"]:
        lines.append("### Promotion Candidates (Pattern-Key)")
        lines.append("")
        lines.append("These entries meet promotion criteria (Recurrence >= 3, within 30-day window):")
        lines.append("")
        for e in analysis["promotion_candidates"]:
            pk = e["metadata"].get("Pattern-Key", "?")
            rc = e["metadata"].get("Recurrence-Count", "?")
            lines.append(f"- `{e['id']}` Pattern-Key: `{pk}` (Recurrence: {rc})")
        lines.append("")

    # Promotion evaluation (detailed cross-task analysis)
    promo_eval = analysis.get("promotion_evaluation", [])
    qualified = [pe for pe in promo_eval if pe["meets_all_criteria"]]
    if qualified:
        lines.append("### Promotion Evaluation")
        lines.append("")
        lines.append("以下条目满足晋升标准（Recurrence >= 3, 30天窗口内, 2+ Area）：")
        lines.append("")
        for idx, pe in enumerate(qualified, 1):
            entry = pe["entry"]
            lines.append(f"{idx}. `{entry['id']}` Pattern-Key: `{pe['pattern_key']}`")
            lines.append(f"   - Recurrence: {pe['recurrence']}, Areas: {', '.join(pe['areas'])}")
            lines.append(f"   - 建议晋升到: {pe['target']}")
            lines.append(f"   - 建议规则: \"{pe['rule_suggestion']}\"")
        lines.append("")
    elif promo_eval:
        # Show near-misses (have promotion candidates but none meet all 3 criteria)
        lines.append("### Promotion Evaluation")
        lines.append("")
        lines.append("当前无条目满足全部晋升标准（Recurrence >= 3 + 30天窗口 + 2+ Area）。")
        lines.append("")
        lines.append("近似候选：")
        lines.append("")
        for idx, pe in enumerate(promo_eval, 1):
            entry = pe["entry"]
            missing = []
            if not pe["cross_task"]:
                missing.append("仅出现在 1 个 Area")
            if not pe["in_window"]:
                missing.append("超出 30 天窗口")
            lines.append(
                f"{idx}. `{entry['id']}` Pattern-Key: `{pe['pattern_key']}` "
                f"— 缺少: {', '.join(missing) if missing else '无'}"
            )
        lines.append("")

    # Promotable entries
    if analysis["promotable"]:
        lines.append("### Promotable Entries")
        lines.append("")
        lines.append("Resolved high/critical entries or entries with 2+ See Also links:")
        lines.append("")
        for e in analysis["promotable"]:
            lines.append(f"- `{e['id']}` - {e.get('summary', e.get('category', '?'))}")
        lines.append("")

    # Potential duplicates
    if analysis["potential_duplicates"]:
        lines.append("### Potential Duplicates")
        lines.append("")
        for a, b, score in analysis["potential_duplicates"]:
            lines.append(f"- `{a['id']}` <-> `{b['id']}` (similarity: {score:.0%})")
        lines.append("")

    # Error-to-skill suggestions
    if analysis["skill_suggestions"]:
        lines.append("### Error-to-Skill Suggestions")
        lines.append("")
        lines.append("Tags appearing >= 3 times in error entries (consider extracting as skill):")
        lines.append("")
        for tag, count in sorted(analysis["skill_suggestions"].items(), key=lambda x: -x[1]):
            lines.append(f"- `{tag}` ({count} occurrences)")
        lines.append("")

    # --- Skill health ---
    lines.append("## Skill Health Report")
    lines.append("")
    if not skill_issues:
        lines.append("All skills healthy.")
    else:
        lines.append(f"Found {len(skill_issues)} issue(s):")
        lines.append("")
        lines.append("| Skill | Issue |")
        lines.append("|-------|-------|")
        for si in skill_issues:
            lines.append(f"| {si['skill']} | {si['issue']} |")
    lines.append("")

    # --- Gene health ---
    if gene_analysis is not None:
        lines.append("## Gene Health Report")
        lines.append("")

        by_status = gene_analysis.get("by_status", {})
        active_count = len(by_status.get("active", []))
        stale_count = len(by_status.get("stale", []))
        degraded_count = len(by_status.get("degraded", []))

        lines.append("### Overview")
        lines.append("")
        lines.append("| Status | Count |")
        lines.append("|--------|-------|")
        lines.append(f"| Active | {active_count} |")
        lines.append(f"| Stale | {stale_count} |")
        lines.append(f"| Degraded | {degraded_count} |")
        lines.append(f"| **Total** | **{gene_analysis.get('total', 0)}** |")
        lines.append("")

        # Stale genes
        stale_genes = by_status.get("stale", [])
        if stale_genes:
            lines.append("### Stale Genes (需要审查)")
            lines.append("")
            for g in stale_genes:
                gene_id = g.get("gene_id", "?")
                name = g.get("_dir_name", g.get("name", "?"))
                freshness = g.get("_calc_freshness", "?")
                last_used = g.get("last_used", "never")
                lines.append(f"- `{name}` ({gene_id}) - freshness: {freshness}, last used: {last_used}")
            lines.append("")

        # Degraded genes
        degraded_genes = by_status.get("degraded", [])
        if degraded_genes:
            lines.append("### Degraded Genes (需要决策)")
            lines.append("")
            for g in degraded_genes:
                gene_id = g.get("gene_id", "?")
                name = g.get("_dir_name", g.get("name", "?"))
                freshness = g.get("_calc_freshness", "?")
                last_used = g.get("last_used", "never")
                lines.append(f"- `{name}` ({gene_id}) - freshness: {freshness}, last used: {last_used}")
            lines.append("")

        # Top performing genes
        top_genes = gene_analysis.get("top_genes", [])
        if top_genes:
            lines.append("### Top Performing Genes")
            lines.append("")
            for score, g in top_genes:
                name = g.get("_dir_name", g.get("name", "?"))
                usage = g.get("usage_count", 0)
                lines.append(f"- `{name}` (effectiveness: {score}, usage: {usage})")
            lines.append("")

        # Registry issues
        missing_reg = gene_analysis.get("missing_from_registry", set())
        missing_disk = gene_analysis.get("missing_from_disk", set())
        missing_desc = gene_analysis.get("missing_description", [])
        zero_use = gene_analysis.get("zero_usage", [])

        registry_issues = []
        for name in sorted(missing_reg):
            registry_issues.append(f"Gene `{name}` on disk but missing from registry.json")
        for name in sorted(missing_disk):
            registry_issues.append(f"Gene `{name}` in registry.json but missing from disk")
        for g in missing_desc:
            registry_issues.append(f"Gene `{g.get('_dir_name', '?')}` has missing/TODO description")
        for g in zero_use:
            registry_issues.append(f"Gene `{g.get('_dir_name', '?')}` has zero usage")

        if registry_issues:
            lines.append("### Issues")
            lines.append("")
            for issue in registry_issues:
                lines.append(f"- {issue}")
            lines.append("")

    # --- Gene decay actions ---
    if gene_decay_actions:
        lines.append("## Gene Decay Updates")
        lines.append("")
        for action in gene_decay_actions:
            lines.append(f"- {action}")
        lines.append("")

    # --- Auto-fix actions ---
    if fix_actions:
        lines.append("## Auto-Fix Actions")
        lines.append("")
        for action in fix_actions:
            lines.append(f"- {action}")
        lines.append("")

    # --- Action items ---
    action_items: list[str] = []
    if analysis["promotion_candidates"]:
        action_items.append(f"Promote {len(analysis['promotion_candidates'])} Pattern-Key entries to project memory")
    promo_qualified = [pe for pe in analysis.get("promotion_evaluation", []) if pe["meets_all_criteria"]]
    if promo_qualified:
        targets = set(pe["target"] for pe in promo_qualified)
        action_items.append(
            f"Execute {len(promo_qualified)} promotion(s) to: {', '.join(sorted(targets))}"
        )
    if analysis["promotable"]:
        action_items.append(f"Review {len(analysis['promotable'])} promotable entries")
    if analysis["potential_duplicates"]:
        action_items.append(f"Deduplicate {len(analysis['potential_duplicates'])} potential duplicate pairs")
    if analysis["skill_suggestions"]:
        action_items.append(f"Consider extracting skills for tags: {', '.join(analysis['skill_suggestions'].keys())}")
    fixable = [i for i in skill_issues if i.get("auto_fix")]
    non_fixable = [i for i in skill_issues if not i.get("auto_fix")]
    if non_fixable:
        action_items.append(f"Fix {len(non_fixable)} skill health issues manually")

    # Gene-related action items
    if gene_analysis is not None:
        stale_genes = gene_analysis.get("by_status", {}).get("stale", [])
        degraded_genes = gene_analysis.get("by_status", {}).get("degraded", [])
        if stale_genes:
            action_items.append(f"Review {len(stale_genes)} stale gene(s) for relevance")
        if degraded_genes:
            action_items.append(f"Decide on {len(degraded_genes)} degraded gene(s): update or retire")
        if gene_analysis.get("missing_from_registry"):
            action_items.append(f"Add {len(gene_analysis['missing_from_registry'])} gene(s) to registry.json")
        if gene_analysis.get("missing_from_disk"):
            action_items.append(f"Remove {len(gene_analysis['missing_from_disk'])} stale registry entries")

    # Ecosystem-related action items
    if ecosystem_analysis is not None:
        ea = ecosystem_analysis
        stale = ea.get("stale_skills", [])
        disabled = ea.get("disabled_skills", [])
        if stale:
            action_items.append(f"Review {len(stale)} stale skill(s) — consider removing unused ones")
        if disabled:
            action_items.append(f"Decide on {len(disabled)} disabled skill(s): re-enable or remove")

    if action_items:
        lines.append("## Action Items")
        lines.append("")
        for idx, item in enumerate(action_items, 1):
            lines.append(f"{idx}. {item}")
        lines.append("")

    return "\n".join(lines)


def write_report(report: str, workspace: str, dry_run: bool) -> str | None:
    """Write report to file. Returns path or None if dry-run."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    report_dir = Path(workspace) / REPORT_SUBDIR
    report_path = report_dir / f"{date_str}.md"

    if dry_run:
        return None

    report_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    return str(report_path)


def print_summary(
    analysis: dict,
    skill_issues: list[dict],
    fix_actions: list[str],
    gene_analysis: dict | None = None,
    gene_decay_actions: list[str] | None = None,
    ecosystem_analysis: dict | None = None,
) -> None:
    """Print compact summary to stdout for cron session forwarding."""
    c = analysis["counts"]
    total_pending = len(analysis["pending"])
    print(f"=== Self-Improvement Daily Summary ===")
    print(f"Entries: {c.get('learnings', 0)} learnings, {c.get('errors', 0)} errors, {c.get('features', 0)} features")
    print(f"Pending: {total_pending}")

    if analysis["promotion_candidates"]:
        print(f"Promotion candidates: {len(analysis['promotion_candidates'])}")
    promo_eval = analysis.get("promotion_evaluation", [])
    promo_qualified = [pe for pe in promo_eval if pe["meets_all_criteria"]]
    if promo_qualified:
        print(f"Ready for promotion (all criteria met): {len(promo_qualified)}")
    if analysis["promotable"]:
        print(f"Promotable entries: {len(analysis['promotable'])}")
    if analysis["potential_duplicates"]:
        print(f"Potential duplicates: {len(analysis['potential_duplicates'])}")
    if analysis["skill_suggestions"]:
        print(f"Skill extraction suggestions: {', '.join(analysis['skill_suggestions'].keys())}")

    issues_count = len(skill_issues)
    fixable_count = len([i for i in skill_issues if i.get("auto_fix")])
    if issues_count:
        print(f"Skill health issues: {issues_count} ({fixable_count} auto-fixable)")

    if fix_actions:
        print(f"Auto-fixes applied: {len(fix_actions)}")

    # Gene summary
    if gene_analysis is not None:
        by_status = gene_analysis.get("by_status", {})
        active = len(by_status.get("active", []))
        stale = len(by_status.get("stale", []))
        degraded = len(by_status.get("degraded", []))
        print(f"Genes: {gene_analysis.get('total', 0)} total ({active} active, {stale} stale, {degraded} degraded)")

    if gene_decay_actions:
        print(f"Gene decay updates: {len(gene_decay_actions)}")

    # Ecosystem summary
    if ecosystem_analysis is not None:
        ea = ecosystem_analysis
        parts = [f"{ea.get('skill_count', 0)} skills"]
        parts.append(f"{ea.get('mcp_server_count', 0)} MCP servers")
        parts.append(f"{ea.get('mcp_skill_enabled_count', 0)} MCP skills")
        print(f"Ecosystem: {', '.join(parts)}")
        new_items = len(ea.get("new_skills", [])) + len(ea.get("new_mcp_servers", [])) + len(ea.get("new_mcp_skills", []))
        if new_items and not ea.get("is_first_run"):
            print(f"Today new: +{new_items}")
        stale_count = len(ea.get("stale_skills", []))
        if stale_count:
            print(f"Stale skills (>{SKILL_STALE_DAYS}d): {stale_count}")

    has_actions = (
        analysis["promotion_candidates"]
        or analysis["promotable"]
        or analysis["potential_duplicates"]
        or analysis["skill_suggestions"]
        or [i for i in skill_issues if not i.get("auto_fix")]
    )
    if gene_analysis is not None:
        has_actions = has_actions or (
            gene_analysis.get("by_status", {}).get("stale", [])
            or gene_analysis.get("by_status", {}).get("degraded", [])
            or gene_analysis.get("missing_from_registry")
            or gene_analysis.get("missing_from_disk")
        )
    if ecosystem_analysis is not None:
        has_actions = has_actions or (
            ecosystem_analysis.get("stale_skills")
            or ecosystem_analysis.get("disabled_skills")
        )
    if has_actions:
        print(">>> Action items present - see full report")
    else:
        print("No action items.")


# ===================================================================
# Main
# ===================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Daily self-improvement analysis for OpenClaw",
    )
    parser.add_argument(
        "--workspace",
        default=DEFAULT_WORKSPACE,
        help=f"Workspace directory (default: {DEFAULT_WORKSPACE})",
    )
    parser.add_argument(
        "--skills-dir",
        default=DEFAULT_SKILLS_DIR,
        help=f"Skills directory to scan (default: {DEFAULT_SKILLS_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print report without writing files",
    )
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="Apply safe auto-fixes (default: report only)",
    )
    parser.add_argument(
        "--genes-dir",
        default=None,
        help="Directory containing .genes/ (default: same as --workspace)",
    )
    parser.add_argument(
        "--openclaw-config",
        default=DEFAULT_OPENCLAW_CONFIG,
        help=f"Path to openclaw.json (default: {DEFAULT_OPENCLAW_CONFIG})",
    )
    parser.add_argument(
        "--mcp-config",
        default=DEFAULT_MCP_CONFIG,
        help=f"Path to mcporter.json (default: {DEFAULT_MCP_CONFIG})",
    )
    args = parser.parse_args()

    genes_workspace = args.genes_dir if args.genes_dir else args.workspace

    # Run analysis
    analysis = analyze_learnings(args.workspace)
    skill_issues = check_skill_health(args.skills_dir)

    # Gene analysis
    gene_analysis = analyze_genes(genes_workspace)

    # Ecosystem analysis
    ecosystem = scan_ecosystem(args.skills_dir, args.openclaw_config, args.mcp_config)
    ecosystem_analysis = analyze_ecosystem(ecosystem, args.workspace, args.dry_run)

    # Auto-fix
    fix_actions: list[str] = []
    gene_decay_actions: list[str] = []
    if args.auto_fix:
        fix_actions = apply_fixes(skill_issues, args.skills_dir, args.dry_run)
        gene_decay_actions = update_gene_decay(genes_workspace, args.dry_run)

    # Generate report
    report = generate_report(
        analysis, skill_issues, fix_actions, args.workspace, args.dry_run,
        gene_analysis=gene_analysis,
        gene_decay_actions=gene_decay_actions,
        ecosystem_analysis=ecosystem_analysis,
    )

    # Write report
    report_path = write_report(report, args.workspace, args.dry_run)

    # Print summary
    print_summary(analysis, skill_issues, fix_actions, gene_analysis, gene_decay_actions, ecosystem_analysis)

    if args.dry_run:
        print("\n--- Full Report (dry-run) ---\n")
        print(report)
    elif report_path:
        print(f"\nFull report: {report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
