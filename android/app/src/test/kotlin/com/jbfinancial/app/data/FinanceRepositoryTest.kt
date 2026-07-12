package com.jbfinancial.app.data

import com.jbfinancial.crypto.FinanceCrypto
import kotlinx.coroutines.runBlocking
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Verifies FinanceRepository against a real .enc file produced by the Python
 * desktop app (see repository_fixture.enc, generated via finance_app's own
 * DatabaseManager/VaultService/CurrencyService/ReportService). Robolectric
 * gives us a real android.database.sqlite.SQLiteDatabase + org.json in a
 * plain JVM test, so this runs without an emulator.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class FinanceRepositoryTest {

    private class FileEncryptedFileStore(private val file: File) : EncryptedFileStore {
        override suspend fun readBytes(): ByteArray = file.readBytes()
        override suspend fun writeBytes(bytes: ByteArray) {
            file.writeBytes(bytes)
        }
    }

    private val fixturePassword = "MobileTestPass!789"

    private fun freshFixtureCopy(): File {
        val bytes = javaClass.getResourceAsStream("/repository_fixture.enc")!!.readBytes()
        val file = File.createTempFile("repo_test", ".enc")
        file.writeBytes(bytes)
        return file
    }

    @Test
    fun `reads vault items and dashboard data written by the python app`(): Unit = runBlocking {
        val workingFile = freshFixtureCopy()
        val tempDb = File.createTempFile("repo_test_db", ".sqlite3")
        val repo = FinanceRepository(FileEncryptedFileStore(workingFile), tempDb)

        repo.unlock(fixturePassword)

        val items = repo.listVaultItems()
        assertEquals(2, items.size)
        val github = items.first { it.title == "GitHub" }
        assertEquals("login", github.type)
        assertEquals("Dev", github.folder)
        assertEquals("code", github.tags)

        val payload = repo.getVaultPayload(github.id)
        assertEquals("jithesh", payload["username"])
        assertEquals("hunter2", payload["password"])
        assertEquals("github.com", payload["url"])

        val wifi = items.first { it.title == "Wifi" }
        assertEquals("ssid/pass here", repo.getVaultPayload(wifi.id)["notes"])

        assertEquals("USD", repo.getBaseCurrency())
        val history = repo.netWorthHistory()
        assertTrue(history.isNotEmpty())

        repo.lock()
    }

    @Test
    fun `writes back a new vault item and it survives a reopen`(): Unit = runBlocking {
        val workingFile = freshFixtureCopy()
        val tempDb = File.createTempFile("repo_write_test_db", ".sqlite3")
        val repo = FinanceRepository(FileEncryptedFileStore(workingFile), tempDb)
        repo.unlock(fixturePassword)

        val newId = repo.createVaultItem(
            type = "login",
            title = "Added From Android",
            folder = null,
            tags = null,
            fields = mapOf("username" to "androiduser", "password" to "androidpass"),
        )
        repo.lock()

        val tempDb2 = File.createTempFile("repo_write_test_db2", ".sqlite3")
        val repo2 = FinanceRepository(FileEncryptedFileStore(workingFile), tempDb2)
        repo2.unlock(fixturePassword)

        val items = repo2.listVaultItems()
        assertEquals(3, items.size)
        val added = items.first { it.id == newId }
        assertEquals("Added From Android", added.title)
        assertEquals("androiduser", repo2.getVaultPayload(newId)["username"])
        repo2.lock()

        assertTrue(workingFile.readBytes().size > FinanceCrypto.SALT_SIZE)

        // Leave the round-tripped file where a separate cross-language check can
        // decrypt it with the Python app (see android/verify_roundtrip.py).
        val artifact = File("build/test-artifacts/roundtrip_from_android.enc")
        artifact.parentFile.mkdirs()
        workingFile.copyTo(artifact, overwrite = true)
    }
}
