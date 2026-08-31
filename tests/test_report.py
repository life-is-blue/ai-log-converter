"""Tests for ai_report.py core functions.

Tests call production code directly — no logic duplication.
"""

import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

# Ensure we can import from project root
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_report import (
    parse_distill_ops,
    apply_ops,
    quality_gate,
    parse_lesson_entries,
    _parse_gene_yaml,
    _tokenize_bigram,
    _jaccard,
    _parse_all_lesson_pits,
    _count_memory_rules,
    extract_pattern_counts,
    _merge_soul_entry,
    _parse_soul_sections,
    extract_unabsorbed_soul,
    append_skip,
    read_and_clear_skip_buffer,
    _parse_skipped_section,
    priority_gate,
    _entry_id,
    _ensure_entry_id,
    _apply_dedup_ops,
    _parse_memory_layers,
    _rebuild_memory,
    find_sessions,
    _check_rule_freshness,
    _soul_touched_on_day,
    _report_month_dir,
    _truncate_utf8,
    _repo_web_url,
    _wecom_send,
    cmd_alert,
    cmd_weekly,
    _last_complete_week,
    _entries_in_window,
    _lesson_slugs_in_window,
    _rules_with_week_evidence,
    WECOM_MAX_BYTES,
)
from ai_prompts import MEMORY_SKELETON


class TestParseDistillOps(unittest.TestCase):
    def test_basic_ops(self):
        raw = (
            "ADD MUST: 操作前必全量阅读目标文件\n"
            "STRENGTHEN PREFER: old hint → new full rule\n"
            "WEAKEN MUST: some rule to weaken\n"
            "REMOVE MUST_NOT: deprecated rule\n"
            "NOP\n"
        )
        ops = parse_distill_ops(raw)
        self.assertEqual(len(ops), 4)
        self.assertEqual(ops[0], ("ADD", "MUST", "操作前必全量阅读目标文件"))
        self.assertEqual(ops[1], ("STRENGTHEN", "PREFER", "old hint → new full rule"))
        self.assertEqual(ops[2], ("WEAKEN", "MUST", "some rule to weaken"))
        self.assertEqual(ops[3], ("REMOVE", "MUST_NOT", "deprecated rule"))

    def test_nop_only(self):
        self.assertEqual(parse_distill_ops("NOP"), [])
        self.assertEqual(parse_distill_ops("NOP\n"), [])

    def test_empty_input(self):
        self.assertEqual(parse_distill_ops(""), [])
        self.assertEqual(parse_distill_ops("  \n  "), [])

    def test_invalid_lines_skipped(self):
        raw = "ADD MUST: valid rule\nthis is garbage\nADD PREFER: another"
        ops = parse_distill_ops(raw)
        self.assertEqual(len(ops), 2)

    def test_invalid_section_rejected(self):
        raw = "ADD INVALID_SECTION: some rule"
        ops = parse_distill_ops(raw)
        self.assertEqual(len(ops), 0)

    def test_add_with_pk_tag_parses(self):
        """The pk suffix is carried inside the content — regex must not strip it."""
        raw = "ADD MUST: Always read before edit <!-- pk: read-before-edit -->"
        ops = parse_distill_ops(raw)
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0], ("ADD", "MUST", "Always read before edit <!-- pk: read-before-edit -->"))

    def test_legacy_add_without_pk_still_parses(self):
        raw = "ADD MUST: Always read before edit"
        ops = parse_distill_ops(raw)
        self.assertEqual(ops[0], ("ADD", "MUST", "Always read before edit"))


class TestApplyOps(unittest.TestCase):
    def _skeleton(self):
        return MEMORY_SKELETON.format(date="2026-04-26", version=0)

    def test_add_to_empty(self):
        content = self._skeleton()
        ops = [("ADD", "MUST", "Always read before edit")]
        result = apply_ops(content, ops)
        self.assertIn("- Always read before edit", result)
        self.assertIn("Version: 1", result)

    def test_remove(self):
        content = self._skeleton().replace("## MUST\n", "## MUST\n- old rule to remove\n")
        ops = [("REMOVE", "MUST", "old rule to remove")]
        result = apply_ops(content, ops)
        self.assertNotIn("old rule to remove", result)

    def test_strengthen_with_arrow(self):
        content = self._skeleton().replace("## MUST\n", "## MUST\n- Evidence before claiming\n")
        ops = [("STRENGTHEN", "MUST", "Evidence before claiming → Evidence: show test output")]
        result = apply_ops(content, ops)
        self.assertIn("Evidence: show test output", result)
        self.assertNotIn("Evidence before claiming\n", result)

    def test_weaken_moves_to_prefer(self):
        content = self._skeleton().replace("## MUST\n", "## MUST\n- Strict rule here\n")
        ops = [("WEAKEN", "MUST", "Strict rule here")]
        result = apply_ops(content, ops)
        self.assertNotIn("## MUST\n- Strict rule here", result)
        self.assertIn("Strict rule here (待观察)", result)

    def test_empty_content_creates_skeleton(self):
        ops = [("ADD", "MUST", "First rule ever")]
        result = apply_ops("", ops)
        self.assertIn("## MUST", result)

    def test_add_with_pk_writes_tag_through(self):
        content = self._skeleton()
        ops = [("ADD", "MUST", "Always read before edit <!-- pk: read-before-edit -->")]
        result = apply_ops(content, ops)
        self.assertIn("- Always read before edit <!-- pk: read-before-edit -->", result)

    def test_weaken_preserves_pk_tag(self):
        content = self._skeleton().replace(
            "## MUST\n", "## MUST\n- Strict rule here <!-- pk: strict-rule -->\n")
        ops = [("WEAKEN", "MUST", "Strict rule here <!-- pk: strict-rule -->")]
        result = apply_ops(content, ops)
        self.assertNotIn("## MUST\n- Strict rule here", result)
        self.assertIn("Strict rule here <!-- pk: strict-rule --> (待观察)", result)


class TestQualityGate(unittest.TestCase):
    def test_keeps_valid_bullets(self):
        obs = "- **决策模式**: 先规划再执行，引用了'谋定而后动'"
        result = quality_gate(obs)
        self.assertIn("先规划再执行", result)

    def test_rejects_insufficient_data(self):
        obs = "- 数据不足，无法构建心智模型"
        result = quality_gate(obs)
        self.assertEqual(result, "")

    def test_rejects_speculative(self):
        obs = "- 推测使用 Python 进行开发"
        result = quality_gate(obs)
        self.assertEqual(result, "")

    def test_rejects_too_short(self):
        obs = "- **技术偏好**: 用AI"
        result = quality_gate(obs)
        self.assertEqual(result, "")

    def test_preserves_headers(self):
        obs = "# Title\n- **决策模式**: 先规划再执行，使用了 codex 做验收"
        result = quality_gate(obs)
        self.assertIn("# Title", result)


class TestParseLessonEntries(unittest.TestCase):
    def test_valid_entry(self):
        raw = (
            "## bool-is-int-timestamp\n"
            "> 2026-04-18 | pk: timestamp-parse-guard | area: backend\n\n"
            "**坑**: 时间戳出现 bool\n"
            "**因**: Python bool 是 int 子类\n"
            "**法**: 解析前排除 bool\n"
        )
        entries = parse_lesson_entries(raw, "2026-04-20")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["slug"], "bool-is-int-timestamp")
        self.assertIn("2026-04-20", entries[0]["text"])  # date rewritten

    def test_missing_triple_rejected(self):
        raw = (
            "## incomplete-entry\n"
            "> 2026-04-18 | pk: test\n\n"
            "**坑**: something\n"
            "**因**: reason\n"
            # Missing **法**
        )
        entries = parse_lesson_entries(raw, "2026-04-20")
        self.assertEqual(len(entries), 0)

    def test_none_output(self):
        entries = parse_lesson_entries("NONE", "2026-04-20")
        self.assertEqual(len(entries), 0)

    def test_correction_format(self):
        raw = (
            "## naming-style-correction\n"
            "> 2026-04-26 | pk: naming-consistency | area: docs | type: correction\n\n"
            "**误**: AI 用混合命名（ai_prompts.py + ai-report.py）\n"
            "**正**: 统一用 snake_case（ai_report.py）\n"
            "**因**: 初始命名随意，后续文件沿用了不同约定\n"
        )
        entries = parse_lesson_entries(raw, "2026-04-26")
        self.assertEqual(len(entries), 1)

    def test_correction_without_cause_rejected(self):
        raw = (
            "## bad-correction\n"
            "> 2026-04-26 | pk: test | area: backend | type: correction\n\n"
            "**误**: did X\n"
            "**正**: should do Y\n"
        )
        entries = parse_lesson_entries(raw, "2026-04-26")
        self.assertEqual(len(entries), 0)

    def test_method_format(self):
        raw = (
            "## plan-before-act-method\n"
            "> 2026-04-26 | pk: plan-before-act | area: arch | type: method\n\n"
            "**法**: 谋定而后动\n"
            "**步**: 1) 探索代码库 → 2) 对齐需求 → 3) 出计划 → 4) 执行 → 5) 验证\n"
            "**用**: 非平凡任务（涉及 >3 个文件或架构变更）\n"
        )
        entries = parse_lesson_entries(raw, "2026-04-26")
        self.assertEqual(len(entries), 1)

    def test_old_format_still_works(self):
        """Entries without type: field must still parse with 坑/因/法."""
        raw = (
            "## old-lesson\n"
            "> 2026-04-18 | pk: old-pattern\n\n"
            "**坑**: something broke\n"
            "**因**: root cause\n"
            "**法**: the fix\n"
        )
        entries = parse_lesson_entries(raw, "2026-04-26")
        self.assertEqual(len(entries), 1)


class TestParseGeneYaml(unittest.TestCase):
    def test_basic_fields(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write("gene_id: GEN-20260426-001\n")
            f.write("name: plan-before-act\n")
            f.write("created: 2026-04-26\n")
            f.write("decay_window_days: 90\n")
            f.write("freshness_score: 1.0\n")
            f.write("decay_status: active\n")
            path = f.name
        try:
            result = _parse_gene_yaml(Path(path))
            self.assertIsNotNone(result)
            self.assertEqual(result["gene_id"], "GEN-20260426-001")
            self.assertEqual(result["name"], "plan-before-act")
            self.assertEqual(result["decay_window_days"], "90")
        finally:
            os.unlink(path)

    def test_skips_block_scalars(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write("name: test-gene\n")
            f.write("approach: |\n")
            f.write("  step 1: do something\n")
            f.write("  step 2: do more\n")
            f.write("last_used: 2026-04-20\n")
            path = f.name
        try:
            result = _parse_gene_yaml(Path(path))
            self.assertEqual(result["name"], "test-gene")
            self.assertEqual(result["last_used"], "2026-04-20")
            self.assertNotIn("approach", result)  # block scalar skipped
        finally:
            os.unlink(path)

    def test_nonexistent_file(self):
        self.assertIsNone(_parse_gene_yaml(Path("/nonexistent/gene.yaml")))

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write("")
            path = f.name
        try:
            self.assertIsNone(_parse_gene_yaml(Path(path)))
        finally:
            os.unlink(path)


class TestTokenizeBigram(unittest.TestCase):
    def test_cjk_bigrams(self):
        tokens = _tokenize_bigram("时间戳解析")
        self.assertIn("时间", tokens)
        self.assertIn("间戳", tokens)
        self.assertIn("戳解", tokens)
        self.assertIn("解析", tokens)

    def test_latin_words(self):
        tokens = _tokenize_bigram("Python bool int")
        self.assertIn("python", tokens)
        self.assertIn("bool", tokens)
        self.assertIn("int", tokens)

    def test_mixed(self):
        tokens = _tokenize_bigram("Python的bool是int子类")
        self.assertIn("python", tokens)
        self.assertIn("bool", tokens)
        # CJK bigrams from 子类 etc
        self.assertIn("子类", tokens)

    def test_empty(self):
        self.assertEqual(_tokenize_bigram(""), set())


class TestJaccard(unittest.TestCase):
    def test_identical(self):
        s = {"a", "b", "c"}
        self.assertAlmostEqual(_jaccard(s, s), 1.0)

    def test_disjoint(self):
        self.assertAlmostEqual(_jaccard({"a"}, {"b"}), 0.0)

    def test_partial(self):
        self.assertAlmostEqual(_jaccard({"a", "b"}, {"b", "c"}), 1/3)

    def test_empty(self):
        self.assertAlmostEqual(_jaccard(set(), {"a"}), 0.0)
        self.assertAlmostEqual(_jaccard(set(), set()), 0.0)


class TestParseAllLessonPits(unittest.TestCase):
    def test_extracts_pits(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("# LESSONS.md\n\n")
            f.write("## slug-one\n")
            f.write("<!-- absorbed: true -->\n")
            f.write("> 2026-04-18 | pk: test\n\n")
            f.write("**坑**: 时间戳出现 bool 值\n")
            f.write("**因**: reason\n**法**: fix\n\n")
            f.write("## slug-two\n")
            f.write("<!-- absorbed: false -->\n")
            f.write("> 2026-04-19 | pk: test2\n\n")
            f.write("**坑**: MCP 配置路径错误\n")
            f.write("**因**: reason\n**法**: fix\n")
            path = f.name
        try:
            pits = _parse_all_lesson_pits(Path(path))
            self.assertEqual(len(pits), 2)
            self.assertEqual(pits[0][0], "slug-one")
            self.assertIn("bool", pits[0][1])
            self.assertEqual(pits[1][0], "slug-two")
            self.assertIn("MCP", pits[1][1])
        finally:
            os.unlink(path)

    def test_nonexistent(self):
        self.assertEqual(_parse_all_lesson_pits(Path("/nonexistent")), [])


class TestCountMemoryRules(unittest.TestCase):
    def test_counts_sections(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("## MUST\n\n- rule 1\n- rule 2\n\n")
            f.write("## MUST NOT\n\n- no rule 1\n\n")
            f.write("## PREFER\n\n- prefer 1\n- prefer 2\n- prefer 3\n\n")
            f.write("## CONTEXT\n\n")
            path = f.name
        try:
            counts = _count_memory_rules(Path(path))
            self.assertEqual(counts["MUST"], 2)
            self.assertEqual(counts["MUST NOT"], 1)
            self.assertEqual(counts["PREFER"], 3)
            self.assertEqual(counts["CONTEXT"], 0)
        finally:
            os.unlink(path)


class TestExtractPatternCounts(unittest.TestCase):
    def test_counts_from_soul(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("# SOUL.md\n\n")
            f.write("\n### 2026-04-18\n")
            f.write("- observation <!-- pk: plan-before-act -->\n")
            f.write("- another <!-- pk: tight-loop -->\n")
            f.write("\n### 2026-04-19\n")
            f.write("- repeated <!-- pk: plan-before-act -->\n")
            path = f.name
        try:
            counts = extract_pattern_counts(Path(path))
            self.assertEqual(counts["plan-before-act"], 2)
            self.assertEqual(counts["tight-loop"], 1)
        finally:
            os.unlink(path)




class TestMergeSoulEntry(unittest.TestCase):
    """Tests for _merge_soul_entry()."""

    def _skeleton(self) -> str:
        return (
            "# SOUL.md\n\n"
            "> Last updated: 2026-05-02\n\n"
            "---\n\n"
            "## Identity\n\n"
            "## Preferences\n\n"
            "## Patterns\n\n"
            "## Context\n"
        )

    def test_identity_dedup_jaccard(self):
        """Similar identity entries (Jaccard > 0.5) are skipped."""
        soul = self._skeleton() + "- I prefer clean code\n"
        # Very similar entry: should be deduped
        new_obs = "## Identity\n\n- I prefer clean code style\n"
        result = _merge_soul_entry(soul, new_obs, "2026-05-02")
        # Only 1 identity entry should remain (new one deduped as too similar)
        identity_m = re.search(r"## Identity\n(.*?)(?=\n## |\Z)", result, re.S)
        entries = [l for l in identity_m.group(1).splitlines() if l.strip().startswith("-")]
        self.assertEqual(len(entries), 1)

    def test_preferences_dedup_by_key(self):
        """Same PREFER key appends (dedup is dream's job now)."""
        soul = (
            "# SOUL.md\n\n"
            "## Identity\n\n"
            "## Preferences\n\n"
            "- PREFER streaming over batch\n\n"
            "## Patterns\n\n"
            "## Context\n"
        )
        new_obs = "## Preferences\n\n- PREFER streaming over batch, faster feedback\n"
        result = _merge_soul_entry(soul, new_obs, "2026-05-02")
        # Pure append: 2 entries now (dedup is dream's job)
        pref_m = re.search(r"## Preferences\n(.*?)(?=\n## |\Z)", result, re.S)
        entries = [l for l in pref_m.group(1).splitlines() if l.strip().startswith("-")]
        self.assertEqual(len(entries), 2)
        # Both entries present
        self.assertIn("faster feedback", result)

    def test_preferences_new_appends(self):
        """Different PREFER key appends a new entry."""
        soul = (
            "# SOUL.md\n\n"
            "## Identity\n\n"
            "## Preferences\n\n"
            "- PREFER streaming over batch\n\n"
            "## Patterns\n\n"
            "## Context\n"
        )
        new_obs = "## Preferences\n\n- PREFER small commits\n"
        result = _merge_soul_entry(soul, new_obs, "2026-05-02")
        pref_m = re.search(r"## Preferences\n(.*?)(?=\n## |\Z)", result, re.S)
        entries = [l for l in pref_m.group(1).splitlines() if l.strip().startswith("-")]
        self.assertEqual(len(entries), 2)

    def test_patterns_dedup_by_pk(self):
        """Same pk tag appends (dedup is dream's job now)."""
        soul = (
            "# SOUL.md\n\n"
            "## Identity\n\n"
            "## Preferences\n\n"
            "## Patterns\n\n"
            "- Old wording <!-- pk: plan-before-act -->\n\n"
            "## Context\n"
        )
        new_obs = "## Patterns\n\n- New wording <!-- pk: plan-before-act -->\n"
        result = _merge_soul_entry(soul, new_obs, "2026-05-02")
        # Pure append: both entries present (dedup is dream's job)
        self.assertIn("Old wording", result)
        self.assertIn("New wording", result)
        pat_m = re.search(r"## Patterns\n(.*?)(?=\n## |\Z)", result, re.S)
        entries = [l for l in pat_m.group(1).splitlines() if l.strip().startswith("-")]
        self.assertEqual(len(entries), 2)

    def test_context_dedup_by_prefix(self):
        """Same context fact appends (dedup is dream's job now)."""
        soul = (
            "# SOUL.md\n\n"
            "## Identity\n\n"
            "## Preferences\n\n"
            "## Patterns\n\n"
            "## Context\n\n"
            "- Works at Acme Corp (since 2020) <!-- new: 2026-01-01 -->\n"
        )
        # New entry: same fact, different since-date → both appended (dream consolidates later)
        new_obs = "## Context\n\n- Works at Acme Corp (since 2024)\n"
        result = _merge_soul_entry(soul, new_obs, "2026-05-02")
        ctx_m = re.search(r"## Context\n(.*?)(?=\n## |\Z)", result, re.S)
        entries = [l for l in ctx_m.group(1).splitlines() if l.strip().startswith("-")]
        self.assertEqual(len(entries), 2)

    def test_appended_entry_leaves_blank_line_before_next_section(self):
        """Regression: appending must not glue the last entry to the next ## header."""
        soul = (
            "# SOUL.md\n\n"
            "## Identity\n\n"
            "## Preferences\n\n"
            "- PREFER streaming over batch\n\n"
            "## Patterns\n\n"
            "## Context\n"
        )
        new_obs = "## Preferences\n\n- PREFER small commits\n"
        result = _merge_soul_entry(soul, new_obs, "2026-05-02")
        self.assertIn("PREFER small commits <!-- new: 2026-05-02 -->\n\n## Patterns", result)

    def test_empty_soul_gets_skeleton(self):
        """Empty soul_content gets sections created automatically."""
        soul = "# SOUL.md\n\n"  # no sections at all
        new_obs = "## Identity\n\n- I am a backend engineer\n"
        result = _merge_soul_entry(soul, new_obs, "2026-05-02")
        self.assertIn("## Identity", result)
        self.assertIn("backend engineer", result)


class TestParseSoulSections(unittest.TestCase):
    """Tests for _parse_soul_sections()."""

    def test_parses_four_sections(self):
        content = (
            "# SOUL.md\n\n"
            "## Identity\n\n"
            "- I am a developer\n\n"
            "## Preferences\n\n"
            "- PREFER Python over Java\n"
            "  Why: ecosystem\n"
            "  How: default to Python\n\n"
            "## Patterns\n\n"
            "- Always plan <!-- pk: plan-before-act -->\n\n"
            "## Context\n\n"
            "- Senior engineer at startup\n"
        )
        sections = _parse_soul_sections(content)
        self.assertEqual(len(sections["Identity"]), 1)
        self.assertEqual(len(sections["Preferences"]), 1)
        self.assertEqual(len(sections["Patterns"]), 1)
        self.assertEqual(len(sections["Context"]), 1)

    def test_empty_sections(self):
        content = (
            "## Identity\n\n"
            "## Preferences\n\n"
            "## Patterns\n\n"
            "## Context\n"
        )
        sections = _parse_soul_sections(content)
        self.assertEqual(sections["Identity"], [])
        self.assertEqual(sections["Preferences"], [])
        self.assertEqual(sections["Patterns"], [])
        self.assertEqual(sections["Context"], [])

    def test_multiline_preferences(self):
        """A multi-line Preferences entry (Why/How) stays as one entry."""
        content = (
            "## Preferences\n\n"
            "- PREFER streaming over batch\n"
            "  Why: faster feedback\n"
            "  How: always stream\n\n"
            "## Patterns\n"
        )
        sections = _parse_soul_sections(content)
        self.assertEqual(len(sections["Preferences"]), 1)
        self.assertIn("Why: faster feedback", sections["Preferences"][0])


class TestExtractUnabsorbedSoul(unittest.TestCase):
    """Tests for extract_unabsorbed_soul()."""

    def test_finds_new_entries(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(
                "## Identity\n\n"
                "- I code in Python <!-- new: 2026-05-02 -->\n\n"
                "## Preferences\n\n"
                "## Patterns\n\n"
                "## Context\n"
            )
            path = f.name
        try:
            result = extract_unabsorbed_soul(Path(path))
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0][0], "Identity")
            self.assertIn("Python", result[0][1])
        finally:
            os.unlink(path)

    def test_skips_absorbed(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(
                "## Identity\n\n"
                "- I code in Python <!-- absorbed: 2026-05-01 -->\n\n"
                "## Preferences\n\n"
                "## Patterns\n\n"
                "## Context\n"
            )
            path = f.name
        try:
            result = extract_unabsorbed_soul(Path(path))
            self.assertEqual(len(result), 0)
        finally:
            os.unlink(path)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("")
            path = f.name
        try:
            result = extract_unabsorbed_soul(Path(path))
            self.assertEqual(result, [])
        finally:
            os.unlink(path)




class TestSkipBuffer(unittest.TestCase):
    """Tests for skip-buffer read/write/clear."""

    def test_append_and_read_clears(self):
        with tempfile.TemporaryDirectory() as d:
            logs = Path(d)
            append_skip(logs, 'lessons', [{"slug": "x", "reason": "covered"}])
            entries = read_and_clear_skip_buffer(logs)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]['source'], 'lessons')
            self.assertEqual(entries[0]['slug'], 'x')
            # Buffer should be cleared
            self.assertEqual(read_and_clear_skip_buffer(logs), [])

    def test_empty_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            entries = read_and_clear_skip_buffer(Path(d))
            self.assertEqual(entries, [])

    def test_multiple_sources(self):
        with tempfile.TemporaryDirectory() as d:
            logs = Path(d)
            append_skip(logs, 'lessons', [{"slug": "a", "reason": "covered"}])
            append_skip(logs, 'gene', [{"pk": "b", "decision": "skip", "reason": "weak"}])
            entries = read_and_clear_skip_buffer(logs)
            self.assertEqual(len(entries), 2)
            sources = {e['source'] for e in entries}
            self.assertIn('lessons', sources)
            self.assertIn('gene', sources)
            # After clear
            self.assertEqual(read_and_clear_skip_buffer(logs), [])


class TestTruncateUtf8(unittest.TestCase):
    """Regression: WeCom push truncated by char-slicing a byte-length check,
    which could leave the result over WeCom's real byte limit for CJK text."""

    def test_short_text_unchanged(self):
        self.assertEqual(_truncate_utf8("hello", 100), "hello")

    def test_cuts_on_char_boundary_not_byte_boundary(self):
        # Each CJK char is 3 UTF-8 bytes; cutting at 7 bytes must not split one.
        text = "你好世界"
        result = _truncate_utf8(text, 7)
        result.encode("utf-8")  # raises if a char was split
        self.assertLessEqual(len(result.encode("utf-8")), 7)
        self.assertEqual(result, "你好")

    def test_real_report_stays_under_wecom_limit_after_footer(self):
        """The exact scenario that broke production: byte length was checked,
        but the old code truncated by character count, so a CJK-heavy report
        just above the trigger threshold got the footer appended on top of
        the (unshortened) full text, pushing it past WeCom's real limit."""
        cjk_paragraph = "工作日报内容测试" * 300  # ~1200 chars, ~3600 bytes: over old 4000-byte trigger, under old 3500-char cut
        self.assertGreater(len(cjk_paragraph.encode("utf-8")), WECOM_MAX_BYTES)
        footer = "\n\n...\n\n> 完整日报: https://cnb.cool/ai-alchemy-factory/ai-memory/-/blob/main/reports/2026/08/2026-08-22.md"
        footer_bytes = len(footer.encode("utf-8"))
        result = _truncate_utf8(cjk_paragraph, WECOM_MAX_BYTES - footer_bytes) + footer
        self.assertLessEqual(len(result.encode("utf-8")), WECOM_MAX_BYTES)


class TestRepoWebUrl(unittest.TestCase):
    """Tests for _repo_web_url (derives the report's web link from git remote)."""

    def test_derives_url_from_https_remote(self):
        with tempfile.TemporaryDirectory() as d:
            logs = Path(d)
            subprocess.run(["git", "init", "-q", str(logs)], check=True)
            subprocess.run(
                ["git", "-C", str(logs), "remote", "add", "origin",
                 "https://cnb.cool/ai-alchemy-factory/ai-memory.git"],
                check=True,
            )
            url = _repo_web_url(logs, "reports/2026/08/2026-08-22.md")
            self.assertEqual(
                url,
                "https://cnb.cool/ai-alchemy-factory/ai-memory/-/blob/main/reports/2026/08/2026-08-22.md",
            )

    def test_no_git_repo_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(_repo_web_url(Path(d), "reports/x.md"))


class TestWecomSend(unittest.TestCase):
    """_wecom_send is the shared transport for push and alert; a 200 response
    carrying errcode != 0 means WeCom silently dropped the message."""

    def test_missing_webhook_returns_false(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(_wecom_send("body", "Push"))

    def test_errcode_zero_is_success(self):
        resp = mock.MagicMock()
        resp.read.return_value = b'{"errcode":0,"errmsg":"ok"}'
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda *a: None
        with mock.patch.dict(os.environ, {"WECOM_WEBHOOK_URL": "https://example.com/h"}), \
             mock.patch("ai_report.urlopen", return_value=resp):
            self.assertTrue(_wecom_send("body", "Push"))

    def test_nonzero_errcode_is_failure(self):
        resp = mock.MagicMock()
        resp.read.return_value = b'{"errcode":40058,"errmsg":"invalid content"}'
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda *a: None
        with mock.patch.dict(os.environ, {"WECOM_WEBHOOK_URL": "https://example.com/h"}), \
             mock.patch("ai_report.urlopen", return_value=resp), \
             contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertFalse(_wecom_send("body", "Push"))
        self.assertIn("40058", err.getvalue())

    def test_network_error_is_failure_not_raise(self):
        with mock.patch.dict(os.environ, {"WECOM_WEBHOOK_URL": "https://example.com/h"}), \
             mock.patch("ai_report.urlopen", side_effect=OSError("connection refused")), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertFalse(_wecom_send("body", "Push"))


class TestCmdAlert(unittest.TestCase):
    """A silent cron failure stalled the pipeline for 3 days; alert makes the
    failure visible. It must never raise, or it would mask the real failure."""

    def _args(self, stage, log=None):
        return argparse.Namespace(stage=stage, log=log)

    def test_message_names_stage_and_quotes_log_tail(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "cron.log"
            log.write_text("early noise\n" + "\n".join(f"line{i}" for i in range(50))
                           + "\nERROR: ai-memory has tracked local changes\n")
            with mock.patch("ai_report._wecom_send", return_value=True) as send, \
                 contextlib.redirect_stderr(io.StringIO()):
                cmd_alert(self._args("pull-memory", str(log)))
            body = send.call_args[0][0]
        self.assertIn("pull-memory", body)
        self.assertIn("tracked local changes", body)
        # Tail only — early lines must not be quoted
        self.assertNotIn("early noise", body)
        self.assertLessEqual(len(body.encode("utf-8")), WECOM_MAX_BYTES)

    def test_unreadable_log_still_alerts(self):
        with mock.patch("ai_report._wecom_send", return_value=True) as send, \
             contextlib.redirect_stderr(io.StringIO()):
            cmd_alert(self._args("harvest", "/nonexistent/path.log"))
        self.assertIn("harvest", send.call_args[0][0])

    def test_send_failure_does_not_raise(self):
        with mock.patch("ai_report._wecom_send", return_value=False), \
             contextlib.redirect_stderr(io.StringIO()):
            cmd_alert(self._args("soul"))  # must not raise


class TestReportMonthDir(unittest.TestCase):
    """Tests for _report_month_dir (reports/YYYY/MM/ partitioning)."""

    def test_single_digit_month_zero_padded(self):
        d = _report_month_dir(Path("/x/reports"), date(2026, 3, 9))
        self.assertEqual(d, Path("/x/reports/2026/03"))

    def test_double_digit_month(self):
        d = _report_month_dir(Path("/x/reports"), date(2026, 11, 1))
        self.assertEqual(d, Path("/x/reports/2026/11"))


class TestFindSessions(unittest.TestCase):
    """Regression: root-level jsonl files (e.g. .skip-buffer.jsonl) aren't sessions."""

    def test_excludes_root_level_jsonl(self):
        with tempfile.TemporaryDirectory() as d:
            logs = Path(d)
            (logs / ".skip-buffer.jsonl").write_text('{"source": "lessons"}\n')
            (logs / "claude" / "myproject").mkdir(parents=True)
            (logs / "claude" / "myproject" / "session1.jsonl").write_text('{}\n')
            sessions = find_sessions(logs)
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].name, "session1.jsonl")

    def test_excludes_reports_dir(self):
        with tempfile.TemporaryDirectory() as d:
            logs = Path(d)
            (logs / "reports").mkdir()
            (logs / "reports" / "2026-01-01.jsonl").write_text('{}\n')
            (logs / "claude" / "myproject").mkdir(parents=True)
            (logs / "claude" / "myproject" / "session1.jsonl").write_text('{}\n')
            sessions = find_sessions(logs)
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].name, "session1.jsonl")


class TestCheckRuleFreshness(unittest.TestCase):
    """Regression: freshness bridge must read the current 4-section SOUL.md
    format (### date blocks no longer exist), via new:/absorbed: tags."""

    def _write(self, d, name, content):
        path = Path(d) / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_recent_pk_marks_matching_rule_evidenced(self):
        with tempfile.TemporaryDirectory() as d:
            today = date.today().isoformat()
            soul = self._write(d, "SOUL.md", (
                "# SOUL.md\n\n## Identity\n\n## Preferences\n\n## Patterns\n\n"
                f"- Plans before acting | Evidence: x <!-- pk: plan-before-act --> <!-- new: {today} -->\n\n"
                "## Context\n"
            ))
            memory = self._write(d, "MEMORY.md", (
                "## MUST\n\n- Plan before acting on ambiguous requests\n"
                "- Unrelated rule about something else\n"
            ))
            results = dict(_check_rule_freshness(memory, soul))
            self.assertEqual(results["Plan before acting on ambiguous requests"], "evidenced")
            self.assertEqual(results["Unrelated rule about something else"], "stale")

    def test_old_pk_tag_does_not_count_as_recent(self):
        with tempfile.TemporaryDirectory() as d:
            soul = self._write(d, "SOUL.md", (
                "# SOUL.md\n\n## Identity\n\n## Preferences\n\n## Patterns\n\n"
                "- Plans before acting | Evidence: x <!-- pk: plan-before-act --> <!-- absorbed: 2020-01-01 -->\n\n"
                "## Context\n"
            ))
            memory = self._write(d, "MEMORY.md", (
                "## MUST\n\n- Plan before acting on ambiguous requests\n"
            ))
            results = dict(_check_rule_freshness(memory, soul))
            self.assertEqual(results["Plan before acting on ambiguous requests"], "stale")

    def test_pk_word_requires_whole_word_match(self):
        """Regression: plain substring matching false-positived pk word
        'review' against 'reviewer' and 'commit' against 'Commits'."""
        with tempfile.TemporaryDirectory() as d:
            today = date.today().isoformat()
            soul = self._write(d, "SOUL.md", (
                "# SOUL.md\n\n## Identity\n\n## Preferences\n\n## Patterns\n\n"
                f"- Reviews before commit | Evidence: x <!-- pk: review-before-commit --> <!-- new: {today} -->\n\n"
                "## Context\n"
            ))
            memory = self._write(d, "MEMORY.md", (
                "## MUST\n\n"
                "- Writing pipeline: draft -> reviewer -> illustrator\n"
                "- Use Conventional Commits format for messages\n"
                "- Please commit small changes\n"
            ))
            results = dict(_check_rule_freshness(memory, soul))
            self.assertEqual(results["Writing pipeline: draft -> reviewer -> illustrator"], "stale")
            self.assertEqual(results["Use Conventional Commits format for messages"], "stale")
            self.assertEqual(results["Please commit small changes"], "evidenced")

    def test_exact_pk_join_marks_evidenced(self):
        """Tier 1: a pk-bearing rule joins on its OWN pk, not on word matches."""
        with tempfile.TemporaryDirectory() as d:
            today = date.today().isoformat()
            soul = self._write(d, "SOUL.md", (
                "# SOUL.md\n\n## Identity\n\n## Preferences\n\n## Patterns\n\n"
                f"- Plans before acting | Evidence: x <!-- pk: plan-before-act --> <!-- new: {today} -->\n\n"
                "## Context\n"
            ))
            memory = self._write(d, "MEMORY.md", (
                "## MUST\n\n"
                "- Always plan first <!-- pk: plan-before-act -->\n"
            ))
            results = dict(_check_rule_freshness(memory, soul))
            self.assertEqual(results["Always plan first <!-- pk: plan-before-act -->"], "evidenced")

    def test_exact_pk_join_marks_stale_when_pk_not_recent(self):
        """Tier 1 must decide BEFORE Tier 2: a pk-bearing rule with a non-recent
        pk stays 'stale' even if its words match another recent pk."""
        with tempfile.TemporaryDirectory() as d:
            today = date.today().isoformat()
            # recent pk is plan-before-act; the rule's pk is review-before-commit (not recent)
            soul = self._write(d, "SOUL.md", (
                "# SOUL.md\n\n## Identity\n\n## Preferences\n\n## Patterns\n\n"
                f"- Plans before acting | Evidence: x <!-- pk: plan-before-act --> <!-- new: {today} -->\n\n"
                "## Context\n"
            ))
            memory = self._write(d, "MEMORY.md", (
                "## MUST\n\n"
                "- Plan then review before committing <!-- pk: review-before-commit -->\n"
            ))
            results = dict(_check_rule_freshness(memory, soul))
            # words "plan"/"before" match the recent pk, but the rule's OWN pk is stale
            self.assertEqual(results["Plan then review before committing <!-- pk: review-before-commit -->"], "stale")

    def test_rule_without_pk_falls_back_to_word_split(self):
        """Tier 2 unchanged for pk-less rules: word match → evidenced, else stale."""
        with tempfile.TemporaryDirectory() as d:
            today = date.today().isoformat()
            soul = self._write(d, "SOUL.md", (
                "# SOUL.md\n\n## Identity\n\n## Preferences\n\n## Patterns\n\n"
                f"- Plans before acting | Evidence: x <!-- pk: plan-before-act --> <!-- new: {today} -->\n\n"
                "## Context\n"
            ))
            memory = self._write(d, "MEMORY.md", (
                "## MUST\n\n"
                "- Plan before acting on ambiguous requests\n"
                "- Completely unrelated rule\n"
            ))
            results = dict(_check_rule_freshness(memory, soul))
            self.assertEqual(results["Plan before acting on ambiguous requests"], "evidenced")
            self.assertEqual(results["Completely unrelated rule"], "stale")

    def test_malformed_pk_tag_falls_back_without_crashing(self):
        with tempfile.TemporaryDirectory() as d:
            today = date.today().isoformat()
            soul = self._write(d, "SOUL.md", (
                "# SOUL.md\n\n## Identity\n\n## Preferences\n\n## Patterns\n\n"
                f"- Plans before acting | Evidence: x <!-- pk: plan-before-act --> <!-- new: {today} -->\n\n"
                "## Context\n"
            ))
            memory = self._write(d, "MEMORY.md", (
                "## MUST\n\n"
                "- Rule with id only <!-- id: abc12345 -->\n"
                "- Rule with broken pk <!-- pk: -->\n"
            ))
            results = dict(_check_rule_freshness(memory, soul))
            # neither matches a recent pk's words → both stale, no crash
            self.assertEqual(results["Rule with id only <!-- id: abc12345 -->"], "stale")
            self.assertEqual(results["Rule with broken pk <!-- pk: -->"], "stale")


class TestSoulTouchedOnDay(unittest.TestCase):
    """Regression: `make leader` runs soul then distill in the same chain, and
    distill rewrites `new: DAY` → `absorbed: DAY`. The daily report's section 7
    must still show `✓` for a day whose entries were produced *and* absorbed
    that day — otherwise SOUL shows `—` forever under the normal chain."""

    def test_new_tag_counts(self):
        self.assertTrue(_soul_touched_on_day(
            "- entry <!-- new: 2026-08-22 -->", date.fromisoformat("2026-08-22")))

    def test_absorbed_tag_counts_when_new_was_rewritten(self):
        # distill rewrote new: → absorbed: same day; soul did run that day
        self.assertTrue(_soul_touched_on_day(
            "- entry <!-- absorbed: 2026-08-22 -->", date.fromisoformat("2026-08-22")))

    def test_different_day_does_not_count(self):
        self.assertFalse(_soul_touched_on_day(
            "- entry <!-- absorbed: 2026-08-21 -->", date.fromisoformat("2026-08-22")))
        self.assertFalse(_soul_touched_on_day(
            "- entry <!-- new: 2026-08-21 -->", date.fromisoformat("2026-08-22")))

    def test_no_tags_does_not_count(self):
        self.assertFalse(_soul_touched_on_day(
            "- entry with no lifecycle tags", date.fromisoformat("2026-08-22")))


class TestCmdDistillPkAttach(unittest.TestCase):
    """End-to-end: a pk-bearing unabsorbed LESSONS entry → ADD op with pk tag →
    MEMORY.md rule carries <!-- pk: xxx --> → freshness marks it evidenced."""

    def test_pk_flows_from_entry_to_rule(self):
        from unittest import mock
        from types import SimpleNamespace
        import ai_report as ar

        with tempfile.TemporaryDirectory() as d:
            today = date.today().isoformat()
            # unabsorbed LESSONS entry carrying a pk
            lessons = Path(d) / "LESSONS.md"
            lessons.write_text(
                "# LESSONS.md\n\n"
                "## plan-before-act\n"
                f"> {today} | pk: plan-before-act | area: arch | type: method | priority: 80\n\n"
                "**法**: 先规划再执行\n"
                "**步**: 1) 探索 → 2) 对齐 → 3) 执行\n"
                "**用**: 非平凡任务\n",
                encoding="utf-8")
            soul = Path(d) / "SOUL.md"
            soul.write_text(
                "# SOUL.md\n\n## Identity\n\n## Preferences\n\n## Patterns\n\n## Context\n",
                encoding="utf-8")
            memory = Path(d) / "MEMORY.md"
            # 与 MEMORY_SKELETON 一致的格式（apply_ops 设计时预期的锚点结构）。
            # 注意：真实生产 MEMORY 带 ### Universal 子层，apply_ops 的 ADD 会
            # 追加到段尾（子层之外）——那是独立的现存 bug，不在本次范围。
            memory.write_text(
                "## MUST\n\n## MUST NOT\n\n## PREFER\n\n## CONTEXT\n",
                encoding="utf-8")

            # Fake the LLM: it saw the pk in the entry prose and echoes it on the rule
            fake_response = (
                "ADD PREFER: 非平凡任务先规划对齐再动手 <!-- pk: plan-before-act -->\n"
                "## Skipped\nNone"
            )
            args = SimpleNamespace(soul=str(soul), memory=str(memory),
                                   lessons=str(lessons), force=True, logs=d)
            with mock.patch.object(ar, "call_engine", return_value=fake_response):
                ar.cmd_distill(args)

            mem = memory.read_text(encoding="utf-8")
            self.assertIn("非平凡任务先规划对齐再动手 <!-- pk: plan-before-act -->", mem)
            # entry got marked absorbed
            self.assertIn("absorbed: true", lessons.read_text(encoding="utf-8"))

            # freshness now exact-joins: pk in SOUL? No — but the LESSONS source had
            # it; freshness reads SOUL only, so without SOUL evidence it's stale
            results = dict(_check_rule_freshness(memory, soul))
            self.assertEqual(
                results["非平凡任务先规划对齐再动手 <!-- pk: plan-before-act -->"], "stale")


class TestParseSkippedSection(unittest.TestCase):
    """Tests for _parse_skipped_section."""

    def test_strips_skipped_section(self):
        raw = "ADD MUST: some rule\n\n## Skipped\n- slug-a: covered by rule X\n"
        main, items = _parse_skipped_section(raw)
        self.assertEqual(main.strip(), "ADD MUST: some rule")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['slug'], 'slug-a')
        self.assertIn('covered', items[0]['reason'])

    def test_none_skipped(self):
        raw = "ADD MUST: some rule\n\n## Skipped\nNone"
        main, items = _parse_skipped_section(raw)
        self.assertEqual(items, [])
        self.assertIn("ADD MUST", main)

    def test_no_skipped_section(self):
        raw = "ADD MUST: some rule"
        main, items = _parse_skipped_section(raw)
        self.assertEqual(main, raw)
        self.assertEqual(items, [])


class TestGeneReviewParse(unittest.TestCase):
    """Test that gene review JSONL output is parsed correctly."""

    def test_parses_jsonl_decisions(self):
        sample = (
            '{"pk": "a", "action": "create", "confidence": "high", "reason": "new"}\n'
            '{"pk": "b", "action": "skip", "reason": "covered"}\n'
        )
        decisions = []
        for line in sample.splitlines():
            if line.strip().startswith('{'):
                decisions.append(json.loads(line))
        self.assertEqual(len(decisions), 2)
        self.assertEqual(decisions[0]["action"], "create")
        self.assertEqual(decisions[0]["confidence"], "high")
        self.assertEqual(decisions[1]["action"], "skip")
        self.assertEqual(decisions[1]["reason"], "covered")

    def test_skips_non_json_lines(self):
        sample = (
            'Some header text\n'
            '{"pk": "x", "action": "create", "confidence": "medium", "reason": "ok"}\n'
            '# comment\n'
        )
        decisions = []
        for line in sample.splitlines():
            line = line.strip()
            if line.startswith('{'):
                try:
                    decisions.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["pk"], "x")


class TestPriorityGate(unittest.TestCase):
    """Mechanical priority<50 cutoff — drops low-signal SOUL entries without
    relying on the LLM to self-restrain."""

    def test_drops_low_priority_preferences(self):
        obs = (
            "## Preferences\n"
            "- PREFER a / REJECT b <!-- priority: 90 -->\n"
            "  Why: strong reason\n"
            "  How: do this\n"
            "- PREFER c / REJECT d <!-- priority: 30 -->\n"
            "  Why: weak reason\n"
            "  How: do that\n"
        )
        result = priority_gate(obs)
        self.assertIn("PREFER a", result)
        self.assertNotIn("PREFER c", result)

    def test_keeps_identity_regardless_of_priority(self):
        obs = "## Identity\n- some identity fact\n"
        result = priority_gate(obs)
        self.assertIn("some identity fact", result)

    def test_missing_priority_tag_defaults_to_keep(self):
        obs = "## Context\n- untagged fact (since 2026-01-01)\n"
        result = priority_gate(obs)
        self.assertIn("untagged fact", result)

    def test_no_section_headers_passes_through(self):
        obs = "NONE"
        self.assertEqual(priority_gate(obs), "NONE")


class TestEntryId(unittest.TestCase):
    """Stable content-hash ids used by the structured dream dedup."""

    def test_id_stable_across_lifecycle_tag_changes(self):
        e1 = "- PREFER foo <!-- new: 2026-08-01 -->"
        e2 = "- PREFER foo <!-- absorbed: 2026-08-10 -->"
        self.assertEqual(_entry_id(e1), _entry_id(e2))

    def test_ensure_entry_id_assigns_and_reuses(self):
        eid, tagged = _ensure_entry_id("- PREFER bar")
        self.assertIn("<!-- id:", tagged)
        eid2, tagged2 = _ensure_entry_id(tagged)
        self.assertEqual(eid, eid2)
        self.assertEqual(tagged, tagged2)

    def test_different_content_different_id(self):
        _, t1 = _ensure_entry_id("- PREFER foo")
        _, t2 = _ensure_entry_id("- PREFER bar")
        self.assertNotEqual(_entry_id(t1), _entry_id(t2))


class TestApplyDedupOps(unittest.TestCase):
    """Structured remove/merge decision application — the core of the
    ID-based dream refactor. LLM output here is untrusted input."""

    def _pool(self, entries):
        id_map = {}
        for e in entries:
            eid, tagged = _ensure_entry_id(e)
            id_map[eid] = tagged
        return id_map

    def test_remove_drops_entry(self):
        id_map = self._pool(["- A entry", "- B entry"])
        target = next(iter(id_map))
        result = _apply_dedup_ops(id_map, [{"op": "remove", "ids": [target]}], set())
        self.assertEqual(len(result), 1)

    def test_merge_replaces_two_with_one(self):
        id_map = self._pool(["- A entry", "- B entry", "- C entry"])
        ids = list(id_map)
        ops = [{"op": "merge", "ids": [ids[0], ids[1]], "content": "- merged A+B"}]
        result = _apply_dedup_ops(id_map, ops, set())
        self.assertEqual(len(result), 2)
        self.assertTrue(any("merged A+B" in r for r in result))
        self.assertTrue(any("C entry" in r for r in result))

    def test_merge_preserves_new_tag_if_any_source_unabsorbed(self):
        id_map = self._pool(["- A entry", "- B entry"])
        ids = list(id_map)
        result = _apply_dedup_ops(
            id_map, [{"op": "merge", "ids": ids, "content": "- merged"}], {ids[0]}
        )
        self.assertTrue(any("<!-- new:" in r for r in result))

    def test_unknown_id_in_op_is_ignored(self):
        id_map = self._pool(["- A entry"])
        result = _apply_dedup_ops(id_map, [{"op": "remove", "ids": ["deadbeef"]}], set())
        self.assertEqual(len(result), 1)

    def test_merge_without_content_is_ignored(self):
        id_map = self._pool(["- A entry", "- B entry"])
        ids = list(id_map)
        result = _apply_dedup_ops(id_map, [{"op": "merge", "ids": ids, "content": ""}], set())
        self.assertEqual(len(result), 2)

    def test_unknown_op_is_ignored(self):
        id_map = self._pool(["- A entry"])
        result = _apply_dedup_ops(id_map, [{"op": "explode", "ids": list(id_map)}], set())
        self.assertEqual(len(result), 1)

    def test_double_claimed_id_second_op_ignored(self):
        id_map = self._pool(["- A entry", "- B entry"])
        ids = list(id_map)
        ops = [
            {"op": "remove", "ids": [ids[0]]},
            {"op": "merge", "ids": [ids[0], ids[1]], "content": "- merged"},
        ]
        result = _apply_dedup_ops(id_map, ops, set())
        # ids[0] already claimed by remove; the merge op still applies to the
        # remaining unclaimed id (ids[1]) alone, producing one merged entry
        self.assertEqual(len(result), 1)

    def test_empty_ops_is_no_op(self):
        id_map = self._pool(["- A entry", "- B entry"])
        result = _apply_dedup_ops(id_map, [], set())
        self.assertEqual(len(result), 2)


class TestParseMemoryLayers(unittest.TestCase):
    """MEMORY.md parsing must degrade gracefully on missing/malformed
    sections instead of crashing — this is what makes the 2026-05-11-style
    corruption (3 of 4 sections silently dropped) recoverable rather than
    a hard failure."""

    def test_tolerates_missing_sections(self):
        broken = (
            "# MEMORY.md\n\n"
            "## MUST\n\n"
            "### Universal\n- rule one\n- rule two\n\n"
            "### Project-specific (ai-distillery)\n- proj rule\n"
        )
        layers = _parse_memory_layers(broken)
        self.assertEqual(layers["MUST"]["Universal"], ["- rule one", "- rule two"])
        self.assertEqual(layers["MUST"]["Project-specific"], ["- proj rule"])
        self.assertEqual(layers["MUST NOT"]["Universal"], [])
        self.assertEqual(layers["PREFER"]["Universal"], [])
        self.assertEqual(layers["CONTEXT"]["Universal"], [])

    def test_legacy_flat_format_treated_as_universal(self):
        flat = "# MEMORY.md\n\n## MUST\n- flat rule one\n- flat rule two\n"
        layers = _parse_memory_layers(flat)
        self.assertEqual(layers["MUST"]["Universal"], ["- flat rule one", "- flat rule two"])

    def test_rebuild_always_emits_all_four_sections(self):
        layers = _parse_memory_layers("# MEMORY.md\n\n## MUST\n\n### Universal\n- x\n")
        rebuilt = _rebuild_memory("# MEMORY.md\n", layers)
        for section in ("MUST", "MUST NOT", "PREFER", "CONTEXT"):
            self.assertIn(f"## {section}", rebuilt)


class TestLastCompleteWeek(unittest.TestCase):
    """Weekly covers the last FINISHED Mon-Sun week — run midweek or Sunday and
    it still reports last week, never the week in progress."""

    def test_monday_gets_previous_week(self):
        self.assertEqual(_last_complete_week(date(2026, 8, 31)), (date(2026, 8, 24), date(2026, 8, 30)))

    def test_sunday_still_previous_week(self):
        self.assertEqual(_last_complete_week(date(2026, 9, 6)), (date(2026, 8, 24), date(2026, 8, 30)))

    def test_wednesday_still_previous_week(self):
        self.assertEqual(_last_complete_week(date(2026, 9, 2)), (date(2026, 8, 24), date(2026, 8, 30)))

    def test_tuesday(self):
        self.assertEqual(_last_complete_week(date(2026, 9, 1)), (date(2026, 8, 24), date(2026, 8, 30)))


class TestWeeklyDeltaHelpers(unittest.TestCase):
    START, END = date(2026, 8, 24), date(2026, 8, 30)

    def test_entries_in_window_both_tag_forms(self):
        content = (
            "## Identity\n"
            "- in-window new | Evidence: \"x\" <!-- new: 2026-08-26 -->\n"
            "- in-window absorbed | Evidence: \"y\" <!-- absorbed: 2026-08-27 -->\n"
            "  Why: continuation line must not be a separate entry\n"
            "- before window <!-- absorbed: 2026-08-23 -->\n"
            "- after window <!-- absorbed: 2026-08-31 -->\n"
            "- no tag at all\n"
            "not an entry: <!-- absorbed: 2026-08-26 -->\n"
        )
        got = _entries_in_window(content, self.START, self.END)
        self.assertEqual(got, ["in-window new", "in-window absorbed"])

    def test_lesson_slugs_in_window(self):
        content = (
            "## old-lesson\n> 2026-08-01 | pk: old | area: x | type: trap\n**坑**: ...\n"
            "## new-lesson\n> 2026-08-27 | pk: new | area: x | type: trap\n**坑**: ...\n"
        )
        self.assertEqual(_lesson_slugs_in_window(content, self.START, self.END), ["new-lesson"])

    def test_rules_with_week_evidence(self):
        soul = "- pattern entry <!-- pk: hot --> <!-- absorbed: 2026-08-26 -->\n"
        lessons = "## some-lesson\n> 2026-08-01 | pk: cold | area: x | type: trap\n"
        memory = (
            "- rule with fresh evidence <!-- pk: hot --> <!-- id: a1 -->\n"
            "- rule with stale evidence <!-- pk: cold --> <!-- id: b2 -->\n"
            "- rule without pk <!-- id: c3 -->\n"
        )
        got = _rules_with_week_evidence(soul, lessons, memory, self.START, self.END)
        self.assertEqual(got, ["rule with fresh evidence"])


class TestCmdWeekly(unittest.TestCase):
    def _setup_logs(self, logs: Path):
        # One session active on two in-window days, one outside, in "proj";
        # 16 one-session noise projects to exercise the top-N + aggregate tail.
        for name, ts in [("s1", "2026-08-25T10:00:00"), ("s2", "2026-08-26T11:00:00"),
                         ("s3", "2026-09-05T10:00:00")]:
            p = logs / "claude" / "proj" / f"{name}.jsonl"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"meta": {"timestamp": ts}}) + "\n", encoding="utf-8")
        for i in range(16):
            p = logs / "claude" / f"tmp-noise-{i}" / "s.jsonl"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"meta": {"timestamp": "2026-08-25T10:00:00"}}) + "\n",
                         encoding="utf-8")
        # Daily reports for two of the week's days.
        rdir = logs / "reports" / "2026" / "08"
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "2026-08-25.md").write_text("# 2026-08-25\n\n做了 A。\n", encoding="utf-8")
        (rdir / "2026-08-26.md").write_text("# 2026-08-26\n\n做了 B。\n", encoding="utf-8")
        # Knowledge files with one in-window delta each.
        (logs / "SOUL.md").write_text(
            "## Identity\n- new observation <!-- absorbed: 2026-08-26 -->\n", encoding="utf-8")
        (logs / "MEMORY.md").write_text(
            "# MEMORY.md\n\n## MUST\n\n### Universal\n- fresh rule <!-- pk: hot --> <!-- id: a1 -->\n",
            encoding="utf-8")
        (logs / "LESSONS.md").write_text(
            "## new-lesson\n> 2026-08-27 | pk: hot | area: x | type: trap\n**坑**: ...\n",
            encoding="utf-8")

    def test_generates_report_and_pushes_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp)
            self._setup_logs(logs)
            sent = {}
            canned = "## 本周要点\n- 要点甲\n- 要点乙\n\n## 本周工作汇总\n\nLLM 摘要\n"
            with mock.patch.dict(os.environ, {"WECOM_WEBHOOK_URL": "https://example.com/h"}), \
                 mock.patch("ai_report.call_engine", return_value=canned) as llm, \
                 mock.patch("ai_report._wecom_send", return_value=True) as send:
                cmd_weekly(argparse.Namespace(date=date(2026, 8, 31), logs=str(logs)))
                sent["md"] = send.call_args[0][0]
            out = logs / "reports" / "2026" / "08" / "weekly-2026-08-24.md"
            self.assertTrue(out.exists(), "weekly report file must be written")
            content = out.read_text(encoding="utf-8")
            self.assertIn("周报 2026-08-24 ~ 2026-08-30", content)
            self.assertIn("| 2026-08-25 | 17 |", content)
            self.assertNotIn("2026-09-05", content)  # out-of-window session excluded
            self.assertIn("本周新增 1 条观察", content)
            self.assertIn("new observation", content)
            self.assertIn("本周有新证据支撑 1 条", content)
            self.assertIn("new-lesson", content)
            self.assertIn("LLM 摘要", content)
            # File keeps tables but caps the project list at 15 + aggregate tail
            self.assertIn("| 其他 2 项 | 2 |", content)
            # One atomic synthesis call over the daily reports
            prompt = llm.call_args[0][0]
            self.assertIn("2026-08-25 日报", prompt)
            self.assertIn("2026-08-26 日报", prompt)
            self.assertFalse(llm.call_args.kwargs.get("allow_chunking", True))
            # Push is a purpose-built digest: no tables, highlights + counts only
            md = sent["md"]
            self.assertLessEqual(len(md.encode("utf-8")), WECOM_MAX_BYTES)
            self.assertIn("周报 2026-08-24 ~ 2026-08-30", md)
            self.assertIn("**本周要点**", md)
            self.assertIn("- 要点甲", md)
            self.assertIn("工作量: 18 sessions", md.replace("*", ""))
            self.assertIn("主力项目", md)
            self.assertIn("其他 13 项", md)
            self.assertIn("知识库: SOUL +1 · MEMORY 1 条获新证据 · LESSONS +1", md.replace("*", ""))
            self.assertIn("new observation", md)
            for table_marker in ("| 日期 |", "| 工具 |", "| 项目 |", "|------|"):
                self.assertNotIn(table_marker, md, "WeCom renders no tables")

    def test_no_webhook_skips_push(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp)
            self._setup_logs(logs)
            with mock.patch.dict(os.environ, {}, clear=False), \
                 mock.patch("ai_report.call_engine", return_value="x"), \
                 mock.patch("ai_report._wecom_send", return_value=True) as send:
                os.environ.pop("WECOM_WEBHOOK_URL", None)
                cmd_weekly(argparse.Namespace(date=date(2026, 8, 31), logs=str(logs)))
            send.assert_not_called()

    def test_empty_week_skips_push_but_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp)
            with mock.patch.dict(os.environ, {"WECOM_WEBHOOK_URL": "https://example.com/h"}), \
                 mock.patch("ai_report._wecom_send", return_value=True) as send, \
                 contextlib.redirect_stderr(io.StringIO()):
                cmd_weekly(argparse.Namespace(date=date(2026, 8, 31), logs=str(logs)))
            send.assert_not_called()
            out = logs / "reports" / "2026" / "08" / "weekly-2026-08-24.md"
            self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
