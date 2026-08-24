#!/usr/bin/env python3
"""Independently verify an immutable AI Guardians avatar CDN pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath

SCHEMA = 1
STATUS = "immutable_production_runtime_asset_pack"
INVENTORY_STATUS = "p2_product_freeze"
VERSION_PATTERN = re.compile(r"v[1-9][0-9]*")
MAX_FILE_BYTES = 50_000_000
TOP_LEVEL_KEYS = frozenset(
    {
        "schema",
        "version",
        "status",
        "source",
        "license",
        "content_types",
        "extensions",
        "mime_types",
        "families",
        "media_roles",
        "contract",
        "contract_sha256",
        "files",
    }
)
ROW_KEYS = frozenset({"family", "media_role", "path", "runtime_path", "sha256", "size"})
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


class PackVerificationError(RuntimeError):
    """Pack bytes or metadata do not satisfy the sealed contract."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def exact_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise PackVerificationError(f"{label} is not an exact SHA-256")
    return value


def exact_candidate(value: object, label: str = "candidate_sha") -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise PackVerificationError(f"{label} is not an exact Git SHA")
    return value


def positive_size(value: object, label: str) -> int:
    if type(value) is not int:
        raise PackVerificationError(f"{label} is not an exact JSON integer")
    size = value
    if size <= 0 or size > MAX_FILE_BYTES:
        raise PackVerificationError(
            f"{label} is outside the allowed 1..50,000,000 byte range: {size}"
        )
    return size


def exact_nonnegative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise PackVerificationError(f"{label} is not an exact nonnegative JSON integer")
    return value


def exact_json_equal(observed: object, expected: object) -> bool:
    if type(observed) is not type(expected):
        return False
    if isinstance(expected, Mapping):
        return set(observed) == set(expected) and all(  # type: ignore[arg-type]
            exact_json_equal(observed[key], value)  # type: ignore[index]
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(observed) == len(expected) and all(  # type: ignore[arg-type]
            exact_json_equal(left, right)
            for left, right in zip(observed, expected, strict=True)  # type: ignore[arg-type]
        )
    return observed == expected


def role_path_matches(runtime_path: str, role: str) -> bool:
    return any(
        re.fullmatch(pattern, runtime_path) for pattern in ROLE_PATH_PATTERNS[role]
    )


def canonical_runtime_path(value: object, version: str) -> str:
    if not isinstance(value, str):
        raise PackVerificationError(f"runtime path is not a string: {value!r}")
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
        raise PackVerificationError(f"unsafe or noncanonical runtime path: {value!r}")
    parts = PurePosixPath(path).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise PackVerificationError(f"unsafe runtime path components: {path}")
    if path in FORBIDDEN_RUNTIME_PATHS:
        raise PackVerificationError(
            f"explicitly forbidden non-runtime avatar asset entered pack: {path}"
        )
    if not any(path == tree or path.startswith(tree + "/") for tree in ALLOWED_TREES):
        raise PackVerificationError(f"path is outside production avatar trees: {path}")
    lowered = "/" + path.casefold() + "/"
    if any(marker in lowered for marker in FORBIDDEN_MARKERS):
        raise PackVerificationError(f"review or experimental path entered pack: {path}")
    return path


def verify_magic(path: Path, extension: str) -> None:
    with path.open("rb") as handle:
        header = handle.read(64)
    if header.startswith(b"version https://git-lfs.github.com/spec/v1"):
        raise PackVerificationError(f"payload is a Git LFS pointer: {path}")
    valid = False
    if extension == ".png":
        valid = header.startswith(b"\x89PNG\r\n\x1a\n")
    elif extension == ".webm":
        valid = header.startswith(b"\x1aE\xdf\xa3")
    elif extension == ".webp":
        valid = len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    if not valid:
        raise PackVerificationError(f"payload magic does not match {extension}: {path}")


def add_aggregate(result: dict[str, dict[str, int]], key: str, size: int) -> None:
    row = result.setdefault(key, {"files": 0, "bytes": 0})
    row["files"] += 1
    row["bytes"] += size


def validate_alpha_mask_closure(
    rows: Sequence[Mapping[str, object]], version: str
) -> None:
    by_path = {str(row["runtime_path"]): row for row in rows}
    if version == "v5":
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
            raise PackVerificationError(
                f"{runtime_path} lacks its exact {mask_role}: {mask_path}"
            )
    observed_masks = {
        str(row["runtime_path"])
        for row in rows
        if str(row["media_role"]) in set(alpha_pairs.values())
    }
    if observed_masks != expected_masks:
        raise PackVerificationError(
            "alpha-mask closure drifted: "
            f"missing={sorted(expected_masks - observed_masks)} "
            f"extra={sorted(observed_masks - expected_masks)}"
        )


def validate_dependencies(rows: Sequence[Mapping[str, object]]) -> None:
    by_path = {str(row["runtime_path"]): row for row in rows}
    transitions = [row for row in rows if row["media_role"] == "portrait_transition"]
    expected_transition_paths = {
        f"images/chars/animated/transitions/{stem}.webm"
        for stem in EXPECTED_TRANSITION_STEMS
    }
    observed_transition_paths = {str(row["runtime_path"]) for row in transitions}
    if observed_transition_paths != expected_transition_paths:
        raise PackVerificationError(
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
        raise PackVerificationError(
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
        raise PackVerificationError(
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
        raise PackVerificationError(
            "A.L.L.Y. foreground closure drifted: "
            f"missing={sorted(expected_foreground_paths - observed_foreground_paths)} "
            f"extra={sorted(observed_foreground_paths - expected_foreground_paths)}"
        )

    def require(path: str, role: str, owner: str) -> None:
        dependency = by_path.get(path)
        if dependency is None or dependency.get("media_role") != role:
            raise PackVerificationError(
                f"{owner} lacks its exact {role} dependency: {path}"
            )

    for row in transitions:
        path = str(row["runtime_path"])
        match = TRANSITION_PATTERN.fullmatch(path)
        if match is None:
            raise PackVerificationError(
                f"portrait_transition is not an A.L.L.Y. transition: {path}"
            )
        stem = match.group(1)
        require(
            f"{ALLY_ORAL_ROOT}/{stem}_oral.webm",
            "oral_motion_patch",
            path,
        )
        if "ally_thinking_to_" in stem or "_to_thinking" in stem:
            require(
                f"{ALLY_FOREGROUND_ROOT}/{stem}_foreground.webm",
                "thinking_contact_foreground",
                path,
            )

    ally_living = [
        row for row in rows if str(row["runtime_path"]) in expected_living_paths
    ]
    for row in ally_living:
        path = str(row["runtime_path"])
        match = ALLY_LIVING_PATTERN.fullmatch(path)
        if match is None:
            raise PackVerificationError(f"invalid A.L.L.Y. living path: {path}")
        stem = match.group(1)
        require(
            f"{ALLY_ORAL_ROOT}/{stem}_oral.webm",
            "oral_motion_patch",
            path,
        )
        if stem == "ally_thinking_alive":
            require(
                f"{ALLY_FOREGROUND_ROOT}/{stem}_foreground.webm",
                "thinking_contact_foreground",
                path,
            )


def normalize_manifest_rows(
    manifest: Mapping[str, object], version_root: Path, version: str
) -> tuple[list[dict[str, object]], dict[str, dict[str, dict[str, int]]]]:
    raw_rows = manifest.get("files")
    if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
        raise PackVerificationError("manifest files is not a flat list")
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    folded: dict[str, str] = {}
    extensions: dict[str, dict[str, int]] = {}
    mimes: dict[str, dict[str, int]] = {}
    families: dict[str, dict[str, int]] = {}
    roles: dict[str, dict[str, int]] = {}
    for raw_row in raw_rows:
        if not isinstance(raw_row, Mapping) or set(raw_row) != ROW_KEYS:
            raise PackVerificationError(f"manifest row keys drifted: {raw_row!r}")
        runtime_path = canonical_runtime_path(raw_row["runtime_path"], version)
        public_path_value = raw_row["path"]
        if not isinstance(public_path_value, str):
            raise PackVerificationError(
                f"public path is not a string for {runtime_path}"
            )
        public_path = public_path_value
        if public_path != f"{version}/{runtime_path}":
            raise PackVerificationError(
                f"public/runtime path relation drifted: {public_path} {runtime_path}"
            )
        if runtime_path in seen:
            raise PackVerificationError(f"duplicate runtime path: {runtime_path}")
        casefolded = runtime_path.casefold()
        if casefolded in folded:
            raise PackVerificationError(
                f"casefold collision: {folded[casefolded]} and {runtime_path}"
            )
        seen.add(runtime_path)
        folded[casefolded] = runtime_path
        family_value = raw_row["family"]
        role_value = raw_row["media_role"]
        if not isinstance(family_value, str) or not isinstance(role_value, str):
            raise PackVerificationError(
                f"family/media role must be strings for {runtime_path}"
            )
        family = family_value
        role = role_value
        if not re.fullmatch(r"[a-z0-9_]+", family):
            raise PackVerificationError(
                f"invalid family for {runtime_path}: {family!r}"
            )
        if role == "static_source" or role not in ROLE_EXTENSIONS:
            raise PackVerificationError(
                f"invalid media role for {runtime_path}: {role!r}"
            )
        extension = PurePosixPath(runtime_path).suffix.lower()
        if extension not in CONTENT_TYPES or extension not in ROLE_EXTENSIONS[role]:
            raise PackVerificationError(
                f"extension/role mismatch for {runtime_path}: {extension} {role}"
            )
        if not role_path_matches(runtime_path, role):
            raise PackVerificationError(
                f"media role/path namespace mismatch for {runtime_path}: {role}"
            )
        size = positive_size(raw_row["size"], f"size for {runtime_path}")
        digest = exact_sha(raw_row["sha256"], f"SHA for {runtime_path}")
        payload_path = version_root.joinpath(*PurePosixPath(runtime_path).parts)
        cursor = version_root
        for part in PurePosixPath(runtime_path).parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise PackVerificationError(
                    f"pack payload is a symlink: {runtime_path}"
                )
        if not payload_path.is_file():
            raise PackVerificationError(f"pack payload is missing: {runtime_path}")
        observed_size = payload_path.stat().st_size
        observed_sha = sha256_file(payload_path)
        if observed_size != size or observed_sha != digest:
            raise PackVerificationError(
                f"pack payload drifted for {runtime_path}: "
                f"size {observed_size}/{size}, SHA {observed_sha}/{digest}"
            )
        verify_magic(payload_path, extension)
        row = {
            "family": family,
            "media_role": role,
            "path": public_path,
            "runtime_path": runtime_path,
            "sha256": digest,
            "size": size,
        }
        rows.append(row)
        add_aggregate(extensions, extension, size)
        add_aggregate(mimes, CONTENT_TYPES[extension], size)
        add_aggregate(families, family, size)
        add_aggregate(roles, role, size)
    ordered = sorted(rows, key=lambda row: str(row["path"]).encode("utf-8"))
    if rows != ordered:
        raise PackVerificationError(
            "manifest files are not in bytewise public-path order"
        )
    validate_dependencies(rows)
    return rows, {
        "extensions": dict(sorted(extensions.items())),
        "mime_types": dict(sorted(mimes.items())),
        "families": dict(sorted(families.items())),
        "media_roles": dict(sorted(roles.items())),
    }


def inventory_contract(rows: Sequence[Mapping[str, object]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(
            (
                f"{row['runtime_path']}\0{row['size']}\0{row['sha256']}\0"
                f"{row['family']}\0{row['media_role']}\n"
            ).encode("utf-8")
        )
    return digest.hexdigest()


def verify_inventory(
    inventory_path: Path,
    manifest: Mapping[str, object],
    manifest_rows: Sequence[Mapping[str, object]],
) -> None:
    raw = inventory_path.read_bytes()
    try:
        inventory = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackVerificationError("inventory is not valid UTF-8 JSON") from exc
    if not isinstance(inventory, Mapping):
        raise PackVerificationError("inventory root is not an object")
    if set(inventory) != {"schema", "status", "candidate_sha", "files"}:
        raise PackVerificationError("inventory root keys drifted")
    if (
        type(inventory.get("schema")) is not int
        or inventory.get("schema") != SCHEMA
        or inventory.get("status") != INVENTORY_STATUS
    ):
        raise PackVerificationError("inventory schema/status drifted")
    source = manifest["source"]
    if exact_candidate(inventory.get("candidate_sha")) != source["candidate_sha"]:  # type: ignore[index]
        raise PackVerificationError(
            "inventory candidate does not equal manifest source"
        )
    if sha256_bytes(raw) != source["inventory_sha256"]:  # type: ignore[index]
        raise PackVerificationError("inventory raw SHA does not equal manifest source")
    raw_rows = inventory.get("files")
    if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
        raise PackVerificationError("inventory files is not a list")
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    casefold_seen: dict[str, str] = {}
    version = str(manifest["version"])
    for row in raw_rows:
        if not isinstance(row, Mapping) or set(row) != INVENTORY_ROW_KEYS:
            raise PackVerificationError("inventory row keys drifted")
        runtime_path = canonical_runtime_path(row["runtime_path"], version)
        if runtime_path in seen:
            raise PackVerificationError(
                f"inventory duplicate runtime path: {runtime_path}"
            )
        folded = runtime_path.casefold()
        if folded in casefold_seen:
            raise PackVerificationError(
                "inventory casefold collision: "
                f"{casefold_seen[folded]} and {runtime_path}"
            )
        seen.add(runtime_path)
        casefold_seen[folded] = runtime_path
        family_value = row["family"]
        role_value = row["media_role"]
        if not isinstance(family_value, str) or not isinstance(role_value, str):
            raise PackVerificationError(
                f"inventory family/media role must be strings for {runtime_path}"
            )
        family = family_value
        role = role_value
        if not re.fullmatch(r"[a-z0-9_]+", family):
            raise PackVerificationError(
                f"inventory family is invalid for {runtime_path}"
            )
        extension = PurePosixPath(runtime_path).suffix.lower()
        if (
            role == "static_source"
            or role not in ROLE_EXTENSIONS
            or extension not in ROLE_EXTENSIONS[role]
        ):
            raise PackVerificationError(
                f"inventory media role is invalid for {runtime_path}: {role!r}"
            )
        if not role_path_matches(runtime_path, role):
            raise PackVerificationError(
                "inventory media role/path namespace mismatch for "
                f"{runtime_path}: {role}"
            )
        normalized.append(
            {
                "runtime_path": runtime_path,
                "size": positive_size(
                    row["size"], f"inventory size for {runtime_path}"
                ),
                "sha256": exact_sha(row["sha256"], f"inventory SHA for {runtime_path}"),
                "family": family,
                "media_role": role,
            }
        )
    if normalized != sorted(
        normalized, key=lambda row: str(row["runtime_path"]).encode("utf-8")
    ):
        raise PackVerificationError("inventory rows are not in bytewise path order")
    if inventory_contract(normalized) != source["inventory_contract_sha256"]:  # type: ignore[index]
        raise PackVerificationError("inventory normalized contract SHA drifted")
    manifest_projection = [
        {
            "runtime_path": row["runtime_path"],
            "size": row["size"],
            "sha256": row["sha256"],
            "family": row["family"],
            "media_role": row["media_role"],
        }
        for row in manifest_rows
    ]
    if normalized != manifest_projection:
        raise PackVerificationError("inventory and manifest exact membership disagree")


def verify_receipt(
    receipt_path: Path,
    manifest_raw: bytes,
    manifest: Mapping[str, object],
    version: str,
) -> dict[str, object]:
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackVerificationError("sealed receipt is missing or invalid") from exc
    expected_keys = {
        "schema",
        "status",
        "version",
        "candidate_sha",
        "manifest",
        "contract",
        "inventory",
    }
    if not isinstance(receipt, Mapping) or set(receipt) != expected_keys:
        raise PackVerificationError("sealed receipt keys drifted")
    if (
        type(receipt.get("schema")) is not int
        or receipt.get("schema") != SCHEMA
        or receipt.get("status") != "sealed_pack_receipt"
        or receipt.get("version") != version
        or exact_candidate(receipt.get("candidate_sha"), "receipt candidate")
        != manifest["source"]["candidate_sha"]  # type: ignore[index]
    ):
        raise PackVerificationError("sealed receipt authority drifted")
    expected_manifest = {
        "path": f"{version}/manifest.json",
        "bytes": len(manifest_raw),
        "sha256": sha256_bytes(manifest_raw),
    }
    expected_contract = {
        "files": manifest["contract"]["files"],  # type: ignore[index]
        "bytes": manifest["contract"]["bytes"],  # type: ignore[index]
        "sha256": manifest["contract_sha256"],
    }
    expected_inventory = {
        "sha256": manifest["source"]["inventory_sha256"],  # type: ignore[index]
        "contract_sha256": manifest["source"][  # type: ignore[index]
            "inventory_contract_sha256"
        ],
    }
    manifest_receipt = receipt.get("manifest")
    contract_receipt = receipt.get("contract")
    inventory_receipt = receipt.get("inventory")
    if not isinstance(manifest_receipt, Mapping) or set(manifest_receipt) != set(
        expected_manifest
    ):
        raise PackVerificationError("receipt raw manifest identity drifted")
    exact_nonnegative_int(manifest_receipt.get("bytes"), "receipt manifest bytes")
    exact_sha(manifest_receipt.get("sha256"), "receipt manifest SHA")
    if not exact_json_equal(manifest_receipt, expected_manifest):
        raise PackVerificationError("receipt raw manifest identity drifted")
    if not isinstance(contract_receipt, Mapping) or set(contract_receipt) != set(
        expected_contract
    ):
        raise PackVerificationError("receipt canonical contract identity drifted")
    exact_nonnegative_int(contract_receipt.get("files"), "receipt contract files")
    exact_nonnegative_int(contract_receipt.get("bytes"), "receipt contract bytes")
    exact_sha(contract_receipt.get("sha256"), "receipt contract SHA")
    if not exact_json_equal(contract_receipt, expected_contract):
        raise PackVerificationError("receipt canonical contract identity drifted")
    if not isinstance(inventory_receipt, Mapping) or set(inventory_receipt) != set(
        expected_inventory
    ):
        raise PackVerificationError("receipt inventory identity drifted")
    exact_sha(inventory_receipt.get("sha256"), "receipt inventory SHA")
    exact_sha(
        inventory_receipt.get("contract_sha256"),
        "receipt inventory contract SHA",
    )
    if not exact_json_equal(inventory_receipt, expected_inventory):
        raise PackVerificationError("receipt inventory identity drifted")
    return dict(receipt)


def verify_pack(
    pack_root: Path,
    version: str = "v1",
    inventory_path: Path | None = None,
    allow_transactional_backup: bool = False,
) -> dict[str, object]:
    pack_root = pack_root.resolve(strict=True)
    if VERSION_PATTERN.fullmatch(version) is None:
        raise PackVerificationError(f"invalid immutable pack version: {version!r}")
    stale_backup = pack_root / f".{version}.prebuild-backup"
    backup_present = stale_backup.exists() or stale_backup.is_symlink()
    if backup_present and not allow_transactional_backup:
        raise PackVerificationError(
            f"stale pack backup blocks sealed verification: {stale_backup}"
        )
    if allow_transactional_backup and (
        not stale_backup.is_dir() or stale_backup.is_symlink()
    ):
        raise PackVerificationError(
            "transactional verification requires the exact regular prebuild backup"
        )
    nojekyll = pack_root / ".nojekyll"
    if nojekyll.is_symlink() or not nojekyll.is_file() or nojekyll.stat().st_size != 0:
        raise PackVerificationError("Pages pack requires an empty .nojekyll")
    version_root = pack_root / version
    if not version_root.is_dir() or version_root.is_symlink():
        raise PackVerificationError(
            f"pack version directory is missing: {version_root}"
        )
    manifest_path = version_root / "manifest.json"
    manifest_raw = manifest_path.read_bytes()
    try:
        manifest = json.loads(manifest_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackVerificationError("manifest is not valid UTF-8 JSON") from exc
    if not isinstance(manifest, Mapping) or set(manifest) != TOP_LEVEL_KEYS:
        raise PackVerificationError(
            f"manifest top-level keys drifted: {sorted(manifest) if isinstance(manifest, Mapping) else type(manifest)}"
        )
    if (
        type(manifest.get("schema")) is not int
        or manifest.get("schema") != SCHEMA
        or manifest.get("version") != version
        or manifest.get("status") != STATUS
    ):
        raise PackVerificationError("manifest schema/version/status drifted")
    source = manifest.get("source")
    if not isinstance(source, Mapping) or set(source) != {
        "candidate_sha",
        "repository",
        "inventory_sha256",
        "inventory_contract_sha256",
    }:
        raise PackVerificationError("manifest source authority keys drifted")
    exact_candidate(source.get("candidate_sha"), "manifest source candidate")
    if source.get("repository") != "NellWatson/AI-Guardians":
        raise PackVerificationError("manifest source repository drifted")
    exact_sha(source.get("inventory_sha256"), "manifest inventory SHA")
    exact_sha(
        source.get("inventory_contract_sha256"),
        "manifest inventory contract SHA",
    )
    license_row = manifest.get("license")
    if not isinstance(license_row, Mapping) or set(license_row) != {
        "identifier",
        "holder",
        "notice",
    }:
        raise PackVerificationError("manifest license keys drifted")
    if (
        license_row.get("identifier") != "LicenseRef-Proprietary"
        or license_row.get("holder") != "Nell Watson"
    ):
        raise PackVerificationError("manifest proprietary license authority drifted")
    if not exact_json_equal(
        manifest.get("content_types"), dict(sorted(CONTENT_TYPES.items()))
    ):
        raise PackVerificationError("manifest content-type contract drifted")

    rows, aggregates = normalize_manifest_rows(manifest, version_root, version)
    if int(version[1:]) >= 3:
        validate_alpha_mask_closure(rows, version)
    for key, observed in aggregates.items():
        if not exact_json_equal(manifest.get(key), observed):
            raise PackVerificationError(f"manifest {key} aggregates drifted")
    contract = manifest.get("contract")
    if not isinstance(contract, Mapping) or set(contract) != {
        "files",
        "bytes",
        "ordering",
        "record_encoding",
        "sha256",
    }:
        raise PackVerificationError("manifest canonical contract keys drifted")
    digest = hashlib.sha256()
    for row in rows:
        digest.update(
            (
                f"{row['path']}\0{row['size']}\0{row['sha256']}\0{row['media_role']}\n"
            ).encode("utf-8")
        )
    contract_sha = digest.hexdigest()
    contract_files = exact_nonnegative_int(
        contract.get("files"), "manifest contract files"
    )
    contract_bytes = exact_nonnegative_int(
        contract.get("bytes"), "manifest contract bytes"
    )
    if (
        contract_files != len(rows)
        or contract_bytes != sum(int(row["size"]) for row in rows)
        or contract.get("ordering") != "ascending UTF-8 path order"
        or contract.get("record_encoding") != "path\\0size\\0sha256\\0media_role\\n"
        or exact_sha(contract.get("sha256"), "manifest contract SHA") != contract_sha
        or exact_sha(
            manifest.get("contract_sha256"),
            "manifest top-level contract SHA",
        )
        != contract_sha
    ):
        raise PackVerificationError("manifest canonical contract drifted")

    expected_files = {str(row["runtime_path"]) for row in rows} | {
        "manifest.json",
        "receipt.json",
    }
    actual_files: set[str] = set()
    for path in version_root.rglob("*"):
        if path.is_symlink():
            raise PackVerificationError(
                f"pack version contains a symlink: {path.relative_to(version_root)}"
            )
        if path.is_file():
            actual_files.add(path.relative_to(version_root).as_posix())
    if actual_files != expected_files:
        missing = sorted(expected_files - actual_files)
        extra = sorted(actual_files - expected_files)
        raise PackVerificationError(
            f"pack file closure drifted: missing={missing[:10]} extra={extra[:10]}"
        )
    receipt = verify_receipt(
        version_root / "receipt.json", manifest_raw, manifest, version
    )
    if inventory_path is None:
        raise PackVerificationError(
            "release verification requires the exact P2 closure inventory"
        )
    verify_inventory(inventory_path.resolve(strict=True), manifest, rows)
    return {
        "schema": SCHEMA,
        "status": (
            "passed_transactional_install" if allow_transactional_backup else "passed"
        ),
        "version": version,
        "candidate_sha": source["candidate_sha"],
        "files": len(rows),
        "bytes": sum(int(row["size"]) for row in rows),
        "manifest_sha256": sha256_bytes(manifest_raw),
        "contract_sha256": contract_sha,
        "inventory_sha256": source["inventory_sha256"],
        "transition_movies": sum(
            row["media_role"] == "portrait_transition" for row in rows
        ),
        "receipt": receipt,
        "content_types": manifest["content_types"],
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pack-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--version", default="v1")
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument(
        "--transactional-backup",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = verify_pack(
            args.pack_root,
            args.version,
            args.inventory,
            allow_transactional_backup=args.transactional_backup,
        )
    except Exception as exc:
        if args.json:
            print(
                json.dumps(
                    {"schema": SCHEMA, "status": "failed", "detail": str(exc)},
                    sort_keys=True,
                )
            )
        else:
            print(f"avatar pack verification FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=None if args.json else 2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
