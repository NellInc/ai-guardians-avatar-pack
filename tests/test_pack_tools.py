"""Focused contracts for deterministic immutable avatar-pack tooling."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_pack as builder  # noqa: E402
import verify_pack as verifier  # noqa: E402

TRANSITIONS = (
    "concerned_to_helpful",
    "concerned_to_neutral",
    "concerned_to_sad",
    "concerned_to_thinking",
    "happy_to_neutral",
    "happy_to_thinking",
    "helpful_to_concerned",
    "helpful_to_neutral",
    "helpful_to_thinking",
    "neutral_to_concerned",
    "neutral_to_happy",
    "neutral_to_helpful",
    "neutral_to_sad",
    "neutral_to_thinking",
    "sad_to_concerned",
    "sad_to_helpful",
    "sad_to_neutral",
    "sad_to_thinking",
    "thinking_to_concerned",
    "thinking_to_helpful",
    "thinking_to_neutral",
    "thinking_to_sad",
)
FORBIDDEN_RUNTIME_PATHS = {
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


def media_bytes(path: str) -> bytes:
    seed = hashlib.sha256(path.encode("utf-8")).digest()
    extension = Path(path).suffix.lower()
    if extension == ".webm":
        return b"\x1aE\xdf\xa3" + seed
    if extension == ".webp":
        return b"RIFF\x00\x00\x00\x00WEBP" + seed
    if extension == ".png":
        return b"\x89PNG\r\n\x1a\n" + seed
    raise AssertionError(extension)


def add_row(
    source_root: Path,
    rows: list[dict[str, object]],
    runtime_path: str,
    family: str,
    media_role: str,
) -> None:
    payload = media_bytes(runtime_path)
    path = source_root / runtime_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    rows.append(
        {
            "runtime_path": runtime_path,
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "family": family,
            "media_role": media_role,
        }
    )


def write_inventory(path: Path, rows: list[dict[str, object]]) -> None:
    rows.sort(key=lambda row: str(row["runtime_path"]).encode("utf-8"))
    payload = {
        "schema": 1,
        "status": "p2_product_freeze",
        "candidate_sha": "a" * 40,
        "files": rows,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def fixture_closure(tmp_path: Path) -> tuple[Path, Path, list[dict[str, object]]]:
    source_root = tmp_path / "game"
    source_root.mkdir(parents=True)
    rows: list[dict[str, object]] = []
    for transition in TRANSITIONS:
        stem = "ally_" + transition
        add_row(
            source_root,
            rows,
            f"images/chars/animated/transitions/{stem}.webm",
            "ally_transitions",
            "portrait_transition",
        )
        add_row(
            source_root,
            rows,
            f"{builder.ALLY_ORAL_ROOT}/{stem}_oral.webm",
            "ally_oral_motion",
            "oral_motion_patch",
        )
        if transition.startswith("thinking_to_") or transition.endswith("_to_thinking"):
            add_row(
                source_root,
                rows,
                f"{builder.ALLY_FOREGROUND_ROOT}/{stem}_foreground.webm",
                "ally_thinking_foreground",
                "thinking_contact_foreground",
            )
    for stem in builder.EXPECTED_ALLY_LIVING_STEMS:
        add_row(
            source_root,
            rows,
            f"images/chars/animated/{stem}.webm",
            "ally_living",
            "living_portrait",
        )
        add_row(
            source_root,
            rows,
            f"{builder.ALLY_ORAL_ROOT}/{stem}_oral.webm",
            "ally_oral_motion",
            "oral_motion_patch",
        )
        if stem == "ally_thinking_alive":
            add_row(
                source_root,
                rows,
                f"{builder.ALLY_FOREGROUND_ROOT}/{stem}_foreground.webm",
                "ally_thinking_foreground",
                "thinking_contact_foreground",
            )
    add_row(
        source_root,
        rows,
        "images/chars/_derived/cast_living_v1/alex/alex_normal_alive_v1.webm",
        "cast_living",
        "living_portrait",
    )
    add_row(
        source_root,
        rows,
        "images/chars/_derived/whiskr_speech_v1/warm/A.webp",
        "whiskr_speech",
        "mouth_atlas",
    )
    add_row(
        source_root,
        rows,
        "images/chars/_derived/whiskr_speech_v1/warm/A.alpha.webp",
        "whiskr_speech",
        "mouth_alpha_mask",
    )
    add_row(
        source_root,
        rows,
        "images/chars/_derived/ally_animation_lab/"
        "expression_oral_layers_runtime89_mouth_only_v1/mouth_bed_mask.png",
        "ally_mouth",
        "mouth_mask",
    )
    add_row(
        source_root,
        rows,
        "images/chars/_derived/cast_speech_v1/almiro/blink/weight_018.webp",
        "cast_speech",
        "blink_overlay",
    )
    add_row(
        source_root,
        rows,
        "images/chars/_derived/cast_speech_v1/almiro/blink/weight_018.alpha.webp",
        "cast_speech",
        "blink_alpha_mask",
    )
    add_row(
        source_root,
        rows,
        "images/chars/_derived/cast_speech_v1/atlas/pulse/almiro.webp",
        "cast_speech",
        "semantic_pulse",
    )
    add_row(
        source_root,
        rows,
        "images/chars/_derived/cast_speech_v1/atlas/pulse/almiro.alpha.webp",
        "cast_speech",
        "semantic_alpha_mask",
    )
    inventory = tmp_path / "closure.json"
    write_inventory(inventory, rows)
    return source_root, inventory, rows


def build_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    source_root, inventory, _rows = fixture_closure(tmp_path)
    pack_root = tmp_path / "pack"
    result = builder.build_pack(source_root, inventory, pack_root)
    assert result["status"] == "passed"
    return source_root, inventory, pack_root


def test_deterministic_build_and_independent_verifier(tmp_path: Path) -> None:
    source_root, inventory, rows = fixture_closure(tmp_path)
    pack_root = tmp_path / "pack"
    built = builder.build_pack(source_root, inventory, pack_root)
    assert built["action"] == "built"
    assert built["files"] == len(rows)
    assert built["independent_verifier"] == "passed"
    verified = verifier.verify_pack(pack_root, inventory_path=inventory)
    assert verified["status"] == "passed"
    assert verified["transition_movies"] == 22
    assert verified["manifest_sha256"] == built["manifest_sha256"]
    assert verified["contract_sha256"] == built["contract_sha256"]

    checked = builder.build_pack(source_root, inventory, pack_root, check=True)
    assert checked["action"] == "checked"
    assert checked["manifest_sha256"] == built["manifest_sha256"]

    manifest = json.loads((pack_root / "v1/manifest.json").read_text())
    assert manifest["content_types"] == {
        ".png": "image/png",
        ".webm": "video/webm",
        ".webp": "image/webp",
    }
    assert [row["path"] for row in manifest["files"]] == sorted(
        (row["path"] for row in manifest["files"]),
        key=lambda path: path.encode("utf-8"),
    )
    assert all(set(row) == builder.MANIFEST_ROW_KEYS for row in manifest["files"])
    receipt = json.loads((pack_root / "v1/receipt.json").read_text())
    assert receipt["manifest"]["sha256"] == built["manifest_sha256"]


def test_verifier_rejects_tampered_and_extra_payloads(tmp_path: Path) -> None:
    _source_root, inventory, pack_root = build_fixture(tmp_path)
    manifest = json.loads((pack_root / "v1/manifest.json").read_text())
    first = pack_root / manifest["files"][0]["path"]
    first.write_bytes(first.read_bytes() + b"tamper")
    with pytest.raises(verifier.PackVerificationError, match="payload drifted"):
        verifier.verify_pack(pack_root, inventory_path=inventory)

    shutil_root = tmp_path / "second"
    _source_root, inventory, pack_root = build_fixture(shutil_root)
    extra = pack_root / "v1/images/chars/animated/unlisted.webm"
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_bytes(media_bytes(extra.as_posix()))
    with pytest.raises(verifier.PackVerificationError, match="file closure drifted"):
        verifier.verify_pack(pack_root, inventory_path=inventory)


def test_builder_rejects_missing_dependency_and_experiment(tmp_path: Path) -> None:
    assert builder.FORBIDDEN_RUNTIME_PATHS == FORBIDDEN_RUNTIME_PATHS
    assert verifier.FORBIDDEN_RUNTIME_PATHS == FORBIDDEN_RUNTIME_PATHS
    source_root, inventory, rows = fixture_closure(tmp_path)
    missing = next(
        index
        for index, row in enumerate(rows)
        if str(row["runtime_path"]).endswith("ally_concerned_to_helpful_oral.webm")
    )
    rows.pop(missing)
    write_inventory(inventory, rows)
    with pytest.raises(builder.PackBuildError, match="oral-motion closure drifted"):
        builder.build_pack(source_root, inventory, tmp_path / "pack")

    masks = tmp_path / "missing-alpha-mask"
    source_root, inventory, rows = fixture_closure(masks)
    rows[:] = [
        row
        for row in rows
        if row["media_role"] != "mouth_alpha_mask"
    ]
    write_inventory(inventory, rows)
    with pytest.raises(builder.PackBuildError, match="lacks its exact mouth_alpha_mask"):
        builder.build_pack(source_root, inventory, masks / "pack", version="v3")

    second = tmp_path / "experiment"
    source_root, inventory, rows = fixture_closure(second)
    add_row(
        source_root,
        rows,
        "images/chars/animated/ally_speech_poc.webm",
        "ally_living",
        "living_portrait",
    )
    write_inventory(inventory, rows)
    with pytest.raises(builder.PackBuildError, match="review or experimental"):
        builder.build_pack(source_root, inventory, second / "pack")

    third = tmp_path / "static-role-lie"
    source_root, inventory, rows = fixture_closure(third)
    add_row(
        source_root,
        rows,
        "images/chars/animated/static_fallback.png",
        "ally_mouth",
        "mouth_sprite",
    )
    write_inventory(inventory, rows)
    with pytest.raises(builder.PackBuildError, match="role/path namespace mismatch"):
        builder.build_pack(source_root, inventory, third / "pack")

    fourth = tmp_path / "forbidden-yuki-transition"
    source_root, inventory, rows = fixture_closure(fourth)
    add_row(
        source_root,
        rows,
        "images/chars/_derived/yuki_video_avatar_pilot_v1/transitions/"
        "yuki_normal_to_concerned_v1.webm",
        "yuki_transitions",
        "portrait_transition",
    )
    write_inventory(inventory, rows)
    with pytest.raises(builder.PackBuildError, match="explicitly forbidden"):
        builder.build_pack(source_root, inventory, fourth / "pack")


def test_builder_pins_candidate_inventory_and_source_bytes(tmp_path: Path) -> None:
    source_root, inventory, rows = fixture_closure(tmp_path)
    with pytest.raises(builder.PackBuildError, match="CLI candidate SHA"):
        builder.build_pack(
            source_root,
            inventory,
            tmp_path / "pack",
            candidate_sha="b" * 40,
        )
    target = source_root / str(rows[0]["runtime_path"])
    target.write_bytes(target.read_bytes() + b"changed")
    with pytest.raises(builder.PackBuildError, match="frozen source drifted"):
        builder.build_pack(source_root, inventory, tmp_path / "pack")


def test_inventory_scalar_types_and_lowercase_hashes_are_exact(tmp_path: Path) -> None:
    source_root, inventory, rows = fixture_closure(tmp_path)
    payload = json.loads(inventory.read_text())
    payload["candidate_sha"] = ("a" * 40).upper()
    inventory.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    with pytest.raises(builder.PackBuildError, match="exact Git SHA"):
        builder.build_pack(source_root, inventory, tmp_path / "pack")
    with pytest.raises(verifier.PackVerificationError, match="exact Git SHA"):
        verifier.exact_candidate("A" * 40)

    second = tmp_path / "string-size"
    source_root, inventory, rows = fixture_closure(second)
    payload = json.loads(inventory.read_text())
    payload["files"][0]["size"] = str(payload["files"][0]["size"])
    inventory.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    with pytest.raises(builder.PackBuildError, match="exact JSON integer"):
        builder.build_pack(source_root, inventory, second / "pack")
    with pytest.raises(verifier.PackVerificationError, match="exact JSON integer"):
        verifier.positive_size("36", "fixture size")

    third = tmp_path / "boolean-schema"
    source_root, inventory, _rows = fixture_closure(third)
    payload = json.loads(inventory.read_text())
    payload["schema"] = True
    inventory.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    with pytest.raises(builder.PackBuildError, match="schema/status drifted"):
        builder.build_pack(source_root, inventory, third / "pack")


def test_check_rejects_identical_payload_symlink(tmp_path: Path) -> None:
    source_root, inventory, pack_root = build_fixture(tmp_path)
    manifest = json.loads((pack_root / "v1/manifest.json").read_text())
    payload = pack_root / manifest["files"][0]["path"]
    identical = tmp_path / "identical-payload"
    identical.write_bytes(payload.read_bytes())
    payload.unlink()
    payload.symlink_to(identical)

    with pytest.raises(builder.PackBuildError, match="symlink"):
        builder.build_pack(source_root, inventory, pack_root, check=True)


def test_versioned_successor_and_nojekyll_symlink_contract(
    tmp_path: Path,
) -> None:
    source_root, inventory, pack_root = build_fixture(tmp_path)
    successor = builder.build_pack(
        source_root, inventory, pack_root, version="v2"
    )
    assert successor["version"] == "v2"
    assert verifier.verify_pack(
        pack_root, version="v2", inventory_path=inventory
    )["status"] == "passed"
    for invalid in ("v0", "v01", "V2", "v2/escape"):
        with pytest.raises(builder.PackBuildError, match="invalid immutable pack version"):
            builder.build_pack(source_root, inventory, pack_root, version=invalid)
        with pytest.raises(
            verifier.PackVerificationError, match="invalid immutable pack version"
        ):
            verifier.verify_pack(pack_root, version=invalid, inventory_path=inventory)

    nojekyll_target = tmp_path / "empty-file"
    nojekyll_target.touch()
    (pack_root / ".nojekyll").unlink()
    (pack_root / ".nojekyll").symlink_to(nojekyll_target)
    with pytest.raises(verifier.PackVerificationError, match="empty .nojekyll"):
        verifier.verify_pack(pack_root, inventory_path=inventory)

    (pack_root / ".nojekyll").unlink()
    (pack_root / ".nojekyll").touch()
    (pack_root / ".v1.prebuild-backup").mkdir()
    with pytest.raises(verifier.PackVerificationError, match="stale pack backup"):
        verifier.verify_pack(pack_root, inventory_path=inventory)


def test_verifier_rejects_json_numeric_equivalence_and_requires_inventory(
    tmp_path: Path,
) -> None:
    _source_root, inventory, pack_root = build_fixture(tmp_path)
    manifest_path = pack_root / "v1/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["schema"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    with pytest.raises(verifier.PackVerificationError, match="schema/version/status"):
        verifier.verify_pack(pack_root, inventory_path=inventory)

    second = tmp_path / "float-contract"
    _source_root, inventory, pack_root = build_fixture(second)
    manifest_path = pack_root / "v1/manifest.json"
    receipt_path = pack_root / "v1/receipt.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["contract"]["files"] = float(manifest["contract"]["files"])
    manifest_raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    manifest_path.write_bytes(manifest_raw)
    receipt = json.loads(receipt_path.read_text())
    receipt["manifest"]["bytes"] = len(manifest_raw)
    receipt["manifest"]["sha256"] = hashlib.sha256(manifest_raw).hexdigest()
    receipt["contract"]["files"] = float(receipt["contract"]["files"])
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    with pytest.raises(verifier.PackVerificationError, match="contract files"):
        verifier.verify_pack(pack_root, inventory_path=inventory)

    third = tmp_path / "no-inventory"
    _source_root, inventory, pack_root = build_fixture(third)
    with pytest.raises(verifier.PackVerificationError, match="requires.*inventory"):
        verifier.verify_pack(pack_root)


def test_invalid_nojekyll_cannot_replace_existing_version(tmp_path: Path) -> None:
    source_root, inventory, pack_root = build_fixture(tmp_path)
    before = builder.directory_contract(pack_root / "v1")
    (pack_root / ".nojekyll").write_text("invalid\n")

    with pytest.raises(builder.PackBuildError, match="empty regular .nojekyll"):
        builder.build_pack(source_root, inventory, pack_root)

    assert builder.directory_contract(pack_root / "v1") == before
    assert not (pack_root / ".v1.prebuild-backup").exists()


def test_failed_post_install_verification_restores_previous_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_root, inventory, pack_root = build_fixture(tmp_path)
    old_manifest = (pack_root / "v1/manifest.json").read_bytes()
    old_pack = json.loads(old_manifest)
    changed_row = next(
        row
        for row in json.loads(inventory.read_text())["files"]
        if row["runtime_path"].endswith("alex_normal_alive_v1.webm")
    )
    packed_path = pack_root / "v1" / changed_row["runtime_path"]
    old_payload = packed_path.read_bytes()

    source_path = source_root / changed_row["runtime_path"]
    new_payload = source_path.read_bytes() + b"changed"
    source_path.write_bytes(new_payload)
    inventory_payload = json.loads(inventory.read_text())
    inventory_row = next(
        row
        for row in inventory_payload["files"]
        if row["runtime_path"] == changed_row["runtime_path"]
    )
    inventory_row["size"] = len(new_payload)
    inventory_row["sha256"] = hashlib.sha256(new_payload).hexdigest()
    inventory.write_text(json.dumps(inventory_payload, indent=2, sort_keys=True) + "\n")

    original_verify = builder.run_independent_verifier

    def fail_installed_verification(
        root: Path,
        inventory_path: Path,
        version: str,
        transactional_backup: bool = False,
    ) -> dict[str, object]:
        if root.resolve() == pack_root.resolve():
            raise builder.PackBuildError("synthetic post-install failure")
        return original_verify(
            root,
            inventory_path,
            version,
            transactional_backup=transactional_backup,
        )

    monkeypatch.setattr(
        builder, "run_independent_verifier", fail_installed_verification
    )
    with pytest.raises(builder.PackBuildError, match="synthetic post-install failure"):
        builder.build_pack(source_root, inventory, pack_root)

    assert (pack_root / "v1/manifest.json").read_bytes() == old_manifest
    assert packed_path.read_bytes() == old_payload
    assert not (pack_root / ".v1.prebuild-backup").exists()
    assert old_pack["contract_sha256"] == json.loads(old_manifest)["contract_sha256"]


def test_successful_replacement_verifies_before_backup_removal(tmp_path: Path) -> None:
    source_root, inventory, pack_root = build_fixture(tmp_path)
    inventory_payload = json.loads(inventory.read_text())
    changed_row = next(
        row
        for row in inventory_payload["files"]
        if row["runtime_path"].endswith("alex_normal_alive_v1.webm")
    )
    packed_path = pack_root / "v1" / changed_row["runtime_path"]
    old_payload = packed_path.read_bytes()
    source_path = source_root / changed_row["runtime_path"]
    new_payload = source_path.read_bytes() + b"replacement"
    source_path.write_bytes(new_payload)
    changed_row["size"] = len(new_payload)
    changed_row["sha256"] = hashlib.sha256(new_payload).hexdigest()
    inventory.write_text(json.dumps(inventory_payload, indent=2, sort_keys=True) + "\n")

    result = builder.build_pack(source_root, inventory, pack_root)

    assert result["status"] == "passed"
    assert packed_path.read_bytes() == new_payload
    assert packed_path.read_bytes() != old_payload
    assert not (pack_root / ".v1.prebuild-backup").exists()
    assert (
        verifier.verify_pack(pack_root, inventory_path=inventory)["status"] == "passed"
    )


def test_verifier_is_an_independent_implementation() -> None:
    source = (TOOLS / "verify_pack.py").read_text()
    assert "import build_pack" not in source
    assert "from build_pack" not in source
    assert "EXPECTED_TRANSITION_STEMS" in source
    assert "ally_thinking_to_sad" in source
