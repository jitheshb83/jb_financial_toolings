package com.jbfinancial.app.data

/** Abstracts where the encrypted portable file's bytes come from/go to, so
 * FinanceRepository's crypto+SQLite logic can be unit tested without a real
 * SAF Uri / ContentResolver (see FinanceRepositoryTest, which uses a plain
 * java.io.File-backed implementation). */
interface EncryptedFileStore {
    suspend fun readBytes(): ByteArray
    suspend fun writeBytes(bytes: ByteArray)
}
