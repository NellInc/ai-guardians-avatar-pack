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
DIRECT_RGBA_PILLOW_VERSION = "12.0.0"
V9_SEED_VERSION = "v8"
V9_SEED_MANIFEST_SHA256 = (
    "ecfefbc6ba90d8731bf31c3661bed612a363b7d281957b6abbb2516161689e12"
)
V9_SEED_CONTRACT_SHA256 = (
    "d99fbc67c9320ab98314aede1367742ffe9e7aefcf7f9376dab3845d121a0524"
)
V9_SEED_SOURCE = {
    "candidate_sha": "a9b205e40c0c98845cf098d5361955b3df37cb94",
    "inventory_contract_sha256": (
        "960ab7cb667d30bb7472168661d2fdaebab6c91ce530ac088b4173eba79b5941"
    ),
    "inventory_sha256": (
        "9565e7dd572885744449568a63e5839328e3e5fe95898f80fae03cbfaba5a017"
    ),
    "repository": "NellWatson/AI-Guardians",
}
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
        r"images/chars/_derived/cast_speech_successors_v1/[a-z0-9_]+/"
        r"v[1-9][0-9]*/blink/[a-z0-9_]+/weight_[0-9]{3}\.webp",
    ),
    "blink_rgba_layer": (
        r"images/chars/_derived/cast_speech_v1/almiro/"
        r"blink/weight_[0-9]{3}\.rgba\.png",
        r"images/chars/_derived/cast_speech_v1/[a-z0-9_]+/"
        r"blink/[a-z0-9_]+/weight_[0-9]{3}\.rgba\.png",
        r"images/chars/_derived/cast_speech_successors_v1/[a-z0-9_]+/"
        r"v[1-9][0-9]*/blink/[a-z0-9_]+/weight_[0-9]{3}\.rgba\.png",
    ),
    "living_portrait": (
        r"images/chars/_derived/cast_living_v1/(?P<rig>[a-z0-9_]+)/"
        r"(?P=rig)_[a-z0-9_]+_alive_v1\.webm",
        r"images/chars/_derived/cast_living_successors_v1/"
        r"expression_expansion_v2/(?P<successor_rig>[a-z0-9_]+)/"
        r"(?P=successor_rig)_[a-z0-9_]+_alive_v1\.webm",
        (
            r"images/chars/_derived/cast_living_successors_v1/audience/v2/audience/"
            r"audience_[a-z0-9_]+_alive_v1\.webm"
        ),
        (
            r"images/chars/_derived/cast_living_successors_v1/zach/v2/zach/"
            r"zach_[a-z0-9_]+_alive_v1\.webm"
        ),
        r"images/chars/_derived/whiskr_speech_v1/living/"
        r"whiskr_[a-z0-9_]+_alive_v1\.webm",
        r"images/chars/_derived/yuki_video_avatar_pilot_v1/"
        r"yuki_[a-z0-9_]+_alive_v1\.webm",
        r"images/chars/animated/ally_[a-z0-9_]+_alive\.webm",
    ),
    "mouth_atlas": (
        r"images/chars/_derived/cast_speech_v1/[a-z0-9_]+/"
        r"atlases/[a-z0-9_]+/[A-Za-z0-9_]+\.webp",
        r"images/chars/_derived/cast_speech_successors_v1/[a-z0-9_]+/"
        r"v[1-9][0-9]*/atlases/[a-z0-9_]+/[A-Za-z0-9_]+\.webp",
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
        r"images/chars/_derived/cast_speech_successors_v1/[a-z0-9_]+/"
        r"v[1-9][0-9]*/atlases/[a-z0-9_]+/[A-Za-z0-9_]+\.rgba\.png",
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
    "images/chars/_derived/cast_living_successors_v1/audience/v2/audience",
    "images/chars/_derived/cast_living_successors_v1/zach/v2/zach",
    "images/chars/_derived/cast_speech_v1",
    "images/chars/_derived/cast_speech_successors_v1",
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


def derive_direct_rgba_peer(
    source_root: Path, runtime_path: str, derived_root: Path
) -> Path:
    """Reproduce an inventory-bound direct RGBA PNG from its source WebP."""
    if not runtime_path.endswith(".rgba.png"):
        raise PackBuildError(f"payload is not a direct RGBA peer: {runtime_path}")
    webp_runtime_path = runtime_path.removesuffix(".rgba.png") + ".webp"
    webp_source = ensure_regular_source(source_root, webp_runtime_path)
    try:
        import PIL
        from PIL import Image
    except ImportError as exc:
        raise PackBuildError(
            "missing Pillow required to reproduce direct RGBA peers"
        ) from exc
    if PIL.__version__ != DIRECT_RGBA_PILLOW_VERSION:
        raise PackBuildError(
            "direct RGBA reproduction requires Pillow "
            f"{DIRECT_RGBA_PILLOW_VERSION}, found {PIL.__version__}"
        )
    destination = derived_root.joinpath(*PurePosixPath(runtime_path).parts)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(webp_source) as image:
            with image.convert("RGBA") as rgba:
                rgba.save(destination, format="PNG", optimize=True)
    except Exception as exc:
        raise PackBuildError(
            f"failed to reproduce direct RGBA peer for {runtime_path}: {exc}"
        ) from exc
    return destination


def load_v9_seed_manifest(
    seed_manifest_path: Path, seed_root: Path
) -> tuple[dict[str, dict[str, object]], dict[str, str]]:
    """Load and verify the exact published v8 payload authority for v9 reuse."""
    raw = seed_manifest_path.read_bytes()
    observed_manifest_sha = sha256_bytes(raw)
    if observed_manifest_sha != V9_SEED_MANIFEST_SHA256:
        raise PackBuildError(
            "v9 seed manifest is not the verified live v8 authority: "
            f"{observed_manifest_sha}"
        )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackBuildError("v9 seed manifest is not valid UTF-8 JSON") from exc
    if not isinstance(payload, Mapping):
        raise PackBuildError("v9 seed manifest root is not an object")
    if (
        type(payload.get("schema")) is not int
        or payload.get("schema") != SCHEMA
        or payload.get("status") != STATUS
        or payload.get("version") != V9_SEED_VERSION
        or payload.get("contract_sha256") != V9_SEED_CONTRACT_SHA256
        or payload.get("source") != V9_SEED_SOURCE
    ):
        raise PackBuildError("v9 seed manifest authority drifted")
    raw_rows = payload.get("files")
    if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
        raise PackBuildError("v9 seed manifest files is not a flat list")

    rows: dict[str, dict[str, object]] = {}
    public_paths: list[str] = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, Mapping) or set(raw_row) != MANIFEST_ROW_KEYS:
            raise PackBuildError(f"v9 seed manifest row keys drifted: {raw_row!r}")
        runtime_path = normalize_runtime_path(raw_row["runtime_path"])
        public_path = raw_row["path"]
        if public_path != f"{V9_SEED_VERSION}/{runtime_path}":
            raise PackBuildError(
                f"v9 seed public/runtime path drifted for {runtime_path}"
            )
        if runtime_path in rows:
            raise PackBuildError(f"duplicate v9 seed runtime path: {runtime_path}")
        family, role = validate_media_contract(
            runtime_path, raw_row["family"], raw_row["media_role"]
        )
        size = parse_positive_int(raw_row["size"], f"v9 seed size for {runtime_path}")
        digest = require_sha256(raw_row["sha256"], f"v9 seed SHA for {runtime_path}")
        source = ensure_regular_source(seed_root, runtime_path)
        observed_size = source.stat().st_size
        observed_sha = sha256_file(source)
        if observed_size != size or observed_sha != digest:
            raise PackBuildError(
                f"verified v8 seed bytes drifted for {runtime_path}: "
                f"size {observed_size}/{size}, SHA {observed_sha}/{digest}"
            )
        verify_file_magic(source, PurePosixPath(runtime_path).suffix.lower())
        rows[runtime_path] = {
            "runtime_path": runtime_path,
            "size": size,
            "sha256": digest,
            "family": family,
            "media_role": role,
            "_source": source,
        }
        public_paths.append(str(public_path))
    if public_paths != sorted(public_paths, key=lambda path: path.encode("utf-8")):
        raise PackBuildError("v9 seed manifest rows are not in bytewise path order")
    return rows, {
        "version": V9_SEED_VERSION,
        "manifest_sha256": V9_SEED_MANIFEST_SHA256,
        "contract_sha256": V9_SEED_CONTRACT_SHA256,
    }


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
    inventory_path: Path,
    source_root: Path,
    candidate_sha: str | None,
    seed_rows: Mapping[str, Mapping[str, object]] | None = None,
    derived_root: Path | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
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
    seeded_files = 0
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
        seed = seed_rows.get(runtime_path) if seed_rows is not None else None
        if seed is not None and all(
            seed.get(key) == value
            for key, value in {
                "runtime_path": runtime_path,
                "size": size,
                "sha256": digest,
                "family": family,
                "media_role": role,
            }.items()
        ):
            source = Path(str(seed["_source"]))
            seeded_files += 1
        else:
            try:
                source = ensure_regular_source(source_root, runtime_path)
            except PackBuildError as exc:
                if (
                    role
                    not in {
                        "blink_rgba_layer",
                        "mouth_rgba_layer",
                        "semantic_rgba_layer",
                    }
                    or derived_root is None
                ):
                    raise
                if not isinstance(exc.__cause__, FileNotFoundError):
                    raise
                source = derive_direct_rgba_peer(
                    source_root, runtime_path, derived_root
                )
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
        "seeded_files": seeded_files,
        "overlay_files": len(ordered) - seeded_files,
    }


def validate_alpha_mask_closure(
    rows: Sequence[Mapping[str, object]], version: str
) -> None:
    by_path = {str(row["runtime_path"]): row for row in rows}
    if version in {"v5", "v7", "v8", "v9"}:
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
    metadata: Mapping[str, object],
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
    source_authority: dict[str, object] = {
        "candidate_sha": metadata["candidate_sha"],
        "repository": "NellWatson/AI-Guardians",
        "inventory_sha256": metadata["inventory_sha256"],
        "inventory_contract_sha256": metadata["inventory_contract_sha256"],
    }
    if version == "v9":
        source_authority["predecessor_seed"] = metadata["predecessor_seed"]
    return {
        "schema": SCHEMA,
        "version": version,
        "status": STATUS,
        "source": source_authority,
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
    seed_manifest_path: Path | None = None,
    seed_root: Path | None = None,
) -> dict[str, object]:
    if VERSION_PATTERN.fullmatch(version) is None:
        raise PackBuildError(f"invalid immutable pack version: {version!r}")
    source_root = source_root.resolve(strict=True)
    inventory_path = inventory_path.resolve(strict=True)
    seed_rows: Mapping[str, Mapping[str, object]] | None = None
    seed_authority: Mapping[str, str] | None = None
    if version == "v9":
        if seed_manifest_path is None or seed_root is None:
            raise PackBuildError(
                "v9 requires the exact live v8 --seed-manifest and --seed-root"
            )
        if seed_manifest_path.is_symlink():
            raise PackBuildError("v9 seed manifest must not be a symlink")
        if seed_root.is_symlink():
            raise PackBuildError("v9 seed root must not be a symlink")
        resolved_seed_root = seed_root.resolve(strict=True)
        if not resolved_seed_root.is_dir():
            raise PackBuildError("v9 seed root is not a directory")
        seed_rows, seed_authority = load_v9_seed_manifest(
            seed_manifest_path.resolve(strict=True), resolved_seed_root
        )
    elif seed_manifest_path is not None or seed_root is not None:
        raise PackBuildError("predecessor seeding is reserved for immutable v9")
    pack_root = pack_root.resolve()
    pack_root.mkdir(parents=True, exist_ok=True)
    validate_nojekyll(pack_root, create_missing=False if check else True)
    derived_root = Path(tempfile.mkdtemp(prefix=".pack-derived-", dir=pack_root))
    try:
        rows, metadata = load_inventory(
            inventory_path,
            source_root,
            candidate_sha,
            seed_rows=seed_rows,
            derived_root=derived_root,
        )
        if seed_authority is not None:
            metadata["predecessor_seed"] = dict(seed_authority)
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
                    raise PackBuildError(
                        f"current pack version does not exist: {current}"
                    )
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
                            f"verification={verification_error}; "
                            f"rollback={rollback_error}"
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
    finally:
        if derived_root.exists():
            shutil.rmtree(derived_root)


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
        "--seed-manifest",
        type=Path,
        help="Exact published v8 manifest required when building immutable v9",
    )
    parser.add_argument(
        "--seed-root",
        type=Path,
        help="Verified local v8 payload root required when building immutable v9",
    )
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
            seed_manifest_path=args.seed_manifest,
            seed_root=args.seed_root,
        )
    except Exception as exc:
        print(f"avatar pack build FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
