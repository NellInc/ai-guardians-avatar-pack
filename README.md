# AI Guardians Avatar Pack

This repository is the immutable public runtime-media backing store for AI Guardians motion portraits and speech-mouth overlays.

## Version v1

* Source candidate: `d9de35247fe41d74eebd75b7a5523f158b0788ba`
* Runtime media: 9,089 files, 271,610,332 bytes
* Media types: 8,415 WebP, 521 WebM, 153 PNG
* Source inventory SHA-256: `f2f1a5da3d58a7ede59219b0f7584c60b1f0d92a42e4032cdc88f44bff22693b`
* Source inventory contract SHA-256: `60fd5fa72e6d41c17f6760baf42afbed1c2dad7331b62605ee7e8671211e4b70`
* Runtime contract SHA-256: `1fc3399ca9a79a5fb9033ae9119269d6fe3e98fecaa11f5f27678b381c393b0b`
* Manifest SHA-256: `77fbe4e2fbffd6cc9447cca2743be13ab5e0d6f40e139b408c33a347b02e2822`

## Version v2

* Source candidate: `2bb803d978378aab79bc4b2f1690993fee313c82`
* Runtime media: 9,089 files, 243,131,943 bytes
* Media types: 8,415 WebP, 521 WebM, 153 PNG
* Source inventory SHA-256: `96d0466ddff27017c6f840efeaa18c98d4773ba8e62da6ece5ff4eb6414e0f3e`
* Runtime contract SHA-256: `82542ecf33b5754b4584732d6794df87c46afd0f6f0933eb40084f53224327c8`
* Manifest SHA-256: `7a62d4e446ca2276d1150f2f24a5049443921974a7684e24e7337f9065a7506d`

Version v2 preserves every v1 runtime path and replaces the 38 A.L.L.Y. oral
motion and thinking foreground overlays with deterministic VP9 Profile 0,
`yuv420p` encodes. This is the WebKit compatible successor to v1. Every
converted clip preserves its dimensions, frame rate, frame count, and duration.
The bitexact encode contract uses libvpx-vp9 CRF 12, one thread, stripped
metadata, and two byte-identical independent passes per file.

## Version v5

* Source candidate: `35883b11bbc49724a929cafbb3430df7fe617485`
* Runtime media: 17,504 files, 766,512,587 bytes
* Media types: 8,568 PNG, 521 WebM, 8,415 WebP
* Source inventory SHA-256: `b42ce863fc0590696ac46c99090797649add9d1c6a76c2e11f35dc1d13dcef60`
* Runtime contract SHA-256: `4abc138d87f6c3fb0e0b374e95cd69aa87975ed5fbc381be55952a8eae738ece`
* Manifest SHA-256: `6c251c082d517371986310056f95346b871a73ab238f6a49baf5b3c1627c6ebf`

Version v5 pairs every production mouth, blink, and semantic WebP layer with a
lossless, directly compositable RGBA PNG. The PNG carries the source color and
alpha channels exactly, avoiding WebKit's opaque WebP backing and any secondary
mask shader. Versions v3 and v4 remain immutable diagnostic predecessors.

## Version v7

* Source candidate: `8aa3b439c1534482baaa86861369e78a1517e884`
* Runtime media: 17,531 files, 771,343,169 bytes
* Media types: 8,568 PNG, 548 WebM, 8,415 WebP
* Source inventory SHA-256: `ba0107f00b310fbca526668d19a7d2e0687a97b93a0f1c39eab242d5c2df6630`
* Source inventory contract SHA-256: `0b36ec1a79969c060dfd8e56b4e05a20a5b95228cc1c4a3b46da51736d2fea8f`
* Runtime contract SHA-256: `8c26ab7569575801adef69b35be2c571c9ffecbd56ad5a4295f7558f9d0f54dc`
* Manifest SHA-256: `f7482f76c7a1f7f465fd2f03861f33a5e4210afdbf0182a895fa85657f079eeb`

Version v7 retains v5's direct RGBA WebKit compositor contract. It replaces
nine retired single-expression cast living portraits with the 36 accepted
four-expression successors used by the production registry. Version v6 remains
an immutable diagnostic predecessor.

## Version v8

* Source candidate: `a9b205e40c0c98845cf098d5361955b3df37cb94`
* Runtime media: 18,413 files, 779,449,383 bytes
* Media types: 9,009 PNG, 548 WebM, 8,856 WebP
* Source inventory SHA-256: `9565e7dd572885744449568a63e5839328e3e5fe95898f80fae03cbfaba5a017`
* Source inventory contract SHA-256: `960ab7cb667d30bb7472168661d2fdaebab6c91ce530ac088b4173eba79b5941`
* Runtime contract SHA-256: `d99fbc67c9320ab98314aede1367742ffe9e7aefcf7f9376dab3845d121a0524`
* Manifest SHA-256: `ecfefbc6ba90d8731bf31c3661bed612a363b7d281957b6abbb2516161689e12`

Version v8 replaces nine retired single-expression cast speech rigs with the
612 accepted four-expression versioned successor WebP layers used by the
production registry. Every successor layer has a lossless, directly
compositable RGBA PNG peer for WebKit. Version v8 preserves v7's accepted living
portrait successors, A.L.L.Y. transitions, and direct RGBA compositor contract.

Paths below `v1/` preserve their game-relative names. A runtime request for `images/chars/...` maps to `v1/images/chars/...`.

Each version becomes immutable when published. A changed byte requires a
coordinated new manifest/runtime contract, a new `vN` directory, and a shipped
runtime consumer pinned to that version. The tools reject malformed version
names and verify every requested version against its exact closure inventory.

## Scope

The pack contains only production runtime media: living-portrait WebM files, A.L.L.Y. directional portrait-transition WebM files, mouth and blink WebP assets, A.L.L.Y. mouth PNG assets, and A.L.L.Y. oral or hand-contact WebM layers. Source manifests and metadata remain bundled with the game. Comparison renders, contact sheets, lab-only media, and proof-of-concept media are excluded. The builder and verifier preserve an exact seven-path denylist for the source-resident Yuki review/transition/comparison assets and legacy A.L.L.Y. speech experiments that must never enter this pack.

## Integrity

`v1/manifest.json` lists every file's public path, game runtime path, byte size, SHA-256 digest, family, and media role. Its contract digest is SHA-256 over path-sorted UTF-8 rows encoded as `path\0size\0sha256\0media_role\n`, as documented in the manifest.

A sealed build also writes `v1/receipt.json`. The receipt exposes the raw
manifest SHA-256, the canonical contract SHA-256, the exact source candidate,
and the exact external-closure inventory identity. The receipt is metadata and
is not a runtime payload member.

## Deterministic build

The builder accepts only an explicit external-only P2 closure inventory. It
does not discover or copy a broad directory tree. The inventory has this exact
shape:

```json
{
  "schema": 1,
  "status": "p2_product_freeze",
  "candidate_sha": "<40 lowercase hex characters>",
  "files": [
    {
      "runtime_path": "images/chars/...",
      "size": 123,
      "sha256": "<64 lowercase hex characters>",
      "family": "cast_living",
      "media_role": "living_portrait"
    }
  ]
}
```

Rows must be in ascending UTF-8 runtime-path order. They contain external
payload members only. Static fallback files remain in the game and must not
enter this inventory.

Build a staged pack, independently verify it, and transactionally replace
`v1/`. Handled failures restore the previous version; an interrupted
transaction leaves a detectable backup and fails sealed verification:

```bash
python3 tools/build_pack.py \
  --source-root /absolute/path/to/Contents/Resources/autorun/game \
  --inventory /absolute/path/to/p2_external_closure.json \
  --candidate-sha <exact-p2-commit>
```

Prove that a second build is byte-identical without modifying the pack:

```bash
python3 tools/build_pack.py \
  --source-root /absolute/path/to/Contents/Resources/autorun/game \
  --inventory /absolute/path/to/p2_external_closure.json \
  --candidate-sha <exact-p2-commit> \
  --check
```

Run the independent verifier directly:

```bash
python3 tools/verify_pack.py \
  --pack-root . \
  --inventory /absolute/path/to/p2_external_closure.json
```

The verifier rejects missing or extra files, symlinks, Git LFS pointers, files
above the 50 MB pre-push ceiling, invalid media magic, path or case collisions,
review media, static fallbacks, aggregate drift, any byte or digest mismatch,
and an incomplete A.L.L.Y. transition, oral-motion, or foreground closure.

## Pages transport contract

`.nojekyll` keeps underscore-prefixed runtime paths directly addressable. Media
files remain uncompressed, ordinary repository files so HTTP byte ranges can be
served. The runtime requires the deployed origin to provide:

* `Access-Control-Allow-Origin: *` for every manifest and payload request.
* `Content-Type: video/webm`, `image/webp`, or `image/png` according to the
  manifest's extension contract.
* `206 Partial Content` and an exact `Content-Range` for WebM Range requests.
* Compatibility with a COEP `require-corp` game page through CORS.

These are hosted-response properties. They must be checked against the exact
deployed candidate after publication. A local build or Git object cannot prove
them.

## Rights

Copyright © 2026 Nell Watson. All rights reserved. These proprietary assets are published solely for AI Guardians runtime delivery. Publication does not grant reuse, redistribution, modification, or relicensing rights.
