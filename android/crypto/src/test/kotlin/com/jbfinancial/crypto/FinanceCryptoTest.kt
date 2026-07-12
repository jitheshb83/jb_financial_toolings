package com.jbfinancial.crypto

import java.util.Base64
import java.util.Properties
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertFailsWith

/**
 * Verifies the Kotlin crypto port against real fixtures produced by the
 * Python desktop app (see crypto_fixture.properties, generated from
 * finance_app/security/crypto.py + vault_crypto.py). If these pass, a file
 * written by one app can be read by the other.
 */
class FinanceCryptoTest {
    private val fixture: Properties = Properties().apply {
        FinanceCryptoTest::class.java.getResourceAsStream("/crypto_fixture.properties")!!.use { load(it) }
    }

    private fun hexDecode(s: String): ByteArray {
        val out = ByteArray(s.length / 2)
        for (i in out.indices) {
            out[i] = ((Character.digit(s[i * 2], 16) shl 4) + Character.digit(s[i * 2 + 1], 16)).toByte()
        }
        return out
    }
    private fun b64(s: String) = Base64.getDecoder().decode(s)

    @Test
    fun `derives root key matching python argon2id output`() {
        val salt = hexDecode(fixture.getProperty("salt_hex"))
        val rootKey = FinanceCrypto.deriveRootKey(fixture.getProperty("password"), salt)
        assertContentEquals(hexDecode(fixture.getProperty("root_key_hex")), rootKey)
    }

    @Test
    fun `derives finance and vault subkeys matching python hkdf output`() {
        val rootKey = hexDecode(fixture.getProperty("root_key_hex"))
        val financeKey = FinanceCrypto.financeKeyFromRoot(rootKey)
        val vaultKey = FinanceCrypto.vaultKeyFromRoot(rootKey)
        assertContentEquals(hexDecode(fixture.getProperty("finance_key_hex")), financeKey)
        assertContentEquals(hexDecode(fixture.getProperty("vault_key_hex")), vaultKey)
    }

    @Test
    fun `decrypts a fernet token produced by python`() {
        val financeKey = hexDecode(fixture.getProperty("finance_key_hex"))
        val token = fixture.getProperty("file_token_text").toByteArray(Charsets.US_ASCII)
        val plaintext = FinanceCrypto.fernetDecrypt(token, financeKey)
        assertContentEquals(b64(fixture.getProperty("file_plaintext_b64")), plaintext)
    }

    @Test
    fun `fernet round trip in kotlin`() {
        val financeKey = hexDecode(fixture.getProperty("finance_key_hex"))
        val plaintext = "round trip test 🔐".toByteArray(Charsets.UTF_8)
        val token = FinanceCrypto.fernetEncrypt(plaintext, financeKey)
        val decrypted = FinanceCrypto.fernetDecrypt(token, financeKey)
        assertContentEquals(plaintext, decrypted)
    }

    @Test
    fun `fernet decrypt fails clearly on wrong key`() {
        val wrongKey = ByteArray(32) { 7 }
        val token = fixture.getProperty("file_token_text").toByteArray(Charsets.US_ASCII)
        assertFailsWith<FinanceCrypto.WrongPassword> {
            FinanceCrypto.fernetDecrypt(token, wrongKey)
        }
    }

    @Test
    fun `decrypts a vault item produced by python`() {
        val vaultKey = hexDecode(fixture.getProperty("vault_key_hex"))
        val nonce = hexDecode(fixture.getProperty("vault_nonce_hex"))
        val ciphertext = hexDecode(fixture.getProperty("vault_ciphertext_hex"))
        val plaintext = FinanceCrypto.vaultDecrypt(nonce, ciphertext, vaultKey)
        assertContentEquals(b64(fixture.getProperty("vault_plaintext_b64")), plaintext)
    }

    @Test
    fun `vault gcm round trip in kotlin`() {
        val vaultKey = hexDecode(fixture.getProperty("vault_key_hex"))
        val plaintext = """{"username":"bob","password":"hunter2"}""".toByteArray(Charsets.UTF_8)
        val (nonce, ciphertext) = FinanceCrypto.vaultEncrypt(plaintext, vaultKey)
        val decrypted = FinanceCrypto.vaultDecrypt(nonce, ciphertext, vaultKey)
        assertContentEquals(plaintext, decrypted)
    }

    @Test
    fun `vault gcm detects tampering`() {
        val vaultKey = hexDecode(fixture.getProperty("vault_key_hex"))
        val nonce = hexDecode(fixture.getProperty("vault_nonce_hex"))
        val ciphertext = hexDecode(fixture.getProperty("vault_ciphertext_hex"))
        ciphertext[0] = (ciphertext[0].toInt() xor 0xFF).toByte()
        assertFailsWith<FinanceCrypto.VaultTamperedOrWrongKey> {
            FinanceCrypto.vaultDecrypt(nonce, ciphertext, vaultKey)
        }
    }

    @Test
    fun `decrypts a full portable file end to end`() {
        val salt = hexDecode(fixture.getProperty("salt_hex"))
        val token = fixture.getProperty("file_token_text").toByteArray(Charsets.US_ASCII)
        val fileBytes = salt + token
        val (_, plaintext) = FinanceCrypto.decryptFile(fileBytes, fixture.getProperty("password"))
        assertContentEquals(b64(fixture.getProperty("file_plaintext_b64")), plaintext)
    }
}
