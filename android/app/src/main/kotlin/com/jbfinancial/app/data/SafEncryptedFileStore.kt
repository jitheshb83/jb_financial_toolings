package com.jbfinancial.app.data

import android.content.ContentResolver
import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Reads/writes the encrypted file through Android's Storage Access
 * Framework. Works for any document a user picks — including one exposed by
 * the Google Drive app's DocumentsProvider — with no Drive API/OAuth needed;
 * the provider app (Drive, Dropbox, ...) handles the actual cloud sync. */
class SafEncryptedFileStore(
    private val context: Context,
    private val uri: Uri,
) : EncryptedFileStore {

    override suspend fun readBytes(): ByteArray = withContext(Dispatchers.IO) {
        context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
            ?: throw IllegalStateException("Could not open $uri for reading")
    }

    override suspend fun writeBytes(bytes: ByteArray) = withContext(Dispatchers.IO) {
        // "wt" = write + truncate, so a shorter re-encrypted file doesn't leave
        // trailing garbage from the previous (longer) contents.
        context.contentResolver.openOutputStream(uri, "wt")?.use { it.write(bytes) }
            ?: throw IllegalStateException("Could not open $uri for writing")
    }

    companion object {
        fun persistPermission(context: Context, uri: Uri) {
            val flags = android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION or
                android.content.Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            context.contentResolver.takePersistableUriPermission(uri, flags)
        }
    }
}
