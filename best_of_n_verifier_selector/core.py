"""Deterministic Best-of-N candidate patch verifier and minimal-diff selector."""
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Set


@dataclass
class DiffStats:
    files_touched: List[str]
    added_lines: int
    removed_lines: int
    hunk_count: int

    @property
    def total_churn(self) -> int:
        return self.added_lines + self.removed_lines


@dataclass
class CandidatePatch:
    candidate_id: str
    diff_text: str
    tests_passed: bool
    tests_total: int = 0
    tests_passing_count: int = 0
    lint_errors: int = 0
    type_errors: int = 0
    runtime_ms: float = 0.0


@dataclass
class RankedCandidate:
    candidate: CandidatePatch
    diff_stats: DiffStats
    eligible: bool
    composite_score: float
    rejection_reasons: List[str] = field(default_factory=list)


@dataclass
class SelectionResult:
    winner: Optional[CandidatePatch]
    leaderboard: List[RankedCandidate]


def parse_diff_stats(diff_text: str) -> DiffStats:
    """Parses a unified diff to extract touched files, line churn, and hunk count."""
    files: List[str] = []
    seen: Set[str] = set()
    added = 0
    removed = 0
    hunks = 0

    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            if path != "/dev/null" and path not in seen:
                seen.add(path)
                files.append(path)
        elif line.startswith("--- "):
            continue
        elif line.startswith("@@ "):
            hunks += 1
        elif line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1

    return DiffStats(files_touched=files, added_lines=added, removed_lines=removed, hunk_count=hunks)


def select_best_patch(
    candidates: Sequence[CandidatePatch],
    protected_paths: Optional[Sequence[str]] = None,
    max_churn: Optional[int] = None,
    allow_lint_errors: bool = False,
) -> SelectionResult:
    """Evaluates N candidate patches and selects the cleanest minimal passing patch."""
    if not candidates:
        raise ValueError("candidates must not be empty")

    protected = set(protected_paths or [])
    ranked: List[RankedCandidate] = []

    for cand in candidates:
        stats = parse_diff_stats(cand.diff_text)
        reasons: List[str] = []
        if not cand.tests_passed:
            reasons.append("Unit test suite failed")
        if cand.type_errors > 0:
            reasons.append(f"{cand.type_errors} type errors")
        if not allow_lint_errors and cand.lint_errors > 0:
            reasons.append(f"{cand.lint_errors} lint errors")
        if stats.total_churn == 0:
            reasons.append("Empty diff produces no code change")
        if max_churn is not None and stats.total_churn > max_churn:
            reasons.append(f"Churn {stats.total_churn} exceeds max_churn {max_churn}")
        touched_protected = sorted(set(stats.files_touched) & protected)
        if touched_protected:
            reasons.append(f"Modified protected paths: {', '.join(touched_protected)}")

        eligible = len(reasons) == 0
        pass_ratio = (cand.tests_passing_count / cand.tests_total) if cand.tests_total > 0 else (1.0 if cand.tests_passed else 0.0)
        # Higher score is better: reward passing, penalize churn, file spread, lint/type debt.
        score = (
            (1000.0 if eligible else 0.0)
            + (100.0 * pass_ratio)
            - (1.5 * stats.total_churn)
            - (8.0 * len(stats.files_touched))
            - (25.0 * cand.lint_errors)
            - (40.0 * cand.type_errors)
            - (0.01 * cand.runtime_ms)
        )
        ranked.append(RankedCandidate(cand, stats, eligible, round(score, 4), reasons))

    ranked.sort(
        key=lambda r: (
            1 if r.eligible else 0,
            r.composite_score,
            -r.diff_stats.total_churn,
            r.candidate.candidate_id,
        ),
        reverse=True,
    )
    winner = ranked[0].candidate if ranked[0].eligible else None
    return SelectionResult(winner=winner, leaderboard=ranked)
