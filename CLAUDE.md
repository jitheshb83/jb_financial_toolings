# CLAUDE.md

## Project

Personal finance manager with double-encrypted vault. Two apps share one encrypted file:
- `finance_app/` — Python/Qt desktop (full features)
- `android/` — Kotlin/Compose Android (vault + read-only dashboard)

**Critical**: Any change to encryption, KDF params, or SQLite schema must be mirrored on both sides and verified against cross-app fixtures.

Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for file format, crypto details. [`jb_finacial_tooling_plan.md`](jb_finacial_tooling_plan.md) for roadmap.

## Quick start

**Desktop** (`finance_app/`):
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r finance_app/requirements.txt
python -m finance_app.main                          # run
QT_QPA_PLATFORM=offscreen python -m finance_app.main # headless test
```
No pytest suite. Test via headless imports or `QT_QPA_PLATFORM=offscreen`.

**Android** (`android/`, requires JDK 17+):
```bash
export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
./gradlew :crypto:test              # after ANY crypto change
./gradlew :app:testDebugUnitTest    # full FinanceRepository test
./gradlew :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```
Use `./gradlew` (pinned), not global gradle.

## Fixtures

Kotlin tests decrypt **real Python-produced files**:
- `android/crypto/src/test/resources/crypto_fixture.properties` — keys/ciphertexts
- `android/app/src/test/resources/repository_fixture.enc` — full sample data

If you change KDF/Fernet/AES-GCM/SQLite schema, regenerate both before trusting compatibility.

## Architecture essentials

**Encryption** (both apps identical):
```
master password --Argon2id(salt)--> root_key
  --HKDF-SHA256--> finance_key (Fernet-encrypts whole file)
  --HKDF-SHA256--> vault_key (AES-256-GCM per row)
```
KDF params (time_cost=3, memory_cost=256MiB, parallelism=4) are fixed; changes break all files.

**Desktop MVC**: UI → Services → Data. `DatabaseManager` handles decrypt/re-encrypt lifecycle. Services are headless-testable (no Qt imports). `MainWindow._on_data_activity()` saves on every mutation.

**Android MVVM**: `crypto/` is pure Kotlin/JVM (testable without emulator). `FinanceRepository` mirrors DatabaseManager. `EncryptedFileStore` interface allows testing. Single `AppViewModel`, `Screen` enum (PickFile → Unlock → Main).

**Gotchas**:
- Argon2id 256MB exceeds Android default heap; `android:largeHeap="true"` required.
- Android scope is Vault + Dashboard only (not full parity).
- No concurrent-edit conflict detection.
- Currency rates manually maintained.

## Prompt guidelines

**Be terse**: State task, file, line number. Skip context, setup, politeness.
- Bad: "I'm thinking about optimizing queries. Can you look at transaction fetching?"
- Good: "Optimize `finance_app/services/transaction_service.py:fetch_by_date()` — reduce N+1."

**No back-and-forth**: Include file path, line, constraints in one request.
- Bad: "Look at error?" → "It's in database.py" → "Line 42" → "Handle nulls too"
- Good: "Fix `finance_app/data/database.py:42` to handle nulls; don't break tests."

**Prevent overthinking**: Explicitly scope narrow fixes, no open-ended questions.
- "One-liner fix, don't refactor" not "How should we fix this?"
- Examples: `Add created_at to VaultItem, update fixtures.` / `Bug: decrypt fails on empty payload; early return in vault_crypto.py.`

**Do not imagine**: Never guess file paths, function names, test results, or external APIs. Verify first (grep, read, bash).

**Don't ask Claude to**: Syntax lookups, run tests, or explain code you haven't read yet.
