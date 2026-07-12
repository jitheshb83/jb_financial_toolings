package com.jbfinancial.app.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.os.Handler
import android.os.Looper

private const val DEFAULT_CLEAR_MILLIS = 25_000L

/** Mirrors security/clipboard.py: copy a secret, then clear the clipboard
 * after a timeout — but only if it still holds exactly what we put there. */
fun copyWithAutoClear(context: Context, label: String, text: String, delayMillis: Long = DEFAULT_CLEAR_MILLIS) {
    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    clipboard.setPrimaryClip(ClipData.newPlainText(label, text))

    Handler(Looper.getMainLooper()).postDelayed({
        val current = clipboard.primaryClip
        val currentText = if (current != null && current.itemCount > 0) {
            current.getItemAt(0).coerceToText(context).toString()
        } else null
        if (currentText == text) {
            clipboard.setPrimaryClip(ClipData.newPlainText("", ""))
        }
    }, delayMillis)
}
