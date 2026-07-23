package com.jbfinancial.app.data

import java.io.IOException

class DriveConflictException(message: String) : IOException(message)

/** Reads/writes the encrypted file directly through the Drive v3 REST API
 * for a single linked file id — no SAF/ContentResolver involved. Every
 * FinanceRepository mutation writes straight through [writeBytes] the same
 * way SafEncryptedFileStore always has, so this file is "live-synced" by
 * construction rather than needing a separate sync toggle.
 *
 * Tracks the Drive file's headRevisionId across read/write to detect if it
 * changed remotely in between (e.g. edited from another device) and refuses
 * to silently overwrite that change. */
class DriveEncryptedFileStore(
    private val client: DriveApiClient,
    private val fileId: String,
) : EncryptedFileStore {

    private var lastKnownRevision: String? = null

    override suspend fun readBytes(): ByteArray {
        val bytes = client.downloadFile(fileId)
        lastKnownRevision = client.getMetadata(fileId).headRevisionId
        return bytes
    }

    override suspend fun writeBytes(bytes: ByteArray) {
        val currentRevision = client.getMetadata(fileId).headRevisionId
        if (lastKnownRevision != null && currentRevision != lastKnownRevision) {
            throw DriveConflictException(
                "This file changed on Google Drive since it was last read here. " +
                    "Re-open it to get the latest version before continuing."
            )
        }
        lastKnownRevision = client.updateFile(fileId, bytes)
    }
}
