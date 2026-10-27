# OneLook Thesaurus — standalone Rust development port

One own `search` view command, canonical ID `com.tezbar.native.onelook-thesaurus`.
Schema 3, external executable, protocol 1, SDK 0.1.1, Rust MSRV 1.85. The SDK is an
immutable HTTPS Git dependency at `e955911f0bf5b558f9d3eb5183df0adc95c22af2`;
there is no sibling path dependency, Node/Bun/JavaScript engine or Tauri adapter.
The source manifest retains `artifacts: {}` and both OS verification entries as
`not-run`. Nothing in this directory installs, publishes, changes the catalog,
activates a root workflow or claims clean-profile GUI acceptance.

## Source contract

The authoritative own source is `src/search.tsx`, package and unchanged lock at
`3557a2ccd50cd3b4c3153afed9e4ec8c78106782`. It locks `@raycast/api` 1.104.25 and
`@raycast/utils` 2.3.0. That command:

- Starts with an empty query and no request; every nonempty query revalidates.
- Requests `https://api.datamuse.com/words?qe=ml&md=d&ml=` plus the query with only
  ASCII spaces replaced by `+`. This deliberately preserves source behavior for
  literal `+`, `&`, `%`, `#`, tabs, Unicode, descriptions and patterns. It does
  **not** substitute form/component encoding or invent additional API routes.
- Keeps service order and duplicates. It shows `word`, the nonempty first `defs`
  entry as subtitle, and `# <word>\n---\n<definitions>` as detail markdown.
  Only the first ASCII `/(\w+)\t/` match in each definition becomes inline code.
- Provides “Toggle Definitions,” initially hidden. There are no source dropdowns,
  account settings, local ranking, history, copy, paste, external browser actions,
  selection reads, or visibility calls. The port requests no host capabilities.

The locked utils implementation caches by raw request URL/options, revalidates
nonempty inputs, shows same-key cached data on failure, and does not use another
query's results by default. The port uses a dedicated full-raw-URL cache with the
fixed route/options in the key. There is no account in this source. Cache eviction
is at eight complete entries / 2 MiB, persisted in the extension-private host data
path `datamuse-cache-v1.json`. Corrupt/oversized cache files are left untouched;
the view reports memory-only operation. It never imports a profile or V1 store.

The original icon is copied byte for byte from both the own asset and
Raycast/extensions at `6734d85992290066fd31a7f5bee3cca3d3545a1a`, path
`extensions/onelook-thesaurus/assets/command-icon.png`.
SHA-256: `0723e3c35808ff5ff0aff5fe2dc81db4c4615b013e02d7b35406b29bb096d032`
(141,818 bytes). No image generation, conversion or recompression occurs.

## Ownership, actions and bounds

Every search synchronously records its query/revision and revokes old action IDs
before its first await. The SDK reader supersedes prior searches in dispatch
order, including queued searches. The adapter uses an authoritative bounded
registry outside the SDK's transactional `Value`; canceled opens have drop
cleanup and cancellation-witness pruning. At most 128 sessions exist. A/B/A,
invalid intermediate drafts, pending requests, disposal and cross-session actions
are exercised with actual SDK pipes. No port-owned detached tasks, polling timers,
background actors, leases or process-wide UI effects are used.

Toggle/retry IDs are removed outside staged state before awaiting anything. Fresh
views issue fresh IDs; stale, consumed and foreign-session tokens return
`unchanged`. Retry is deliberate, targets the current query and never reacquires
an old token. GET requests and local cache writes are the only effects; the
original command has no clipboard/browser/paste outcomes or reverse ACK contract
to emulate. No exactly-once or crash-durability guarantee is claimed.

Requests have a 5-second connect / 15-second total timeout, no environment endpoint
or proxy override, and a fixed original HTTPS provider. Completed network/status,
MIME, JSON and size failures produce sanitized visible messages and manual Retry.
Only same-key cached results remain on failure. The source's JSON MIME recognition
is reproduced from locked `fetch-utils.ts`; text/HTML is never executed. Redirects
are rejected as an explicit transport hardening adaptation; the port does not
follow a provider redirect to a different service. QA tests this refusal.

Limits are explicit failures, never silent result truncation: query 4,096 UTF-8
bytes, body 512 KiB, 1,000 rows, word 4,096 bytes, 64 definitions/word, each 8,192
bytes, view 4 MiB. Views have at least 12 MiB headroom beneath the SDK/host 16 MiB
frame cap. JSON recursion is bounded by serde_json. Registry/cache and per-response
allocation are finite; this is not a universal peak-RSS or OS scheduling claim.
Cache commits are small synchronous atomic replacements to avoid a detached late
writer overwriting a newer snapshot. Filesystem failures are visible. Windows
replacement behavior and GUI/network integration still require native validation.

Definitions remain source-derived Markdown; Rust never evaluates it. The pinned
host Markdown renderer sanitizes HTML through DOMPurify. The source has no
explicit external URL actions. UI/Markdown/OS producers are owned stubs during QA.

## Host prerequisite — unapplied

The main Tezbar checkout was accessed only through exact Git objects at
`ea100cee3f69711de12485ba061950c5fc65258f`. It was neither edited nor built.
`patches/0001-renderer-search-ownership.patch` is a generic prerequisite, not an
applied integration or a bundled adapter:

- Dispatch server-search input synchronously from the edit event. The existing
  200 ms post-edit server debounce otherwise lets an old A response overwrite B
  before B owns a request. Client-only search keeps its old debounce. Immediate
  server dispatch is an intentional timing adaptation to the source's throttle.
- Fence search, action, load-more and refresh results/errors by current session and
  query revision; recover from rejected search promises and clear old errors.
- Keep pending status visible, respect command-owned empty text, and accept SDK
  `unchanged` actions without replacing the current view.

The patch is applied only to a disposable fixture copy and compared with the
expected patched fixture. Tests execute the actual pinned list input and parent
reconciliation functions with owned React/OS producers. They demonstrate the
baseline failure and the bounded fixes; they are not a browser/GUI acceptance test
or a whole-host typecheck. Two Rust tests execute the actual pinned host open
payload producer and annotator: notably absent launch `searchText` is produced as
JSON `null`, which the port accepts as an empty launch query. A closed stale action
has no effect. No SDK or host changes are required inside the production binary.

## Reproduce isolated verification

Use existing stable and 1.85 toolchains; no compiler, targets, global tools or fonts
are installed. On another machine adjust the toolchain lookup in `qa/env.py` to
its existing Rust installations. All mutable HOME/TMP/XDG/Cargo/npm/source copies,
TLS certificates and outputs live under `v2/.qa`, ignored `target` or `dist`.
From the repository root:

```sh
python3 v2/qa/env.py python3 qa/bootstrap.py
python3 v2/qa/env.py python3 qa/verify.py
python3 v2/qa/env.py python3 qa/finalize.py
```

`bootstrap.py` uses unchanged V1 package/lock bytes in a disposable copy and locked
QA npm dependencies with install scripts disabled. `verify.py` runs source and
MIME oracles; the actual locked utils closure in a closed VM (all filesystem,
fetch, child/UI producers stubbed before evaluation); pinned renderer/helper and
full JSON Schema 2020-12 negative tests; stable + 1.85 fmt/tests/strict all-target
Clippy; existing Windows GNU check/Clippy; real SDK JSONL/TLS/cancel/capacity/frame
checks; unchanged V1 tests/typecheck; independent pin audit; and a locked production
source build from a newly empty Cargo home and target using the HTTPS SDK.

The separate `onelook-qa` binary requires the `qa` feature and an explicitly owned
loopback TLS URL plus certificate. It shares the production core/SDK bridge and
real reqwest transport. It is excluded from the development archive. There are
no live Datamuse calls, credentials, private queries, user clipboard/selection,
keychain, dialogs or live host sessions in the suite. Production has no QA
endpoint environment switch.

`qa/package.py` creates a deterministic ARM64 development ZIP in ignored `dist`,
with fixed timestamps/modes and a closed member-to-SHA256 manifest. Two ZIP
serializations of identical inputs must match. This does not claim reproducible
compiler output across environments. It validates extraction and launches the
actual extracted default-feature production command over SDK pipes. A specifically
seeded owned cache fixture exercises its definitions/actions without provider
network calls; this is identified separately from owned TLS HTTP tests.

`evidence/gates.json` records exits and log digests. Source/renderer/process/schema,
independent pin-audit and development-package evidence are inspectable alongside
it. Baseline V1 tests/typecheck pass without upgrades. Windows GNU checks are
blocked by the missing MinGW C compiler used by ring; MinGW/dlltool/MSVC/native
Windows and both host GUI acceptance remain gaps. This tree is ready for source
review, not a verified dual-platform release.

## Provenance and review

XERJ used canonical prefix `ax-d6d7c46f0a53` and an owned `.qa` journal. The
original code indexed, but the final incremental update hit frozen dataset/schema
evolution on a new Rust file. No alternate prefix, restart or schema change was
attempted. Full source, exact Git reads, `rg` and independent hashes supply the
verification; the Rust index is explicitly incomplete (`evidence/search.json`).

`fixtures/pins.json` anchors genuine own/SDK/host Git objects and icon provenance;
`fixtures/utils-provenance.json` independently verifies the locked npm archive SRI
and original source-map contents. Derived host snippets must exactly match those
pins. `qa/audit.py` checks these independently of the review inventory and verifies
all V1 tracked bytes except this root README discovery link.

`notices/inventory.json` records authentic dependency grants, including r-efi's
actual `AUTHORS`. The locked Raycast API/utils tarballs declare MIT but omit grant
text; exact metadata and that precise gap are retained in `NOTICE`. No missing
legal grant or legal approval is invented.

`evidence/review-inventory.json` inventories every Git-visible `v2` file plus the
root README, excluding itself. Before committing, the parent must stage the
reviewed scope and rehash the **staged blobs** against that inventory; this agent
leaves everything unstaged/uncommitted. No push, PR, release, installation, clone
deletion, sibling/host/SDK/catalog/profile/ledger changes are performed here.

Temporary T3 project registration for parent cleanup only:
`mcp:66be60c2-9036-42e2-8473-65d5c1fb7204`. This implementation does not alter it.
