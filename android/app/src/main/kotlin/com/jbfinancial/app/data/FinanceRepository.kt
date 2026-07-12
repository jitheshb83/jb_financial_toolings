package com.jbfinancial.app.data

import android.database.sqlite.SQLiteDatabase
import com.jbfinancial.crypto.FinanceCrypto
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.time.format.DateTimeFormatter
import java.time.LocalDateTime

/**
 * Vault (read/write) + Dashboard (read-only) access to the same encrypted
 * SQLite file the desktop app produces. Mirrors finance_app/data/database.py:
 * decrypt the portable file to a private temp file, query/modify it with
 * plain SQL (schema must match finance_app/data/models.py exactly), then
 * re-encrypt with the same salt and hand the bytes back to [fileStore].
 */
class FinanceRepository(
    private val fileStore: EncryptedFileStore,
    private val tempDbFile: File,
) {
    private var salt: ByteArray? = null
    private var financeKey: ByteArray? = null
    private var vaultKey: ByteArray? = null
    private var db: SQLiteDatabase? = null

    val isUnlocked: Boolean
        get() = db != null

    suspend fun unlock(password: String) = withContext(Dispatchers.IO) {
        val fileBytes = fileStore.readBytes()
        val fileSalt = fileBytes.copyOfRange(0, FinanceCrypto.SALT_SIZE)
        val token = fileBytes.copyOfRange(FinanceCrypto.SALT_SIZE, fileBytes.size)
        val keys = FinanceCrypto.unlock(password, fileSalt)
        val plaintext = FinanceCrypto.fernetDecrypt(token, keys.financeKey)

        tempDbFile.writeBytes(plaintext)
        salt = fileSalt
        financeKey = keys.financeKey
        vaultKey = FinanceCrypto.vaultKeyFromRoot(keys.rootKey)
        db = SQLiteDatabase.openDatabase(tempDbFile.absolutePath, null, SQLiteDatabase.OPEN_READWRITE)
        Unit
    }

    suspend fun lock() = withContext(Dispatchers.IO) {
        db?.close()
        db = null
        salt = null
        financeKey = null
        vaultKey = null
        if (tempDbFile.exists()) tempDbFile.delete()
        Unit
    }

    /** Re-encrypts the current temp DB state and writes it back through [fileStore]. */
    private suspend fun save() = withContext(Dispatchers.IO) {
        val requireDb = db ?: error("Repository is not unlocked")
        requireDb.close()
        val plaintext = tempDbFile.readBytes()
        val token = FinanceCrypto.fernetEncrypt(plaintext, financeKey!!)
        fileStore.writeBytes(salt!! + token)
        db = SQLiteDatabase.openDatabase(tempDbFile.absolutePath, null, SQLiteDatabase.OPEN_READWRITE)
    }

    // -- vault --------------------------------------------------------

    suspend fun listVaultItems(): List<VaultItemMeta> = withContext(Dispatchers.IO) {
        val requireDb = db ?: error("Repository is not unlocked")
        val items = mutableListOf<VaultItemMeta>()
        requireDb.rawQuery(
            "SELECT id, type, title, folder, tags, updated_at FROM vault_items ORDER BY title",
            null,
        ).use { cursor ->
            while (cursor.moveToNext()) {
                items += VaultItemMeta(
                    id = cursor.getLong(0),
                    type = cursor.getString(1),
                    title = cursor.getString(2),
                    folder = cursor.getString(3),
                    tags = cursor.getString(4),
                    updatedAt = cursor.getString(5),
                )
            }
        }
        items
    }

    suspend fun getVaultPayload(id: Long): Map<String, String> = withContext(Dispatchers.IO) {
        val requireDb = db ?: error("Repository is not unlocked")
        requireDb.rawQuery(
            "SELECT payload_nonce, payload_ciphertext FROM vault_items WHERE id = ?",
            arrayOf(id.toString()),
        ).use { cursor ->
            if (!cursor.moveToFirst()) error("No vault item with id $id")
            val nonce = cursor.getBlob(0)
            val ciphertext = cursor.getBlob(1)
            val plaintext = FinanceCrypto.vaultDecrypt(nonce, ciphertext, vaultKey!!)
            jsonToMap(String(plaintext, Charsets.UTF_8))
        }
    }

    suspend fun createVaultItem(
        type: String,
        title: String,
        folder: String?,
        tags: String?,
        fields: Map<String, String>,
    ): Long = withContext(Dispatchers.IO) {
        val requireDb = db ?: error("Repository is not unlocked")
        val (nonce, ciphertext) = FinanceCrypto.vaultEncrypt(mapToJson(fields).toByteArray(Charsets.UTF_8), vaultKey!!)
        val now = nowSqliteDateTime()
        val id = requireDb.insert(
            "vault_items",
            null,
            android.content.ContentValues().apply {
                put("type", type)
                put("title", title)
                put("folder", folder)
                put("tags", tags)
                put("payload_nonce", nonce)
                put("payload_ciphertext", ciphertext)
                put("created_at", now)
                put("updated_at", now)
            },
        )
        save()
        id
    }

    suspend fun updateVaultItem(
        id: Long,
        title: String,
        folder: String?,
        tags: String?,
        fields: Map<String, String>,
    ) = withContext(Dispatchers.IO) {
        val requireDb = db ?: error("Repository is not unlocked")
        val (nonce, ciphertext) = FinanceCrypto.vaultEncrypt(mapToJson(fields).toByteArray(Charsets.UTF_8), vaultKey!!)
        requireDb.update(
            "vault_items",
            android.content.ContentValues().apply {
                put("title", title)
                put("folder", folder)
                put("tags", tags)
                put("payload_nonce", nonce)
                put("payload_ciphertext", ciphertext)
                put("updated_at", nowSqliteDateTime())
            },
            "id = ?",
            arrayOf(id.toString()),
        )
        save()
        Unit
    }

    suspend fun deleteVaultItem(id: Long) = withContext(Dispatchers.IO) {
        val requireDb = db ?: error("Repository is not unlocked")
        requireDb.delete("vault_items", "id = ?", arrayOf(id.toString()))
        save()
        Unit
    }

    // -- dashboard (read-only) -----------------------------------------

    suspend fun getBaseCurrency(): String = withContext(Dispatchers.IO) {
        val requireDb = db ?: error("Repository is not unlocked")
        requireDb.rawQuery("SELECT value FROM app_settings WHERE key = 'base_currency'", null).use { cursor ->
            if (cursor.moveToFirst()) cursor.getString(0) else "USD"
        }
    }

    suspend fun netWorthHistory(): List<NetWorthPoint> = withContext(Dispatchers.IO) {
        val requireDb = db ?: error("Repository is not unlocked")
        val points = mutableListOf<NetWorthPoint>()
        requireDb.rawQuery("SELECT date, total_value FROM net_worth_snapshots ORDER BY date", null).use { cursor ->
            while (cursor.moveToNext()) {
                points += NetWorthPoint(cursor.getString(0), cursor.getDouble(1))
            }
        }
        points
    }

    companion object {
        private val SQLITE_DATETIME_FORMAT: DateTimeFormatter =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss.SSSSSS")

        fun nowSqliteDateTime(): String = LocalDateTime.now().format(SQLITE_DATETIME_FORMAT)

        fun jsonToMap(json: String): Map<String, String> {
            val obj = JSONObject(json)
            return obj.keys().asSequence().associateWith { obj.getString(it) }
        }

        fun mapToJson(fields: Map<String, String>): String {
            val obj = JSONObject()
            fields.forEach { (k, v) -> obj.put(k, v) }
            return obj.toString()
        }
    }
}
