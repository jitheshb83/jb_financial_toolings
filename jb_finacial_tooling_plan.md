# Personal Finance Desktop App — Project Plan

## 1. Requirements Summary

| Area | Decision |
|---|---|
| Interface | Desktop GUI |
| Storage | Local, single portable file, cloud-sync friendly (Dropbox/Drive/OneDrive) |
| Security | Encrypted at rest, password-protected |
| Data entry | Manual now, bank/broker API later |
| Currency | Multi-currency |
| Modules | Expenses (incl. recurring/known), Debt & loan payoff planning, Investments (stocks/funds), Fixed deposits, Other investments, Borrowings (lent/owed), **Password vault** |
| Reporting | Charts & dashboards |
| Experience level | Intermediate Python, new to GUI |
| Vault design | Same file as finance data, but vault items get a **second, independent layer of encryption**; stores logins, secure notes, cards, and identities; no built-in generator |

---

## 2. Tech Stack Recommendation

| Layer | Choice | Why |
|---|---|---|
| GUI framework | **PySide6** (official Qt for Python) | LGPL license (free for any use), modern widgets, Qt Designer for drag-and-drop layout building, good docs, easier learning curve than raw PyQt licensing, embeds matplotlib well |
| Database | **SQLite** via **SQLAlchemy ORM** | Single-file, portable, syncs fine over Dropbox/Drive as long as only one device writes at a time (we'll add a simple lock-file check to warn about sync conflicts) |
| Encryption (file layer) | **Fernet symmetric encryption** (from the `cryptography` package) on the whole DB file, key derived from your master password via **Argon2id** | Avoids the native-build headaches of SQLCipher; app decrypts to a temp working file on unlock, re-encrypts on save/exit |
| Encryption (vault layer) | **AES-256-GCM** (via `cryptography`) applied per-item on top of the file-level encryption, using a *separate* key derived from the same master password via **HKDF key separation** | Authenticated encryption (detects tampering), unique nonce per item, and a distinct derived key means the vault key is never directly reusable even if the outer file key were somehow exposed |
| Key derivation | **Argon2id** (via `argon2-cffi`) instead of PBKDF2 | Memory-hard, GPU/ASIC-resistant — the current best-practice choice for master-password hashing/derivation |
| Charts | **matplotlib** embedded in PySide6 via `FigureCanvasQTAgg` | Mature, flexible, easy net-worth/debt/allocation charts |
| Currency conversion | Manual rate entry table now; `exchangerate.host` or similar free API later | Keeps MVP offline-capable |
| Packaging | **PyInstaller** | Produces a single executable per OS |
| Future bank/broker sync | Plaid / broker-specific APIs, added behind a `DataImportService` interface | Designed in from day one so it's a plug-in later, not a rewrite |

---

## 3. Architecture

```
finance_app/
├── data/
│   ├── models.py        # SQLAlchemy models (Account, Transaction, Debt, Investment, FD, Borrowing, Currency, ExchangeRate)
│   ├── database.py       # engine/session setup, encrypt/decrypt helpers
│   └── migrations/       # schema version handling (Alembic)
├── services/
│   ├── expense_service.py
│   ├── debt_service.py         # payoff plans: snowball/avalanche calculators
│   ├── investment_service.py
│   ├── fd_service.py
│   ├── borrowing_service.py
│   ├── currency_service.py     # conversion, rate table
│   ├── vault_service.py        # vault CRUD, enforces double-encryption on write/read
│   └── report_service.py       # net worth, aggregates for charts
├── ui/
│   ├── main_window.py
│   ├── views/            # one widget/screen per module (incl. vault view)
│   ├── widgets/           # reusable components (charts, tables, forms, copy-to-clipboard button)
│   └── dialogs/           # add/edit dialogs, unlock/password dialog
├── security/
│   ├── crypto.py          # Argon2id key derivation, Fernet file encrypt/decrypt
│   ├── vault_crypto.py    # HKDF key separation, AES-256-GCM per-item encrypt/decrypt
│   └── clipboard.py       # auto-clear clipboard N seconds after a password copy
├── main.py
└── requirements.txt
```

**Pattern:** simple layered MVC — `ui/` never talks to `data/` directly, always through `services/`. This keeps the GUI swappable later (e.g., if you ever want a web version) and makes the logic testable without a GUI.

---

## 4. Data Model (high-level)

- **Account**: name, type (bank/cash/broker), currency
- **Transaction**: date, account, category, amount, currency, is_recurring, recurrence_rule, note
- **Debt**: name, principal, interest_rate, currency, start_date, term, minimum_payment, linked_payments
- **Investment**: name, type (stock/fund), currency, units, buy_price, current_price (manual update for now)
- **FixedDeposit**: name, principal, interest_rate, currency, start_date, maturity_date
- **OtherInvestment**: flexible name/type/value fields for anything that doesn't fit above (gold, real estate, crypto, etc.)
- **Borrowing**: counterparty, direction (lent/owed), principal, currency, due_date, status
- **ExchangeRate**: currency_pair, rate, date
- **VaultItem**: type (login/secure_note/card/identity), title, folder/tags, encrypted_payload (JSON blob holding type-specific fields — username, password, URL, note text, card number, expiry, identity details — encrypted as a unit per item), nonce, created_at, updated_at

> Note: only `VaultItem.encrypted_payload` needs the AES-GCM inner layer — the surrounding metadata (title, folder, timestamps) stays as normal encrypted-at-file-level data so the app can list/search vault entries without decrypting every payload up front.

---

## 5. Password Vault — Security Design

Since this holds your actual credentials, it gets stronger treatment than the rest of the app:

1. **Master password → Argon2id** → produces a strong root key (memory-hard, resistant to brute-force/GPU cracking, tunable cost parameters).
2. **HKDF key separation** splits the root key into two independent keys:
   - `finance_key` → encrypts the whole SQLite file (Fernet), covering expenses/debts/investments/etc.
   - `vault_key` → *never* used for anything except vault items.
3. **Per-item AES-256-GCM**: each vault entry's sensitive payload is encrypted individually with `vault_key` + a fresh random nonce, and GCM's authentication tag means any tampering (e.g., a corrupted sync conflict) is detected rather than silently decrypted into garbage.
4. **In-memory hygiene**: decrypted vault payloads are only held in memory while a specific item is open for viewing/editing, and cleared immediately after (Python can't guarantee true memory zeroing, but we avoid keeping decrypted secrets around longer than needed).
5. **Clipboard auto-clear**: copying a password to the clipboard triggers an automatic clear after a configurable timeout (default 20–30s).
6. **Auto-lock**: the whole app re-locks (re-encrypts, drops keys from memory) after a configurable idle timeout, not just the vault.
7. **Practical effect of "same file, second layer"**: even though vault items live in the same SQLite file as your finances, someone who somehow recovered `finance_key` (e.g., a bug that leaks the outer layer) still cannot read vault items without `vault_key`, since the two are cryptographically independent, not just "the same key applied twice."

This gives you meaningfully stronger protection than a single layer, without the complexity of maintaining a fully separate vault file/password to remember.

---

## 6. Build Phases (suggested order)

### Phase 0 — Foundation (get a working shell)
- Project scaffold, virtual env, PySide6 "hello window"
- SQLAlchemy models + SQLite file creation
- Argon2id-based encryption/decryption of the DB file + password unlock dialog
- **Milestone:** app opens, asks for a password, shows an empty main window

### Phase 1 — Password vault
- HKDF key separation (`finance_key` / `vault_key`), AES-256-GCM per-item encrypt/decrypt
- CRUD for logins, secure notes, cards, identities; folders/tags
- Clipboard auto-clear, app auto-lock on idle
- **Milestone:** you can store and retrieve credentials with the double-encryption scheme working
- *(Built early, right after Phase 0, since the vault's crypto work is foundational and you'll likely want to start using it immediately)*

### Phase 2 — Core expense tracking
- Add/edit/delete transactions, categories, recurring expense rules
- Simple table view with filters (date range, category, currency)
- **Milestone:** you can log daily spending and see a running list

### Phase 3 — Debt & loan payoff planning
- Add debts/loans, compute payoff schedules (snowball & avalanche methods)
- Show projected payoff date and interest cost per method
- **Milestone:** you can see when a debt will be paid off and compare strategies

### Phase 4 — Investments, FDs, other investments
- Add holdings, manual price/value updates
- Portfolio value rollup by currency and in base currency

### Phase 5 — Borrowings
- Track money lent/owed, due dates, status (pending/settled)

### Phase 6 — Currency engine
- Base currency setting, manual exchange rate table, conversion used across all reports

### Phase 7 — Dashboard & reporting
- Net worth over time chart
- Expense breakdown pie/bar chart
- Debt payoff timeline chart
- Investment allocation chart

### Phase 8 — Polish
- Icon set across tabs/buttons/window (desktop UI, more visually distinct at a glance)
- Reminders for due payments/maturing FDs (in-app notification on launch)
- Backup/export (CSV/JSON export of all data — vault items excluded from plain export by default)
- Settings screen (base currency, categories, theme)

### Phase 9 — Packaging
- PyInstaller build for your OS
- Document the cloud-sync workflow (e.g., store the encrypted file in your Dropbox folder, add a lock-check to avoid conflicting edits from two devices at once)

### Phase 10 — Future: live data feeds
- Define `DataImportService` interface now (even if unused) so Plaid/broker APIs can be dropped in later without touching the rest of the app

### Phase 11 — Android companion app
- **Scope (v1):** Vault (full read/write) + Dashboard (read-only). Not full feature parity — expenses/debts/investments/borrowings editing stays desktop-only for now, to limit the blast radius of a second codebase writing to the same file.
- **Stack:** Native Kotlin/Android (best mobile UX and access to Android Keystore), separate codebase from the Python desktop app.
- **File compatibility:** a Kotlin crypto module re-implements the same on-disk format byte-for-byte — Argon2id key derivation, HKDF split into `finance_key`/`vault_key`, Fernet decrypt/encrypt for the file layer, AES-256-GCM for vault items — so either app can open a file the other last wrote.
- **Sync mechanism:** Android Storage Access Framework (SAF) file picker pointed at the Google Drive app's document provider. No Google API credentials/OAuth needed — the Drive app itself handles the actual upload/sync, the same way the desktop app just treats a Dropbox/Drive-synced folder as a normal file path.
- **Conflict handling:** same lock-check approach as the desktop cloud-sync workflow (Phase 9) — warn if the file's on-disk state doesn't match what was last read before writing back.
- **Milestone:** open the same `.enc` file created by the desktop app from an Android phone, unlock it, view/edit vault items and the net worth dashboard, and have changes show up back on desktop after a Drive sync.

---

## 7. Suggested Next Step

I'd recommend we start with **Phase 0** (encrypted SQLite setup + password-unlock flow), then move straight into **Phase 1** (the vault) since it depends on that foundation and you can start using it right away. Every feature module after that is largely independent and can be built one at a time.

Let me know if you want to:
1. Start writing Phase 0 + Phase 1 code now, or
2. Adjust anything in this plan first (e.g., snowball vs. avalanche default, category list, base currency, vault item fields).
