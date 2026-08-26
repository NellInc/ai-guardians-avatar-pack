#!/usr/bin/env python3
"""Deterministically build the immutable AI Guardians avatar CDN pack.

The builder consumes an explicit, external-only P2 closure inventory. It never
discovers files by recursively copying a broad source tree. A staged pack is
verified by the independent ``verify_pack.py`` implementation before it can
replace the requested version directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath

SCHEMA = 1
STATUS = "immutable_production_runtime_asset_pack"
INVENTORY_STATUS = "p2_product_freeze"
DEFAULT_VERSION = "v1"
VERSION_PATTERN = re.compile(r"v[1-9][0-9]*")
MAX_FILE_BYTES = 50_000_000
MANIFEST_ROW_KEYS = frozenset(
    {"family", "media_role", "path", "runtime_path", "sha256", "size"}
)
INVENTORY_ROW_KEYS = frozenset(
    {"family", "media_role", "runtime_path", "sha256", "size"}
)
CONTENT_TYPES = {
    ".png": "image/png",
    ".webm": "video/webm",
    ".webp": "image/webp",
}
ROLE_EXTENSIONS = {
    "blink_alpha_mask": {".png", ".webp"},
    "blink_overlay": {".webp"},
    "blink_rgba_layer": {".png"},
    "living_portrait": {".webm"},
    "mouth_alpha_mask": {".png", ".webp"},
    "mouth_atlas": {".webp"},
    "mouth_rgba_layer": {".png"},
    "mouth_mask": {".png"},
    "mouth_sprite": {".png"},
    "oral_motion_patch": {".webm"},
    "portrait_transition": {".webm"},
    "semantic_alpha_mask": {".png", ".webp"},
    "semantic_pulse": {".webp"},
    "semantic_rgba_layer": {".png"},
    "thinking_contact_foreground": {".webm"},
}
ROLE_PATH_PATTERNS = {
    "blink_alpha_mask": (
        r"images/chars/_derived/cast_speech_v1/almiro/"
        r"blink/weight_[0-9]{3}\.alpha\.webp",
        r"images/chars/_derived/cast_speech_v1/[a-z0-9_]+/"
        r"blink/[a-z0-9_]+/weight_[0-9]{3}\.alpha\.webp",
        r"images/chars/_derived/cast_speech_v1/almiro/"
        r"blink/weight_[0-9]{3}\.alpha\.png",
        r"images/chars/_derived/cast_speech_v1/[a-z0-9_]+/"
        r"blink/[a-z0-9_]+/weight_[0-9]{3}\.alpha\.png",
    ),
    "blink_overlay": (
        r"images/chars/_derived/cast_speech_v1/almiro/"
        r"blink/weight_[0-9]{3}\.webp",
        r"images/chars/_derived/cast_speech_v1/[a-z0-9_]+/"
        r"blink/[a-z0-9_]+/weight_[0-9]{3}\.webp",
    ),
    "blink_rgba_layer": (
        r"images/chars/_derived/cast_speech_v1/almiro/"
        r"blink/weight_[0-9]{3}\.rgba\.png",
        r"images/chars/_derived/cast_speech_v1/[a-z0-9_]+/"
        r"blink/[a-z0-9_]+/weight_[0-9]{3}\.rgba\.png",
    ),
    "living_portrait": (
        r"images/chars/_derived/cast_living_v1/(?P<rig>[a-z0-9_]+)/"
        r"(?P=rig)_[a-z0-9_]+_alive_v1\.webm",
        r"images/chars/_derived/cast_living_successors_v1/"
        r"expression_expansion_v2/(?P<successor_rig>[a-z0-9_]+)/"
        r"(?P=successor_rig)_[a-z0-9_]+_alive_v1\.webm",
        r"images/chars/_derived/whiskr_speech_v1/living/"
        r"whiskr_[a-z0-9_]+_alive_v1\.webm",
        r"images/chars/_derived/yuki_video_avatar_pilot_v1/"
        r"yuki_[a-z0-9_]+_alive_v1\.webm",
        r"images/chars/animated/ally_[a-z0-9_]+_alive\.webm",
    ),
    "mouth_atlas": (
        r"images/chars/_derived/cast_speech_v1/[a-z0-9_]+/"
        r"atlases/[a-z0-9_]+/[A-Za-z0-9_]+\.webp",
        r"images/chars/_derived/whiskr_speech_v1/[a-z0-9_]+/"
        r"[A-Za-z0-9_]+\.webp",
        r"images/chars/_derived/yuki_speech_lab/benchmark_v2/"
        r"source_warp_atlases/[a-z0-9_]+/[A-Za-z0-9_]+\.webp",
    ),
    "mouth_alpha_mask": (
        r"images/chars/_derived/cast_speech_v1/[a-z0-9_]+/"
        r"atlases/[a-z0-9_]+/[A-Za-z0-9_]+\.alpha\.webp",
        r"images/chars/_derived/whiskr_speech_v1/[a-z0-9_]+/"
        r"[A-Za-z0-9_]+\.alpha\.webp",
        r"images/chars/_derived/yuki_speech_lab/benchmark_v2/"
        r"source_warp_atlases/[a-z0-9_]+/[A-Za-z0-9_]+\.alpha\.webp",
        r"images/chars/_derived/cast_speech_v1/[a-z0-9_]+/"
        r"atlases/[a-z0-9_]+/[A-Za-z0-9_]+\.alpha\.png",
        r"images/chars/_derived/whiskr_speech_v1/[a-z0-9_]+/"
        r"[A-Za-z0-9_]+\.alpha\.png",
        r"images/chars/_derived/yuki_speech_lab/benchmark_v2/"
        r"source_warp_atlases/[a-z0-9_]+/[A-Za-z0-9_]+\.alpha\.png",
    ),
    "mouth_rgba_layer": (
        r"images/chars/_derived/cast_speech_v1/[a-z0-9_]+/"
        r"atlases/[a-z0-9_]+/[A-Za-z0-9_]+\.rgba\.png",
        r"images/chars/_derived/whiskr_speech_v1/[a-z0-9_]+/"
        r"[A-Za-z0-9_]+\.rgba\.png",
        r"images/chars/_derived/yuki_speech_lab/benchmark_v2/"
        r"source_warp_atlases/[a-z0-9_]+/[A-Za-z0-9_]+\.rgba\.png",
    ),
    "mouth_mask": (
        r"images/chars/_derived/ally_animation_lab/"
        r"expression_oral_layers_runtime89_mouth_only_v1/"
        r"mouth_(?:bed|corner)_mask\.png",
    ),
    "mouth_sprite": (
        r"images/chars/_derived/ally_animation_lab/"
        r"expression_oral_layers_runtime89_mouth_only_v1/"
        r"mouth/[A-Za-z0-9_]+\.png",
    ),
    "oral_motion_patch": (
        r"images/chars/_derived/ally_animation_lab/oral_motion_patches_v1/"
        r"ally_[a-z0-9_]+_oral\.webm",
    ),
    "portrait_transition": (
        r"images/chars/animated/transitions/ally_[a-z0-9_]+_to_[a-z0-9_]+\.webm",
    ),
    "semantic_pulse": (
        r"images/chars/_derived/cast_speech_v1/atlas/pulse/"
        r"[a-z0-9_]+\.webp",
    ),
    "semantic_rgba_layer": (
        r"images/chars/_derived/cast_speech_v1/atlas/pulse/"
        r"[a-z0-9_]+\.rgba\.png",
    ),
    "semantic_alpha_mask": (
        r"images/chars/_derived/cast_speech_v1/atlas/pulse/"
        r"[a-z0-9_]+\.alpha\.webp",
        r"images/chars/_derived/cast_speech_v1/atlas/pulse/"
        r"[a-z0-9_]+\.alpha\.png",
    ),
    "thinking_contact_foreground": (
        r"images/chars/_derived/ally_animation_lab/"
        r"thinking_contact_foregrounds_v1/ally_[a-z0-9_]+_foreground\.webm",
    ),
}
ALLOWED_TREES = (
    "images/chars/_derived/cast_living_v1",
    "images/chars/_derived/cast_living_successors_v1/expression_expansion_v2",
    "images/chars/_derived/cast_speech_v1",
    "images/chars/_derived/whiskr_speech_v1",
    "images/chars/_derived/yuki_video_avatar_pilot_v1",
    "images/chars/_derived/yuki_speech_lab/benchmark_v2/source_warp_atlases",
    "images/chars/_derived/ally_animation_lab/oral_motion_patches_v1",
    "images/chars/_derived/ally_animation_lab/thinking_contact_foregrounds_v1",
    "images/chars/_derived/ally_animation_lab/expression_oral_layers_runtime89_mouth_only_v1",
    "images/chars/animated",
)
FORBIDDEN_MARKERS = (
    "/review/",
    "contact_sheet",
    "comparison",
    "local_neural",
    "phoneme_loop",
    "proof_of_concept",
    "prototype",
    "/scratch/",
    "speech_poc",
    "static_speech_hybrid",
)
FORBIDDEN_RUNTIME_PATHS = frozenset(
    {
        "images/chars/_derived/yuki_video_avatar_pilot_v1/review_contact_sheet_v1.jpg",
        "images/chars/_derived/yuki_video_avatar_pilot_v1/transitions/"
        "yuki_concerned_to_professional_v1.webm",
        "images/chars/_derived/yuki_video_avatar_pilot_v1/transitions/"
        "yuki_normal_to_concerned_v1.webm",
        "images/chars/_derived/yuki_video_avatar_pilot_v1/"
        "yuki_static_speech_hybrid_comparison_v1.webm",
        "images/chars/animated/ally_neutral_speech_local_neural.webm",
        "images/chars/animated/ally_neutral_speech_phoneme_loop.webm",
        "images/chars/animated/ally_neutral_speech_poc_v2.webm",
    }
)
ALLY_ORAL_ROOT = "images/chars/_derived/ally_animation_lab/oral_motion_patches_v1"
ALLY_FOREGROUND_ROOT = (
    "images/chars/_derived/ally_animation_lab/thinking_contact_foregrounds_v1"
)
TRANSITION_PATTERN = re.compile(
    r"images/chars/animated/transitions/"
    r"(ally_[a-z0-9_]+_to_[a-z0-9_]+)\.webm"
)
ALLY_LIVING_PATTERN = re.compile(r"images/chars/animated/(ally_[a-z0-9_]+_alive)\.webm")
EXPECTED_TRANSITION_STEMS = (
    "ally_concerned_to_helpful",
    "ally_concerned_to_neutral",
    "ally_concerned_to_sad",
    "ally_concerned_to_thinking",
    "ally_happy_to_neutral",
    "ally_happy_to_thinking",
    "ally_helpful_to_concerned",
    "ally_helpful_to_neutral",
    "ally_helpful_to_thinking",
    "ally_neutral_to_concerned",
    "ally_neutral_to_happy",
    "ally_neutral_to_helpful",
    "ally_neutral_to_sad",
    "ally_neutral_to_thinking",
    "ally_sad_to_concerned",
    "ally_sad_to_helpful",
    "ally_sad_to_neutral",
    "ally_sad_to_thinking",
    "ally_thinking_to_concerned",
    "ally_thinking_to_helpful",
    "ally_thinking_to_neutral",
    "ally_thinking_to_sad",
)
EXPECTED_ALLY_LIVING_STEMS = (
    "ally_concerned_alive",
    "ally_happy_alive",
    "ally_helpful_alive",
    "ally_neutral_alive",
    "ally_sad_alive",
    "ally_thinking_alive",
)


class PackBuildError(RuntimeError):
    """The explicit immutable pack contract did not hold."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise PackBuildError(f"{label} is not an exact SHA-256")
    return value


def require_candidate_sha(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise PackBuildError("inventory candidate_sha is not an exact Git SHA")
    return value


def normalize_runtime_path(value: object) -> str:
    if not isinstance(value, str):
        raise PackBuildError(f"runtime path is not a string: {value!r}")
    path = value
    if (
        not path
        or path != path.strip()
        or "\\" in path
        or path.startswith("/")
        or path.startswith("game/")
        or re.match(r"^v[1-9][0-9]*/", path)
        or unicodedata.normalize("NFC", path) != path
        or any(ord(character) < 32 for character in path)
        or re.fullmatch(r"[A-Za-z0-9_./-]+", path) is None
    ):
        raise PackBuildError(f"unsafe or noncanonical runtime path: {value!r}")
    parts = PurePosixPath(path).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise PackBuildError(f"unsafe runtime path components: {value!r}")
    if path in FORBIDDEN_RUNTIME_PATHS:
        raise PackBuildError(f"explicitly forbidden non-runtime avatar asset: {path}")
    if not any(path == tree or path.startswith(tree + "/") for tree in ALLOWED_TREES):
        raise PackBuildError(f"runtime path is outside production avatar trees: {path}")
    lowered = "/" + path.casefold() + "/"
    if any(marker in lowered for marker in FORBIDDEN_MARKERS):
        raise PackBuildError(
            f"runtime path looks like review or experimental media: {path}"
        )
    return path


def parse_positive_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise PackBuildError(f"{label} is not an exact JSON integer: {value!r}")
    number = value
    if number <= 0:
        raise PackBuildError(f"{label} must be positive")
    if number > MAX_FILE_BYTES:
        raise PackBuildError(f"{label} exceeds the pre-push 50 MB ceiling: {number}")
    return number


def validate_media_contract(
    runtime_path: str, family: object, role: object
) -> tuple[str, str]:
    if not isinstance(family, str) or not isinstance(role, str):
        raise PackBuildError(f"family/media role must be strings for {runtime_path}")
    family_name = family
    role_name = role
    if not re.fullmatch(r"[a-z0-9_]+", family_name):
        raise PackBuildError(f"invalid asset family for {runtime_path}: {family!r}")
    if role_name == "static_source":
        raise PackBuildError(
            f"static fallback cannot enter the external pack: {runtime_path}"
        )
    if role_name not in ROLE_EXTENSIONS:
        raise PackBuildError(f"unknown media role for {runtime_path}: {role!r}")
    extension = PurePosixPath(runtime_path).suffix.lower()
    if extension not in CONTENT_TYPES or extension not in ROLE_EXTENSIONS[role_name]:
        raise PackBuildError(
            f"extension/role mismatch for {runtime_path}: {extension} {role_name}"
        )
    if not any(
        re.fullmatch(pattern, runtime_path) for pattern in ROLE_PATH_PATTERNS[role_name]
    ):
        raise PackBuildError(
            f"media role/path namespace mismatch for {runtime_path}: {role_name}"
        )
    return family_name, role_name


def verify_file_magic(path: Path, extension: str) -> None:
    with path.open("rb") as handle:
        header = handle.read(64)
    if header.startswith(b"version https://git-lfs.github.com/spec/v1"):
        raise PackBuildError(f"Git LFS pointer is not a runtime payload: {path}")
    valid = {
        ".png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        ".webm": header.startswith(b"\x1aE\xdf\xa3"),
        ".webp": len(header) >= 12
        and header[:4] == b"RIFF"
        and header[8:12] == b"WEBP",
    }[extension]
    if not valid:
        raise PackBuildError(f"payload magic does not match {extension}: {path}")


def ensure_regular_source(source_root: Path, runtime_path: str) -> Path:
    candidate = source_root.joinpath(*PurePosixPath(runtime_path).parts)
    cursor = source_root
    for part in PurePosixPath(runtime_path).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise PackBuildError(f"source payload traverses a symlink: {runtime_path}")
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise PackBuildError(f"source payload is missing: {runtime_path}") from exc
    if source_root not in resolved.parents or not resolved.is_file():
        raise PackBuildError(f"source payload escapes the game root: {runtime_path}")
    return resolved


def inventory_contract_sha(rows: Sequence[Mapping[str, object]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(
            (
                f"{row['runtime_path']}\0{row['size']}\0{row['sha256']}\0"
                f"{row['family']}\0{row['media_role']}\n"
            ).encode("utf-8")
        )
    return digest.hexdigest()


def load_inventory(
    inventory_path: Path, source_root: Path, candidate_sha: str | None
) -> tuple[list[dict[str, object]], dict[str, str]]:
    raw = inventory_path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackBuildError("closure inventory is not valid UTF-8 JSON") from exc
    if not isinstance(payload, Mapping):
        raise PackBuildError("closure inventory root is not an object")
    if set(payload) != {"schema", "status", "candidate_sha", "files"}:
        raise PackBuildError(f"closure inventory root keys drifted: {sorted(payload)}")
    if (
        type(payload.get("schema")) is not int
        or payload.get("schema") != SCHEMA
        or payload.get("status") != INVENTORY_STATUS
    ):
        raise PackBuildError("closure inventory schema/status drifted")
    inventory_candidate = require_candidate_sha(payload.get("candidate_sha"))
    if candidate_sha is not None and inventory_candidate != require_candidate_sha(
        candidate_sha
    ):
        raise PackBuildError("CLI candidate SHA does not equal the closure inventory")
    raw_rows = payload.get("files")
    if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
        raise PackBuildError("closure inventory files is not a flat list")

    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    casefold_seen: dict[str, str] = {}
    for raw_row in raw_rows:
        if not isinstance(raw_row, Mapping) or set(raw_row) != INVENTORY_ROW_KEYS:
            raise PackBuildError(f"closure inventory row keys drifted: {raw_row!r}")
        runtime_path = normalize_runtime_path(raw_row["runtime_path"])
        if runtime_path in seen:
            raise PackBuildError(f"duplicate runtime path: {runtime_path}")
        folded = runtime_path.casefold()
        if folded in casefold_seen:
            raise PackBuildError(
                "case-insensitive path collision: "
                f"{casefold_seen[folded]} and {runtime_path}"
            )
        seen.add(runtime_path)
        casefold_seen[folded] = runtime_path
        family, role = validate_media_contract(
            runtime_path, raw_row["family"], raw_row["media_role"]
        )
        size = parse_positive_int(raw_row["size"], f"size for {runtime_path}")
        digest = require_sha256(raw_row["sha256"], f"SHA for {runtime_path}")
        source = ensure_regular_source(source_root, runtime_path)
        observed_size = source.stat().st_size
        observed_sha = sha256_file(source)
        if observed_size != size or observed_sha != digest:
            raise PackBuildError(
                f"frozen source drifted for {runtime_path}: "
                f"size {observed_size}/{size}, SHA {observed_sha}/{digest}"
            )
        verify_file_magic(source, PurePosixPath(runtime_path).suffix.lower())
        rows.append(
            {
                "runtime_path": runtime_path,
                "size": size,
                "sha256": digest,
                "family": family,
                "media_role": role,
                "_source": source,
            }
        )
    ordered = sorted(rows, key=lambda row: str(row["runtime_path"]).encode("utf-8"))
    if [row["runtime_path"] for row in rows] != [
        row["runtime_path"] for row in ordered
    ]:
        raise PackBuildError("closure inventory rows are not in bytewise path order")
    public_rows = [
        {key: value for key, value in row.items() if key != "_source"}
        for row in ordered
    ]
    validate_ally_dependency_closure(public_rows)
    return ordered, {
        "candidate_sha": inventory_candidate,
        "inventory_sha256": sha256_bytes(raw),
        "inventory_contract_sha256": inventory_contract_sha(public_rows),
    }


def validate_alpha_mask_closure(
    rows: Sequence[Mapping[str, object]], version: str
) -> None:
    by_path = {str(row["runtime_path"]): row for row in rows}
    if version in {"v5", "v7"}:
        alpha_pairs = {
            "blink_overlay": "blink_rgba_layer",
            "mouth_atlas": "mouth_rgba_layer",
            "semantic_pulse": "semantic_rgba_layer",
        }
        mask_extension = ".rgba.png"
    else:
        alpha_pairs = {
            "blink_overlay": "blink_alpha_mask",
            "mouth_atlas": "mouth_alpha_mask",
            "semantic_pulse": "semantic_alpha_mask",
        }
        mask_extension = ".alpha.png" if int(version[1:]) >= 4 else ".alpha.webp"
    expected_masks: set[str] = set()
    for row in rows:
        role = str(row["media_role"])
        mask_role = alpha_pairs.get(role)
        if mask_role is None:
            continue
        runtime_path = str(row["runtime_path"])
        mask_path = runtime_path[:-5] + mask_extension
        expected_masks.add(mask_path)
        mask = by_path.get(mask_path)
        if (
            mask is None
            or mask.get("media_role") != mask_role
            or mask.get("family") != row.get("family")
        ):
            raise PackBuildError(
                f"{runtime_path} lacks its exact {mask_role}: {mask_path}"
            )
    observed_masks = {
        str(row["runtime_path"])
        for row in rows
        if str(row["media_role"]) in set(alpha_pairs.values())
    }
    if observed_masks != expected_masks:
        raise PackBuildError(
            "alpha-mask closure drifted: "
            f"missing={sorted(expected_masks - observed_masks)} "
            f"extra={sorted(observed_masks - expected_masks)}"
        )


def validate_ally_dependency_closure(rows: Sequence[Mapping[str, object]]) -> None:
    by_path = {str(row["runtime_path"]): row for row in rows}
    transitions = [row for row in rows if row["media_role"] == "portrait_transition"]
    expected_transition_paths = {
        f"images/chars/animated/transitions/{stem}.webm"
        for stem in EXPECTED_TRANSITION_STEMS
    }
    observed_transition_paths = {str(row["runtime_path"]) for row in transitions}
    if observed_transition_paths != expected_transition_paths:
        raise PackBuildError(
            "A.L.L.Y. transition identities drifted: "
            f"missing={sorted(expected_transition_paths - observed_transition_paths)} "
            f"extra={sorted(observed_transition_paths - expected_transition_paths)}"
        )

    expected_living_paths = {
        f"images/chars/animated/{stem}.webm" for stem in EXPECTED_ALLY_LIVING_STEMS
    }
    observed_living_paths = {
        str(row["runtime_path"])
        for row in rows
        if row["media_role"] == "living_portrait"
        and str(row["runtime_path"]).startswith("images/chars/animated/ally_")
        and "/transitions/" not in str(row["runtime_path"])
    }
    if observed_living_paths != expected_living_paths:
        raise PackBuildError(
            "A.L.L.Y. living identities drifted: "
            f"missing={sorted(expected_living_paths - observed_living_paths)} "
            f"extra={sorted(observed_living_paths - expected_living_paths)}"
        )

    expected_oral_paths = {
        f"{ALLY_ORAL_ROOT}/{stem}_oral.webm"
        for stem in (*EXPECTED_ALLY_LIVING_STEMS, *EXPECTED_TRANSITION_STEMS)
    }
    observed_oral_paths = {
        str(row["runtime_path"])
        for row in rows
        if row["media_role"] == "oral_motion_patch"
    }
    if observed_oral_paths != expected_oral_paths:
        raise PackBuildError(
            "A.L.L.Y. oral-motion closure drifted: "
            f"missing={sorted(expected_oral_paths - observed_oral_paths)} "
            f"extra={sorted(observed_oral_paths - expected_oral_paths)}"
        )

    foreground_stems = {
        stem
        for stem in EXPECTED_TRANSITION_STEMS
        if "ally_thinking_to_" in stem or "_to_thinking" in stem
    } | {"ally_thinking_alive"}
    expected_foreground_paths = {
        f"{ALLY_FOREGROUND_ROOT}/{stem}_foreground.webm" for stem in foreground_stems
    }
    observed_foreground_paths = {
        str(row["runtime_path"])
        for row in rows
        if row["media_role"] == "thinking_contact_foreground"
    }
    if observed_foreground_paths != expected_foreground_paths:
        raise PackBuildError(
            "A.L.L.Y. foreground closure drifted: "
            f"missing={sorted(expected_foreground_paths - observed_foreground_paths)} "
            f"extra={sorted(observed_foreground_paths - expected_foreground_paths)}"
        )

    def require_dependency(path: str, role: str, owner: str) -> None:
        row = by_path.get(path)
        if row is None or row.get("media_role") != role:
            raise PackBuildError(f"{owner} lacks exact {role} dependency: {path}")

    for row in transitions:
        runtime_path = str(row["runtime_path"])
        match = TRANSITION_PATTERN.fullmatch(runtime_path)
        if match is None:
            raise PackBuildError(
                f"portrait_transition is not an A.L.L.Y. production transition: {runtime_path}"
            )
        stem = match.group(1)
        require_dependency(
            f"{ALLY_ORAL_ROOT}/{stem}_oral.webm",
            "oral_motion_patch",
            runtime_path,
        )
        if "ally_thinking_to_" in stem or "_to_thinking" in stem:
            require_dependency(
                f"{ALLY_FOREGROUND_ROOT}/{stem}_foreground.webm",
                "thinking_contact_foreground",
                runtime_path,
            )

    ally_living = [
        row for row in rows if str(row["runtime_path"]) in expected_living_paths
    ]
    for row in ally_living:
        runtime_path = str(row["runtime_path"])
        match = ALLY_LIVING_PATTERN.fullmatch(runtime_path)
        if match is None:
            raise PackBuildError(f"invalid A.L.L.Y. living path: {runtime_path}")
        stem = match.group(1)
        require_dependency(
            f"{ALLY_ORAL_ROOT}/{stem}_oral.webm",
            "oral_motion_patch",
            runtime_path,
        )
        if stem == "ally_thinking_alive":
            require_dependency(
                f"{ALLY_FOREGROUND_ROOT}/{stem}_foreground.webm",
                "thinking_contact_foreground",
                runtime_path,
            )


def add_aggregate(aggregates: dict[str, dict[str, int]], key: str, size: int) -> None:
    row = aggregates.setdefault(key, {"files": 0, "bytes": 0})
    row["files"] += 1
    row["bytes"] += size


def build_manifest(
    rows: Sequence[Mapping[str, object]],
    metadata: Mapping[str, str],
    version: str,
) -> dict[str, object]:
    files: list[dict[str, object]] = []
    extensions: dict[str, dict[str, int]] = {}
    mime_types: dict[str, dict[str, int]] = {}
    families: dict[str, dict[str, int]] = {}
    roles: dict[str, dict[str, int]] = {}
    contract_digest = hashlib.sha256()
    for row in rows:
        runtime_path = str(row["runtime_path"])
        public_path = f"{version}/{runtime_path}"
        size = int(row["size"])
        manifest_row = {
            "family": row["family"],
            "media_role": row["media_role"],
            "path": public_path,
            "runtime_path": runtime_path,
            "sha256": row["sha256"],
            "size": size,
        }
        if set(manifest_row) != MANIFEST_ROW_KEYS:
            raise AssertionError("internal manifest row schema drift")
        files.append(manifest_row)
        extension = PurePosixPath(runtime_path).suffix.lower()
        add_aggregate(extensions, extension, size)
        add_aggregate(mime_types, CONTENT_TYPES[extension], size)
        add_aggregate(families, str(row["family"]), size)
        add_aggregate(roles, str(row["media_role"]), size)
        contract_digest.update(
            (f"{public_path}\0{size}\0{row['sha256']}\0{row['media_role']}\n").encode(
                "utf-8"
            )
        )
    contract_sha = contract_digest.hexdigest()
    byte_count = sum(int(row["size"]) for row in files)
    return {
        "schema": SCHEMA,
        "version": version,
        "status": STATUS,
        "source": {
            "candidate_sha": metadata["candidate_sha"],
            "repository": "NellWatson/AI-Guardians",
            "inventory_sha256": metadata["inventory_sha256"],
            "inventory_contract_sha256": metadata["inventory_contract_sha256"],
        },
        "license": {
            "identifier": "LicenseRef-Proprietary",
            "holder": "Nell Watson",
            "notice": (
                "All rights reserved. Distribution is limited to AI Guardians "
                "runtime delivery."
            ),
        },
        "content_types": dict(sorted(CONTENT_TYPES.items())),
        "extensions": dict(sorted(extensions.items())),
        "mime_types": dict(sorted(mime_types.items())),
        "families": dict(sorted(families.items())),
        "media_roles": dict(sorted(roles.items())),
        "contract": {
            "files": len(files),
            "bytes": byte_count,
            "ordering": "ascending UTF-8 path order",
            "record_encoding": "path\\0size\\0sha256\\0media_role\\n",
            "sha256": contract_sha,
        },
        "contract_sha256": contract_sha,
        "files": files,
    }


def json_bytes(payload: Mapping[str, object]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_staged_pack(
    stage_root: Path,
    rows: Sequence[Mapping[str, object]],
    manifest: Mapping[str, object],
    version: str,
) -> dict[str, object]:
    version_root = stage_root / version
    version_root.mkdir(parents=True)
    (stage_root / ".nojekyll").touch()
    for row in rows:
        destination = version_root.joinpath(
            *PurePosixPath(str(row["runtime_path"])).parts
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(row["_source"]), destination)
        destination.chmod(0o644)
    manifest_raw = json_bytes(manifest)
    manifest_path = version_root / "manifest.json"
    manifest_path.write_bytes(manifest_raw)
    manifest_sha = sha256_bytes(manifest_raw)
    receipt = {
        "schema": SCHEMA,
        "status": "sealed_pack_receipt",
        "version": version,
        "candidate_sha": manifest["source"]["candidate_sha"],  # type: ignore[index]
        "manifest": {
            "path": f"{version}/manifest.json",
            "bytes": len(manifest_raw),
            "sha256": manifest_sha,
        },
        "contract": {
            "files": manifest["contract"]["files"],  # type: ignore[index]
            "bytes": manifest["contract"]["bytes"],  # type: ignore[index]
            "sha256": manifest["contract_sha256"],
        },
        "inventory": {
            "sha256": manifest["source"]["inventory_sha256"],  # type: ignore[index]
            "contract_sha256": manifest["source"][  # type: ignore[index]
                "inventory_contract_sha256"
            ],
        },
    }
    receipt_path = version_root / "receipt.json"
    receipt_path.write_bytes(json_bytes(receipt))
    return receipt


def run_independent_verifier(
    pack_root: Path,
    inventory_path: Path,
    version: str,
    transactional_backup: bool = False,
) -> dict[str, object]:
    verifier = Path(__file__).with_name("verify_pack.py")
    command = [
        sys.executable,
        str(verifier),
        "--pack-root",
        str(pack_root),
        "--version",
        version,
        "--inventory",
        str(inventory_path),
        "--json",
    ]
    if transactional_backup:
        command.append("--transactional-backup")
    process = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise PackBuildError(
            "independent staged verification failed:\n"
            + process.stdout
            + process.stderr
        )
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise PackBuildError("independent verifier returned invalid JSON") from exc
    expected_status = (
        "passed_transactional_install" if transactional_backup else "passed"
    )
    if result.get("status") != expected_status:
        raise PackBuildError(f"independent verifier did not pass: {result}")
    return result


def directory_contract(root: Path) -> tuple[list[str], str]:
    paths = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix().encode("utf-8"),
    )
    digest = hashlib.sha256()
    names: list[str] = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        names.append(relative)
        digest.update(
            f"{relative}\0{path.stat().st_size}\0{sha256_file(path)}\n".encode("utf-8")
        )
    return names, digest.hexdigest()


def validate_nojekyll(pack_root: Path, create_missing: bool) -> None:
    nojekyll = pack_root / ".nojekyll"
    if nojekyll.is_symlink():
        raise PackBuildError("Pages .nojekyll must not be a symlink")
    if nojekyll.exists():
        if not nojekyll.is_file() or nojekyll.stat().st_size != 0:
            raise PackBuildError("Pages pack requires an empty regular .nojekyll")
        return
    if not create_missing:
        raise PackBuildError("Pages pack requires an empty regular .nojekyll")
    nojekyll.touch(exist_ok=False)


def install_version(stage_root: Path, pack_root: Path, version: str) -> Path | None:
    staged = stage_root / version
    target = pack_root / version
    backup = pack_root / f".{version}.prebuild-backup"
    if not staged.is_dir() or staged.is_symlink():
        raise PackBuildError(f"staged pack version is invalid: {staged}")
    if backup.exists() or backup.is_symlink():
        raise PackBuildError(f"stale pack backup blocks atomic install: {backup}")
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise PackBuildError(
            f"existing pack version is not a regular directory: {target}"
        )
    moved_old = False
    try:
        if target.exists():
            target.rename(backup)
            moved_old = True
        staged.rename(target)
    except Exception:
        if moved_old and backup.exists() and not target.exists():
            backup.rename(target)
        raise
    return backup if moved_old else None


def rollback_version(pack_root: Path, version: str, backup: Path | None) -> None:
    target = pack_root / version
    if target.is_symlink():
        target.unlink()
    elif target.exists():
        if not target.is_dir():
            raise PackBuildError(
                f"cannot roll back non-directory installed target: {target}"
            )
        shutil.rmtree(target)
    if backup is not None:
        if not backup.is_dir() or backup.is_symlink():
            raise PackBuildError(f"cannot restore invalid pack backup: {backup}")
        backup.rename(target)


def finalize_version(backup: Path | None) -> None:
    if backup is not None:
        if not backup.is_dir() or backup.is_symlink():
            raise PackBuildError(f"cannot remove invalid pack backup: {backup}")
        shutil.rmtree(backup)


def build_pack(
    source_root: Path,
    inventory_path: Path,
    pack_root: Path,
    version: str = DEFAULT_VERSION,
    candidate_sha: str | None = None,
    check: bool = False,
) -> dict[str, object]:
    if VERSION_PATTERN.fullmatch(version) is None:
        raise PackBuildError(f"invalid immutable pack version: {version!r}")
    source_root = source_root.resolve(strict=True)
    inventory_path = inventory_path.resolve(strict=True)
    pack_root = pack_root.resolve()
    pack_root.mkdir(parents=True, exist_ok=True)
    validate_nojekyll(pack_root, create_missing=False if check else True)
    rows, metadata = load_inventory(inventory_path, source_root, candidate_sha)
    if int(version[1:]) >= 3:
        validate_alpha_mask_closure(rows, version)
    manifest = build_manifest(rows, metadata, version)
    stage_root = Path(tempfile.mkdtemp(prefix=".pack-build-", dir=pack_root))
    try:
        receipt = write_staged_pack(stage_root, rows, manifest, version)
        verification = run_independent_verifier(stage_root, inventory_path, version)
        if check:
            current = pack_root / version
            if not current.is_dir():
                raise PackBuildError(f"current pack version does not exist: {current}")
            run_independent_verifier(pack_root, inventory_path, version)
            staged_names, staged_sha = directory_contract(stage_root / version)
            current_names, current_sha = directory_contract(current)
            if staged_names != current_names or staged_sha != current_sha:
                raise PackBuildError(
                    "current pack is not a deterministic rebuild: "
                    f"staged={staged_sha} current={current_sha}"
                )
            action = "checked"
        else:
            backup = install_version(stage_root, pack_root, version)
            try:
                run_independent_verifier(
                    pack_root,
                    inventory_path,
                    version,
                    transactional_backup=backup is not None,
                )
            except Exception as verification_error:
                try:
                    rollback_version(pack_root, version, backup)
                except Exception as rollback_error:
                    raise PackBuildError(
                        "installed pack failed verification and rollback failed: "
                        f"verification={verification_error}; rollback={rollback_error}"
                    ) from verification_error
                raise
            finalize_version(backup)
            action = "built"
        return {
            "schema": SCHEMA,
            "status": "passed",
            "action": action,
            "version": version,
            "candidate_sha": metadata["candidate_sha"],
            "files": manifest["contract"]["files"],  # type: ignore[index]
            "bytes": manifest["contract"]["bytes"],  # type: ignore[index]
            "manifest_sha256": receipt["manifest"]["sha256"],  # type: ignore[index]
            "contract_sha256": manifest["contract_sha256"],
            "inventory_sha256": metadata["inventory_sha256"],
            "independent_verifier": verification["status"],
        }
    finally:
        if stage_root.exists():
            shutil.rmtree(stage_root)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument(
        "--pack-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--candidate-sha")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Rebuild in a temporary directory and require byte-identical output",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = build_pack(
            args.source_root,
            args.inventory,
            args.pack_root,
            version=args.version,
            candidate_sha=args.candidate_sha,
            check=args.check,
        )
    except Exception as exc:
        print(f"avatar pack build FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
