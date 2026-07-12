# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal finance manager with a built-in, double-encrypted password vault, implemented as **two independent apps that share one encrypted file format**:

- `finance_app/` — desktop app (Python + PySide6/Qt). Full feature set.
- `android/` — Android companion app (Kotlin + Jetpack Compose). Vault (read/write) + Dashboard (read-only) only.

There is no server and no shared runtime between them. Compatibility exists only because both sides implement the identical encryption scheme against the identical SQLite schema — and that equivalence is verified by fixture-based tests, not assumed. **Any change to the on-disk format, KDF parameters, or SQL schema on one side must be mirrored on the other and re-verified** (see "Cross-app fixtures" below).

Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) before making non-trivial changes — it documents the exact file format, key derivation hierarchy, and the reasoning behind several non-obvious choices (e.g. why Fernet is hand-rolled instead of using a library, why Bouncy Castle over an NDK Argon2 binding, why `android:largeHeap` is required). [`jb_finacial_tooling_plan.md`](jb_finacial_tooling_plan.md) has the phased feature plan and scope decisions.

## Commands

### Desktop app (`finance_app/`)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r finance_app/requirements.txt

python -m finance_app.main                          # run
QT_QPA_PLATFORM=offscreen python -m finance_app.main # headless smoke test (no display)
```

There is no automated test suite for the desktop app. Verification during development has been ad hoc headless scripts that import `finance_app.data`/`finance_app.services` directly and exercise them without Qt, plus offscreen Qt runs (`QT_QPA_PLATFORM=offscreen`) to smoke-test the full UI. When changing desktop code, follow that same pattern rather than assuming a `pytest` suite exists.

### Android app (`android/`)

Requires JDK 17+ (this project has been built against Android Studio's bundled JBR 21) and the Android SDK. From `android/`:

```bash
export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"  # or your JDK

./gradlew :crypto:test              # crypto module vs. real Python-produced fixtures — run this after ANY crypto change
./gradlew :app:testDebugUnitTest    # FinanceRepository vs. a real Python-produced .enc file (Robolectric, no emulator needed)
./gradlew :app:assembleDebug        # produces app/build/outputs/apk/debug/app-debug.apk

# single test class:
./gradlew :crypto:test --tests "com.jbfinancial.crypto.FinanceCryptoTest"
./gradlew :app:testDebugUnitTest --tests "com.jbfinancial.app.data.FinanceRepositoryTest"
```

Install/run on device or emulator: `adb install -r app/build/outputs/apk/debug/app-debug.apk`.

Note: the Gradle wrapper (`./gradlew`) is pinned to a version compatible with the AGP version Android Studio selected on last sync — prefer it over any globally-installed `gradle` binary, which may be a newer/incompatible major version.

### Cross-app fixtures

The Kotlin tests decrypt **real files produced by the Python app**, not synthetic Kotlin-only data:

- `android/crypto/src/test/resources/crypto_fixture.properties` — raw key/token/ciphertext values.
- `android/app/src/test/resources/repository_fixture.enc` — a full encrypted data file with sample vault items and a dashboard snapshot.

If you change the KDF parameters, the Fernet/AES-GCM handling, or the SQLite schema (`finance_app/data/models.py`), regenerate both fixtures from a short Python script that calls `finance_app.security.crypto`/`vault_crypto`/`data.database.DatabaseManager` directly, then re-run the Gradle tests above before trusting cross-app compatibility again.

## Architecture

### The shared encrypted file

```
[ 16-byte salt ][ Fernet token: everything after the salt ]
```

- `master password --Argon2id(salt)--> root_key` (params: time_cost=3, memory_cost=256MiB, parallelism=4 — these are KDF inputs, not tuning knobs; changing them on one side breaks compatibility with every existing file).
- `root_key --HKDF-SHA256--> finance_key` (info=`"finance_key"`) and `vault_key` (info=`"vault_key"`) — two independent subkeys, not layers of the same key.
- `finance_key` Fernet-encrypts the whole SQLite file body.
- `vault_key` AES-256-GCM-encrypts each `vault_items` row's payload individually (own nonce, authenticated).

Both `finance_app/security/crypto.py`+`vault_crypto.py` and `android/crypto/.../FinanceCrypto.kt` implement this identically; the Kotlin side is pure JVM (no Android dependency) specifically so it can be tested against Python-generated fixtures without an emulator.

### Desktop (`finance_app/`) — layered MVC

`ui/` never touches `data/` directly, always through `services/`.

- `data/database.py` — `DatabaseManager` owns the decrypt-to-tempfile / re-encrypt-on-save lifecycle. `unlock()` runs `Base.metadata.create_all()` unconditionally (idempotent), which doubles as a forward migration path when new tables are added — there's no separate migration tool.
- `data/models.py` — SQLAlchemy ORM models, one per domain table (`Account`, `Transaction`, `Debt`, `Investment`, `FixedDeposit`, `OtherInvestment`, `Borrowing`, `ExchangeRate`, `AppSetting`, `NetWorthSnapshot`, `VaultItem`).
- `services/*.py` — one module per domain, takes a SQLAlchemy `Session` in its constructor, no Qt imports. This is what makes headless testing possible. Notable non-CRUD logic: `debt_service.calculate_payoff_plan` (snowball/avalanche amortization simulation) and `report_service` (cross-service aggregation into base-currency dashboard figures).
- `ui/main_window.py` — hosts one `QTabWidget`, one view per tab, each view backed by the service(s) it's handed at construction. Every mutating UI action funnels through `MainWindow._on_data_activity()`, which resets the idle-lock timer and calls `DatabaseManager.save()` — so the file on disk stays current after every change, not just at app close.

### Android (`android/`) — two Gradle modules, MVVM

- `crypto/` — pure Kotlin/JVM, no Android SDK dependency. `FinanceCrypto.kt` mirrors the Python crypto modules function-for-function (Bouncy Castle for Argon2id/HKDF, hand-rolled Fernet over `javax.crypto`, `javax.crypto` AES-GCM).
- `app/data/FinanceRepository.kt` — mirrors `DatabaseManager`'s lifecycle, but talks to the decrypted SQLite file with plain SQL (`android.database.sqlite.SQLiteDatabase`), not an ORM — schema must match `models.py` by hand.
- `app/data/EncryptedFileStore.kt` — interface (`readBytes`/`writeBytes`) that decouples `FinanceRepository` from Android's `ContentResolver`, so it's unit-testable with a `java.io.File`-backed fake. Production uses `SafEncryptedFileStore`, which reads/writes through Android's Storage Access Framework — this is what lets the app sync via the Google Drive app's own document provider with no OAuth/API-key integration; the Drive app handles the actual cloud sync.
- `app/ui/AppViewModel.kt` — single ViewModel, one `StateFlow<AppUiState>`, a `Screen` enum (`PickFile → Unlock → Main`) that `MainActivity` switches on directly (no navigation library). `MainActivity.onStop()` unconditionally locks — auto-lock fires on any backgrounding, more aggressive than desktop's timer-based idle lock.

### Known non-obvious gotchas

- Argon2id's 256MB memory cost exceeds Android's default heap ceiling — `android:largeHeap="true"` in the manifest is required and was only caught by real on-device testing (Robolectric doesn't reproduce heap limits).
- Android's scope is deliberately Vault + Dashboard-only, not full parity with desktop — a scope cut to limit how much surface area a second codebase has for writing into the shared file.
- No conflict detection exists on either side for concurrent edits from two devices around the same sync window.
- Currency conversion uses a manually-maintained rate table (`currency_service`) — no live FX rate API.
