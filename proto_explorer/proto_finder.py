"""
Module for the logic to try finding the proto import root directory
that can be used as --proto_path argument.
"""
from pathlib import Path
import re
from typing import List, Optional, Tuple


_IMPORT_RE = re.compile(r'^\s*import\s+(?:public|weak\s+)?\"([^\"]+)\"\s*;', re.MULTILINE)


def _extract_imports(proto_file: Path) -> List[str]:
    """
    Return a list of import paths as they appear in the .proto file,
    e.g., ["api/common/common.proto", "google/type/quaternion.proto"].
    """
    try:
        text = proto_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = proto_file.read_text(encoding="latin-1")
    return _IMPORT_RE.findall(text)


def _score_candidate(candidate: Path, proto_file: Path, imports: List[str]) -> Tuple[int, int]:
    """
    Score a candidate root directory.

    Returns (resolved_imports_count, structure_bonus)

    - resolved_imports_count: how many imports exist under this candidate
    - structure_bonus: heuristic bonus if the candidate 'looks like' the import root
      (e.g., the first component of the proto's relative path exists as a dir).
    """
    resolved = 0
    for imp in imports:
        if (candidate / imp).exists():
            resolved += 1

    # Does the candidate look like the proto import root?
    # e.g., for /a/b/new/api/model/v1/model.proto, if candidate=/a/b,
    # then (candidate/"new") should exist as a directory.
    bonus = 0
    try:
        rel = proto_file.relative_to(candidate)
        rel_parts = rel.parts
        if len(rel_parts) >= 2 and (candidate / rel_parts[0]).is_dir():
            bonus = 1
    except ValueError:
        # proto_file is not under candidate; ignore
        pass

    return resolved, bonus


def find_proto_root(proto_file: str | Path, max_levels: int = 16) -> Path:
    """
    Given an absolute or relative path to a .proto file, try to infer the
    proto import root directory suitable for --proto_path argument.

    Strategy:
      1) Parse import statements from the .proto.
      2) Walk up candidate ancestors of the proto file's parent directory.
      3) For each candidate, count how many imports exist under it.
      4) Choose the candidate with the highest score.
      5) Fallback to proto's parent if nothing matches.

    Examples:
      /repo/protos/new/api/model/v1/model.proto
        imports "api/common/common.proto"
      -> returns /repo/protos/new

    Returns:
      Path to the inferred proto root (existing directory).

    Notes:
      This is heuristic but works well for typical repo layouts.
      It assumes there is one root. Multiple roots? Later.
    """
    p = Path(proto_file).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Proto file not found: {p}")
    if p.suffix != ".proto":
        raise ValueError(f"Expected a .proto file, got: {p}")

    imports = _extract_imports(p)

    # Build candidate roots: start from the proto's parent, then walk up.
    # Limit to max_levels to avoid scanning the entire filesystem root in
    # unusual setups.
    candidates: List[Path] = []
    parent = p.parent
    levels = 0
    while True:
        candidates.append(parent)
        levels += 1
        if parent.parent == parent or levels >= max_levels:
            break
        parent = parent.parent

    # Score candidates format
    # (resolved_count, bonus, path)
    best: Optional[Tuple[int, int, Path]] = None
    for cand in candidates:
        if not cand.is_dir():
            continue
        resolved_count, bonus = _score_candidate(cand, p, imports)
        if best is None or (resolved_count, bonus) > (best[0], best[1]):
            best = (resolved_count, bonus, cand)

    if best is None:
        # Extremely unlikely; at minimum the proto's parent should exist.
        return p.parent

    resolved_count, bonus, chosen = best

    # If no imports are present or resolvable, fall back to the lowest
    # ancestor that still provides a clean relative path (parent).
    if resolved_count == 0 and bonus == 0:
        return p.parent

    return chosen
