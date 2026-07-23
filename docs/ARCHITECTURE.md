# Architecture & Implementation

This document covers how the system is put together: the encrypted file format both apps share, the desktop app's internal architecture, the Android app's internal architecture, and how the two are kept compatible.

For feature scope and phased build history, see [`jb_finacial_tooling_plan.md`](../jb_finacial_tooling_plan.md).

---

## 1. System overview

```
                    ┌─────────────────────────┐
                    │   *.enc  (portable file)  │
                    │  synced via Dropbox/Drive │
                    └───────────┬───────────────┘
                                │
                ┌───────────────┴────────────────┐
                │                                 │
      ┌─────────▼──────────┐           ┌──────────▼──────────┐
      │  finance_app/       │           │  android/             │
      │  Python + PySide6   │           │  Kotlin + Compose     │
      │  full feature set    │           │  Vault (r/w) +         │
      │                       │           │  Dashboard (read-only) │
      └───────────────────────┘           └────────────────────────┘
```

Both apps read and write the *same* encrypted file, independently. There is no server, no API, no shared runtime — compatibility exists purely because both apps implement the identical encryption/serialization scheme against the identical SQLite schema. That equivalence is verified by tests (§5), not assumed.

Sync has two tiers. By default it's deliberately dumb: the file just needs to land in the same place both apps look — a Dropbox/Google-Drive-synced folder on desktop, and on Android, anything reachable through the Storage Access Framework (including the Google Drive app's own document provider). Neither app talks to a cloud API directly; the sync provider's own app does that.

As an additional opt-in path, both apps can also talk to the Google Drive v3 REST API directly (OAuth, scoped to `drive.file` — only files the app itself creates/opens): desktop mirrors a local file to/from a linked Drive file via `finance_app/sync/` (`DriveAuthManager`, `DriveClient`, `DriveSyncService`); Android reads/writes a chosen Drive file directly through `DriveEncryptedFileStore`, a second `EncryptedFileStore` implementation alongside `SafEncryptedFileStore`. This is additive — the "dumb sync" paths above remain fully available and unaffected.

---

## 2. Encrypted file format

The on-disk file is:

```
[ 16-byte salt ][ Fernet token (rest of file) ]
```

### 2.1 Key derivation

```
master password ──Argon2id(salt)──► root_key (32 bytes)
root_key ──HKDF-SHA256(info=b"finance_key")──► finance_key (32 bytes)
root_key ──HKDF-SHA256(info=b"vault_key")───► vault_key   (32 bytes)
```

- **Argon2id** params: `time_cost=3`, `memory_cost=256 MiB`, `parallelism=4`, `version=0x13` (19) — these must match exactly between implementations, since they're inputs to the KDF, not just tuning knobs. Defined in `finance_app/security/crypto.py` and mirrored in `android/crypto/.../FinanceCrypto.kt`.
- **HKDF**: salt parameter is omitted, which per RFC 5869 (and confirmed against the `cryptography` library's actual behavior) is equivalent to a 32-byte all-zero salt — the Kotlin port uses that explicitly since Bouncy Castle's `HKDFParameters` requires a salt argument.
- `finance_key` encrypts the whole SQLite file. `vault_key` is used *only* for vault item payloads and is never derived from or convertible to `finance_key` — the two are cryptographically independent outputs of the same root key, not layers of the same key.

### 2.2 File-level encryption (Fernet)

The file body (everything after the 16-byte salt) is a [Fernet token](https://github.com/fernet/spec): `version(1) | timestamp(8, big-endian) | iv(16) | AES-128-CBC ciphertext | HMAC-SHA256(32)`, base64url-encoded. `finance_key`'s 32 bytes split into a 16-byte signing key and a 16-byte encryption key (this is exactly what Python's `Fernet` class does internally with a base64-encoded 32-byte key; the Kotlin port skips the base64 round-trip and just splits the raw bytes directly — same result).

Decrypting the file means: read the 16-byte salt, derive keys from the password, Fernet-decrypt the remainder into a plaintext SQLite database, and open that with any standard SQLite driver.

### 2.3 Vault item encryption (AES-256-GCM)

Each `vault_items` row stores `payload_nonce` (12 bytes) and `payload_ciphertext` (plaintext JSON + 16-byte GCM tag) as BLOBs, encrypted with `vault_key`. GCM's authentication tag means a corrupted or tampered row fails to decrypt loudly (`WrongPassword`/`VaultTamperedOrWrongKey` on desktop and Android respectively) rather than silently returning garbage.

### 2.4 Why this design

- Two independent keys instead of one: if a bug or future feature ever leaks `finance_key` (e.g., a misconfigured export), vault items stay opaque, because `vault_key` isn't derivable from it.
- Everything lives in one file rather than a separate vault file: fewer files to sync/lose, one master password to remember, and the desktop app's "portable single file" design goal stays intact.
- Argon2id was chosen over PBKDF2 for memory-hardness (GPU/ASIC cracking resistance) — see the tradeoff this created for Android in §6.4.

---

## 3. Desktop app (`finance_app/`)

Python + PySide6 (Qt), layered MVC: `ui/` never touches `data/` directly, always through `services/`.

```
finance_app/
├── data/
│   ├── models.py       SQLAlchemy ORM models (see §3.2)
│   └── database.py     DatabaseManager — encrypt/decrypt lifecycle (see §3.1)
├── security/
│   ├── crypto.py        Argon2id + Fernet
│   ├── vault_crypto.py   HKDF + AES-256-GCM
│   └── clipboard.py      copy-with-auto-clear
├── services/            one module per domain, session-scoped, no Qt imports
├── ui/
│   ├── main_window.py    tab host, idle-timeout auto-lock
│   ├── views/            one widget per tab
│   ├── dialogs/          add/edit dialogs, unlock dialog
│   ├── widgets/          chart_canvas.py (matplotlib embedding)
│   └── icons.py          qtawesome icon lookup
└── main.py               entry point / unlock-relock loop
```

### 3.1 `DatabaseManager` lifecycle

`finance_app/data/database.py` owns the encrypt/decrypt cycle:

1. **`unlock(password)`** — if the target file doesn't exist, generates a salt and creates a new empty encrypted DB; otherwise reads the file, splits salt/token, derives keys, Fernet-decrypts into a private temp file (`tempfile.mkdtemp()`), and opens a SQLAlchemy engine against that temp file. Either way, `Base.metadata.create_all(engine)` runs afterward — this is idempotent (only creates missing tables) so it also **migrates older files forward** when new tables are added to `models.py`, without a formal migration tool.
2. **`save()`** — disposes pooled connections (forces the temp file to reflect all committed writes), reads the temp file's bytes, Fernet-encrypts with the *same salt* used at unlock, writes `salt + token` back to the portable file path.
3. **`lock()`** — calls `save()`, drops keys from memory, deletes the temp file.

Every view's mutating action (add/edit/delete) calls a shared `MainWindow._on_data_activity()` callback, which resets the idle-lock timer and calls `save()` — so the on-disk file stays current after every change rather than only at app close, and other tabs' currency-dependent rollups get refreshed too.

Idle auto-lock: a `QTimer` in `MainWindow` (default 5 minutes) calls `lock()` and returns to the unlock dialog.

### 3.2 Data model (`finance_app/data/models.py`)

| Model | Purpose |
|---|---|
| `Account` | bank/cash/broker account, name + currency |
| `Transaction` | expense/income entry — signed `amount` (negative = expense), category, recurrence rule |
| `Debt` | loan/debt principal, rate, term, minimum payment |
| `Investment` | stock/fund holding — units, buy price, manually-updated current price |
| `FixedDeposit` | principal, rate, start/maturity dates |
| `OtherInvestment` | free-form holding (gold, real estate, crypto, ...) |
| `Borrowing` | money lent/owed — counterparty, direction, status |
| `ExchangeRate` | manual FX rate table, `"FROM_TO"` pair + rate + date |
| `AppSetting` | generic key/value store (currently just `base_currency`) |
| `NetWorthSnapshot` | one recorded net-worth data point per day, for the dashboard's history chart |
| `VaultItem` | password vault entry — plaintext metadata (title/folder/tags) + encrypted payload |

All SQLAlchemy `date`/`datetime` columns serialize to SQLite as ISO text (`YYYY-MM-DD` / `YYYY-MM-DD HH:MM:SS.ffffff`) — the Android side parses/writes these same string formats directly since it talks to the SQLite file with plain SQL, not an ORM.

### 3.3 Services

Each `services/*.py` module takes a SQLAlchemy `Session` (and sometimes another service) in its constructor and exposes plain CRUD + domain logic — no UI imports, so they're usable/testable headlessly (this is how all of the phase-by-phase verification in this project was done: headless scripts driving services directly, plus `QT_QPA_PLATFORM=offscreen` for full-UI smoke tests).

Notable non-CRUD logic:

- **`debt_service.calculate_payoff_plan`** — month-by-month amortization simulation for snowball (smallest balance first) vs. avalanche (highest rate first) payoff strategies. The combined monthly outlay (sum of all minimums + extra) stays constant; once a debt is paid off, its minimum payment rolls into the pool for the next-targeted debt. Returns per-debt payoff dates/interest and a feasibility flag (budget too low to ever pay off principal + accruing interest).
- **`currency_service`** — stores a manually-maintained exchange rate table (`convert()`/`try_convert()` looks up the latest rate for a pair, or its inverse). No live rate API — this was an explicit MVP scope decision.
- **`report_service`** — aggregates across all other services into base-currency figures for the dashboard: net worth (cash position from transaction sum + investments + FDs + other + net pending borrowings − debt principal), expense breakdown by category, and investment allocation by type. Values that can't be converted (missing FX rate) are reported separately rather than silently dropped.

### 3.4 UI

`MainWindow` hosts one `QTabWidget`; each tab is a `View` widget backed by one service (or two, e.g. `InvestmentsView` uses both `InvestmentService` and `FDService`). Views never construct their own `QSqlDatabase`/session — everything flows through the services they're handed at construction.

Charts (`ui/widgets/chart_canvas.py`) embed matplotlib via `FigureCanvasQTAgg`, used by the Dashboard tab for net worth history, expense breakdown, debt payoff timeline, and investment allocation.

---

## 4. Android app (`android/`)

Two Gradle modules, deliberately split so the highest-risk code (crypto) is testable without any Android dependency:

```
android/
├── crypto/                          pure Kotlin/JVM module, no Android SDK dependency
│   └── FinanceCrypto.kt              Kotlin port of security/crypto.py + vault_crypto.py
└── app/                             Android application module (Jetpack Compose)
    ├── data/
    │   ├── EncryptedFileStore.kt      interface: readBytes()/writeBytes()
    │   ├── SafEncryptedFileStore.kt   real impl — Storage Access Framework
    │   ├── FinanceRepository.kt       crypto + raw SQLite access (mirrors DatabaseManager)
    │   ├── FilePrefs.kt               DataStore — remembers the last-picked file Uri
    │   └── VaultModels.kt             data classes + vault field schemas
    ├── ui/
    │   ├── AppViewModel.kt            single ViewModel, screen-state machine
    │   ├── UnlockScreen.kt / VaultScreen.kt / DashboardScreen.kt / MainScreen.kt
    │   └── ClipboardAutoClear.kt
    └── MainActivity.kt                SAF picker launcher, screen switch on ViewModel state
```

### 4.1 `crypto` module

`FinanceCrypto.kt` mirrors the Python crypto modules function-for-function: `deriveRootKey`, `deriveSubkey`/`financeKeyFromRoot`/`vaultKeyFromRoot`, `fernetEncrypt`/`fernetDecrypt`, `vaultEncrypt`/`vaultDecrypt`, `decryptFile`. Implementation choices, and why:

- **Argon2id**: [Bouncy Castle](https://www.bouncycastle.org/)'s `Argon2BytesGenerator` — pure Kotlin/Java, no NDK/native dependency, so it runs identically in a plain JVM unit test and on-device. (An Android-specific NDK-wrapped Argon2 library was considered and rejected specifically because it can't run in a fast JVM test loop.)
- **HKDF**: Bouncy Castle's `HKDFBytesGenerator`, explicit 32-byte zero salt (see §2.1).
- **Fernet**: hand-rolled against the spec using plain `javax.crypto` (`Cipher`, `Mac`) — no third-party Fernet library, since the format is simple enough to implement directly and this avoids trusting an unmaintained dependency for something security-critical.
- **AES-GCM**: `javax.crypto.Cipher("AES/GCM/NoPadding")`, 12-byte nonce, 128-bit tag — directly interoperable with Python's `cryptography.hazmat.primitives.ciphers.aead.AESGCM` (both append the tag to the ciphertext the same way).

### 4.2 `FinanceRepository`

Mirrors `DatabaseManager`'s lifecycle: `unlock(password)` reads bytes via an injected `EncryptedFileStore`, derives keys, Fernet-decrypts to a local temp file, opens it with `android.database.sqlite.SQLiteDatabase` directly (plain SQL against the same schema Python's SQLAlchemy models produce — no ORM on this side). `lock()`/an internal `save()` re-encrypt with the *same salt* and write back through the file store.

The `EncryptedFileStore` interface exists specifically to keep this class testable: production uses `SafEncryptedFileStore` (real `ContentResolver` I/O), tests use a trivial `java.io.File`-backed implementation, so `FinanceRepository`'s crypto+SQLite logic can be exercised in a fast JVM test without any SAF/emulator involvement.

### 4.3 Storage Access Framework sync

`SafEncryptedFileStore` reads/writes via `ContentResolver.openInputStream`/`openOutputStream(uri, "wt")` against a `Uri` obtained from `ActivityResultContracts.OpenDocument()`. `takePersistableUriPermission()` is called on first pick so the app can reopen the same file on later launches without re-prompting (`FilePrefs`, a small DataStore wrapper, remembers the `Uri` string).

This deliberately avoids the Google Drive REST API / OAuth: the SAF picker can target the Google Drive app's own `DocumentsProvider`, so *the Drive app* handles authentication and the actual upload/sync — this app just reads and writes bytes through a standard Android content URI, the same way it would for any local file.

### 4.4 MVVM / screen flow

`AppViewModel` holds one `StateFlow<AppUiState>` and a `Screen` enum (`PickFile → Unlock → Main`) that `MainActivity` switches on directly (no navigation library). `MainActivity.onStop()` calls `viewModel.lock()` unconditionally — auto-lock fires whenever the app leaves the foreground, not on a timer like desktop. This is intentionally more aggressive than desktop's 5-minute idle timeout, matching typical password-manager mobile UX, at the cost of re-prompting after any brief backgrounding (e.g. switching to the SAF picker itself triggers and then un-triggers this, since picking a file returns to the same activity).

### 4.5 A real bug this caught: Argon2's memory cost vs. Android's heap

Argon2id's `memory_cost=256 MiB` parameter is not a tuning knob that can differ between implementations — changing it changes the derived key, breaking cross-app compatibility. On Android, allocating that inside the default per-app heap ceiling (~192MB) threw `OutOfMemoryError` on first real-device testing. Fixed with `android:largeHeap="true"` in the manifest rather than lowering the memory cost, since the latter would have required also changing the Python side and invalidating every existing encrypted file. This was only caught by testing on a real emulator — the Robolectric test suite doesn't reproduce Android's heap limits, so it passed throughout.

---

## 5. Cross-app compatibility & verification

Because there's no shared runtime, compatibility is verified with fixtures rather than assumed:

1. **`android/crypto/src/test/resources/crypto_fixture.properties`** — raw key/token/ciphertext values generated by calling `finance_app.security.crypto`/`vault_crypto` directly from a short Python script. `FinanceCryptoTest.kt` decrypts these with the Kotlin implementation and asserts equality — this is what proves Argon2id/HKDF/Fernet/AES-GCM are byte-for-byte compatible, not just "should be based on matching parameters."
2. **`android/app/src/test/resources/repository_fixture.enc`** — a complete encrypted data file (vault items, base currency, a net-worth snapshot) produced by the real `DatabaseManager`/`VaultService`/`CurrencyService`/`ReportService`. `FinanceRepositoryTest.kt` (Robolectric — gives a real `SQLiteDatabase` and `org.json` in a plain JVM test, no emulator needed) opens it, reads vault items and dashboard data, and separately writes a new vault item back and confirms it round-trips through a fresh repository instance.
3. **Actual cross-language round trip** (done once during development, not automated): the Kotlin test's write-back output was copied out of the Gradle build directory and opened with the real Python `DatabaseManager` in a one-off script, confirming the desktop app can read a file the Android code wrote — including decrypting the added vault item's AES-GCM payload correctly.
4. **On-device verification**: the flow (SAF file pick → Argon2id unlock → Vault list/decrypt → copy-to-clipboard → edit-dialog decrypt) was driven end-to-end on a Pixel 8 emulator via `adb`, which is what caught the `largeHeap` bug above — a class of failure invisible to both the JVM crypto tests and Robolectric.

If either app's on-disk format changes (a new table, a changed KDF parameter, a different token layout), both fixtures need regenerating from the Python side and the Kotlin tests re-run before trusting cross-app compatibility again.

---

## 6. Known limitations / open items

- **Android scope**: Vault (read/write) + Dashboard (read-only) only. Expenses/debts/investments/borrowings editing is desktop-only for now — a deliberate scope cut to limit how much surface area writes from a second codebase into the shared file.
- **Conflict detection**: only exists for the Drive-API sync path (§1) — both `DriveSyncService` (desktop) and `DriveEncryptedFileStore` (Android) track the Drive file's `headRevisionId` and refuse to overwrite it if it changed remotely since it was last read, warning the user instead. The "dumb sync" paths (manual Dropbox/Drive folder on desktop, SAF on Android) still have none — neither checks whether the on-disk file changed since it was last read before writing back, e.g. two devices editing around the same sync window. Those providers' own sync clients handle serialization differently and a lock-check for them remains unbuilt.
- **No live FX rates**: `currency_service` is a manually-maintained rate table by design (MVP scope) — no external rate API integration.
- **Net worth's debt component** uses each debt's original principal, not outstanding balance (paydown isn't tracked as a running balance separately from the payoff simulator), so `report_service.compute_net_worth()` is a conservative estimate once debts have been partially paid down.
- **Desktop has no automated test suite** — verification has been headless service-layer scripts plus offscreen Qt smoke tests, run ad hoc during development rather than wired into CI.
- **Android's unlock filename display and auto-lock behavior** are functional but minimally polished (see §4.4) — acceptable for the current Vault/Dashboard scope, worth revisiting if Android scope grows.
