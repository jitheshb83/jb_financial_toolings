# Installation

This project isn't distributed as a signed, downloadable build yet (see "Project status" in the [README](../README.md)) — both apps are currently installed by building from source. This guide covers that for macOS (desktop app) and Android (companion app).

---

## macOS — desktop app (`finance_app/`)

### Prerequisites

- macOS with Python 3.11+ installed (`python3 --version` to check). If you don't have it, install via [Homebrew](https://brew.sh): `brew install python@3.11`.

### Install

```bash
git clone <this-repo-url>
cd jb_financial_toolings

python3 -m venv .venv
source .venv/bin/activate
pip install -r finance_app/requirements.txt
```

### Run

```bash
source .venv/bin/activate
python -m finance_app.main
```

### First run

You'll see an **Unlock Finance Data** dialog:

1. Set the data file location — it defaults to `~/finance_data.enc`. Change it (or Browse to a folder) if you want it inside a Dropbox/Google Drive-synced folder, so the same file is reachable from other devices.
2. Since the file doesn't exist yet, the dialog is in "create new" mode — set a master password (8+ characters) and confirm it. This password encrypts everything, including the vault; there is no recovery if you lose it.
3. The app opens on the Dashboard tab.

Every later launch: pick the same file, enter the same password.

### Every subsequent run

```bash
cd jb_financial_toolings
source .venv/bin/activate
python -m finance_app.main
```

### Notes

- The app re-encrypts and saves to disk after every add/edit/delete — there's no separate "save" step.
- The idle auto-lock timeout is 5 minutes; use *File → Lock now* to lock manually.
- No standalone `.app` bundle exists yet — Phase 9 of the [project plan](../jb_finacial_tooling_plan.md) covers building one with PyInstaller, not yet done.

---

## Android — companion app (`android/`)

There's no APK published anywhere yet, so this means building and sideloading a debug build.

### Prerequisites

- [Android Studio](https://developer.android.com/studio) — this single install gives you the JDK, Android SDK, and emulator you need; no separate Java/SDK setup required.
- An Android phone with **Developer options** and **USB debugging** enabled (Settings → About phone → tap "Build number" 7 times, then Settings → Developer options → USB debugging), or an Android emulator created from within Android Studio (Device Manager → Create device).

### Build

```bash
cd jb_financial_toolings/android
export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
./gradlew :app:assembleDebug
```

This produces `android/app/build/outputs/apk/debug/app-debug.apk`.

### Install

**Via USB (phone or emulator), using `adb`:**

```bash
export ANDROID_HOME="$HOME/Library/Android/sdk"
"$ANDROID_HOME/platform-tools/adb" devices          # confirm your device/emulator shows up
"$ANDROID_HOME/platform-tools/adb" install -r android/app/build/outputs/apk/debug/app-debug.apk
```

**Or from Android Studio directly:** open the `android/` folder as the project, select a device/emulator from the toolbar dropdown, and click Run.

**Or by sideloading manually:** copy `app-debug.apk` to the phone (AirDrop-equivalent, USB file transfer, or emailing it to yourself) and open it from a file manager — Android will prompt to allow installs from that source the first time.

### First run

1. **Choose file** — pick the `.enc` file created by the desktop app. If it's in a folder synced by the Google Drive app, you can navigate to it there directly through the picker; if it's on local/USB storage, browse to it the normal way. No Google account sign-in or API setup is needed — the picker just needs read/write access to wherever the file lives.
2. **Unlock** — enter the same master password used on desktop.
3. You land on the **Vault** tab (full read/write) with a **Dashboard** tab (read-only) alongside it.

### Notes

- The app locks automatically whenever it leaves the foreground (switching apps, screen off) — you'll need to re-enter the password each time you come back.
- Only Vault and Dashboard are available on Android; everything else (expenses, debts, investments, borrowings, currency settings) is desktop-only for now.
- To pick up changes made on desktop, make sure the file has finished syncing (via Drive/Dropbox) before unlocking on Android, and vice versa — there's no conflict detection if both devices write around the same time (see "Known limitations" in [`docs/ARCHITECTURE.md`](ARCHITECTURE.md)).

---

## Getting the same file onto both devices

1. On desktop, when creating the file for the first time, choose a location inside your Dropbox/Google Drive-synced folder (e.g. `~/Google Drive/finance_data.enc`).
2. Let it finish syncing to the cloud.
3. On the Android device, open the Google Drive app once so it's signed in and has synced that folder locally, then pick the file from within the Android app's file picker.

The file itself is just an encrypted blob — any sync mechanism that preserves bytes exactly (Drive, Dropbox, AirDrop, a USB copy) works equally well.
