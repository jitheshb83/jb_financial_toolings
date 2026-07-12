package com.jbfinancial.crypto

import org.bouncycastle.crypto.generators.Argon2BytesGenerator
import org.bouncycastle.crypto.generators.HKDFBytesGenerator
import org.bouncycastle.crypto.params.Argon2Parameters
import org.bouncycastle.crypto.params.HKDFParameters
import java.nio.ByteBuffer
import java.security.SecureRandom
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.Mac
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.IvParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * Kotlin port of finance_app/security/crypto.py and vault_crypto.py.
 *
 * Every parameter here (Argon2id cost params, HKDF info strings, Fernet
 * token layout, AES-GCM nonce size) must exactly match the Python
 * implementation, since both apps read/write the same encrypted file.
 * Cross-checked against real fixtures produced by the Python app —
 * see FinanceCryptoTest.
 */
object FinanceCrypto {
    const val SALT_SIZE = 16
    const val ROOT_KEY_SIZE = 32
    private const val GCM_NONCE_SIZE = 12
    private const val GCM_TAG_BITS = 128

    // Must match ARGON2_TIME_COST / ARGON2_MEMORY_COST_KIB / ARGON2_PARALLELISM
    // in finance_app/security/crypto.py.
    private const val ARGON2_TIME_COST = 3
    private const val ARGON2_MEMORY_COST_KIB = 256 * 1024
    private const val ARGON2_PARALLELISM = 4

    class WrongPassword(message: String, cause: Throwable? = null) : Exception(message, cause)
    class VaultTamperedOrWrongKey(message: String, cause: Throwable? = null) : Exception(message, cause)

    // -- key derivation ---------------------------------------------------

    fun deriveRootKey(password: String, salt: ByteArray): ByteArray {
        val params = Argon2Parameters.Builder(Argon2Parameters.ARGON2_id)
            .withVersion(Argon2Parameters.ARGON2_VERSION_13)
            .withIterations(ARGON2_TIME_COST)
            .withMemoryAsKB(ARGON2_MEMORY_COST_KIB)
            .withParallelism(ARGON2_PARALLELISM)
            .withSalt(salt)
            .build()
        val generator = Argon2BytesGenerator()
        generator.init(params)
        val out = ByteArray(ROOT_KEY_SIZE)
        generator.generateBytes(password.toByteArray(Charsets.UTF_8), out)
        return out
    }

    fun deriveSubkey(rootKey: ByteArray, info: ByteArray, length: Int = 32): ByteArray {
        val generator = HKDFBytesGenerator(org.bouncycastle.crypto.digests.SHA256Digest())
        // cryptography's HKDF(salt=None) uses HashLen zero bytes as the salt (RFC 5869 default).
        val zeroSalt = ByteArray(32)
        generator.init(HKDFParameters(rootKey, zeroSalt, info))
        val out = ByteArray(length)
        generator.generateBytes(out, 0, length)
        return out
    }

    fun financeKeyFromRoot(rootKey: ByteArray): ByteArray =
        deriveSubkey(rootKey, "finance_key".toByteArray(Charsets.UTF_8))

    fun vaultKeyFromRoot(rootKey: ByteArray): ByteArray =
        deriveSubkey(rootKey, "vault_key".toByteArray(Charsets.UTF_8))

    fun generateSalt(): ByteArray = ByteArray(SALT_SIZE).also { SecureRandom().nextBytes(it) }

    // -- Fernet (file-level encryption) -----------------------------------
    // Token layout: version(1) | timestamp(8, big-endian) | iv(16) | ciphertext | hmac(32),
    // base64url-encoded. financeKey (32 raw bytes) splits into signingKey (first 16) +
    // encryptionKey (last 16) — equivalent to what Fernet does internally with a
    // base64-encoded 32-byte key, since Python's finance_key is used directly as raw
    // key material passed through base64.urlsafe_b64encode() before Fernet() decodes it again.

    fun fernetDecrypt(token: ByteArray, financeKey: ByteArray): ByteArray {
        val signingKey = financeKey.copyOfRange(0, 16)
        val encryptionKey = financeKey.copyOfRange(16, 32)

        val data = try {
            Base64.getUrlDecoder().decode(token)
        } catch (e: IllegalArgumentException) {
            throw WrongPassword("Incorrect master password or corrupted file.", e)
        }
        if (data.size < 1 + 8 + 16 + 32 || data[0] != 0x80.toByte()) {
            throw WrongPassword("Incorrect master password or corrupted file.")
        }

        val hmacTag = data.copyOfRange(data.size - 32, data.size)
        val signedPart = data.copyOfRange(0, data.size - 32)
        val expectedTag = hmacSha256(signingKey, signedPart)
        if (!expectedTag.contentEquals(hmacTag)) {
            throw WrongPassword("Incorrect master password or corrupted file.")
        }

        val iv = data.copyOfRange(9, 25)
        val ciphertext = data.copyOfRange(25, data.size - 32)
        return try {
            val cipher = Cipher.getInstance("AES/CBC/PKCS5Padding")
            cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(encryptionKey, "AES"), IvParameterSpec(iv))
            cipher.doFinal(ciphertext)
        } catch (e: Exception) {
            throw WrongPassword("Incorrect master password or corrupted file.", e)
        }
    }

    fun fernetEncrypt(plaintext: ByteArray, financeKey: ByteArray): ByteArray {
        val signingKey = financeKey.copyOfRange(0, 16)
        val encryptionKey = financeKey.copyOfRange(16, 32)

        val iv = ByteArray(16).also { SecureRandom().nextBytes(it) }
        val cipher = Cipher.getInstance("AES/CBC/PKCS5Padding")
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(encryptionKey, "AES"), IvParameterSpec(iv))
        val ciphertext = cipher.doFinal(plaintext)

        val timestamp = System.currentTimeMillis() / 1000
        val header = ByteBuffer.allocate(1 + 8).apply {
            put(0x80.toByte())
            putLong(timestamp)
        }.array()

        val signedPart = header + iv + ciphertext
        val hmacTag = hmacSha256(signingKey, signedPart)
        return Base64.getUrlEncoder().encode(signedPart + hmacTag)
    }

    private fun hmacSha256(key: ByteArray, data: ByteArray): ByteArray {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(key, "HmacSHA256"))
        return mac.doFinal(data)
    }

    // -- AES-256-GCM (vault item payloads) ---------------------------------

    fun vaultEncrypt(plaintext: ByteArray, vaultKey: ByteArray): Pair<ByteArray, ByteArray> {
        val nonce = ByteArray(GCM_NONCE_SIZE).also { SecureRandom().nextBytes(it) }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(
            Cipher.ENCRYPT_MODE,
            SecretKeySpec(vaultKey, "AES"),
            GCMParameterSpec(GCM_TAG_BITS, nonce),
        )
        return nonce to cipher.doFinal(plaintext)
    }

    fun vaultDecrypt(nonce: ByteArray, ciphertext: ByteArray, vaultKey: ByteArray): ByteArray {
        return try {
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(
                Cipher.DECRYPT_MODE,
                SecretKeySpec(vaultKey, "AES"),
                GCMParameterSpec(GCM_TAG_BITS, nonce),
            )
            cipher.doFinal(ciphertext)
        } catch (e: Exception) {
            throw VaultTamperedOrWrongKey(
                "Vault item failed authentication (wrong password or corrupted data).", e
            )
        }
    }

    // -- whole-file convenience -------------------------------------------

    data class UnlockedKeys(val rootKey: ByteArray, val financeKey: ByteArray)

    fun unlock(password: String, salt: ByteArray): UnlockedKeys {
        val rootKey = deriveRootKey(password, salt)
        return UnlockedKeys(rootKey, financeKeyFromRoot(rootKey))
    }

    /** Decrypts a full portable file's bytes ([salt][fernet token]) as written by
     * finance_app.security.crypto.encrypt_file. */
    fun decryptFile(fileBytes: ByteArray, password: String): Pair<UnlockedKeys, ByteArray> {
        val salt = fileBytes.copyOfRange(0, SALT_SIZE)
        val token = fileBytes.copyOfRange(SALT_SIZE, fileBytes.size)
        val keys = unlock(password, salt)
        val plaintext = fernetDecrypt(token, keys.financeKey)
        return keys to plaintext
    }
}
