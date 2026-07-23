package com.jbfinancial.app.data

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.URLEncoder

data class DriveFileMeta(
    val id: String,
    val name: String,
    val modifiedTime: String,
    val headRevisionId: String,
)

private const val FILES_URL = "https://www.googleapis.com/drive/v3/files"
private const val UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
private val OCTET_STREAM = "application/octet-stream".toMediaType()
private val JSON = "application/json; charset=utf-8".toMediaType()
private const val META_FIELDS = "id,name,modifiedTime,headRevisionId"
private const val FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

// Matches finance_app/sync/drive_client.py's FOLDER_NAME — both apps store
// their files in the same dedicated, visible Drive folder.
const val DRIVE_APP_FOLDER_NAME = "JB Financial"

class DriveApiException(message: String) : IOException(message)

/** Minimal Drive v3 REST client scoped to drive.file access — only the
 * handful of calls this app needs (list/get/download/create/update),
 * hand-rolled over OkHttp rather than pulling in the official (heavy,
 * semi-abandoned) google-api-client-android + google-api-services-drive
 * stack for what's really ~5 endpoints. */
class DriveApiClient(private val accessTokenProvider: suspend () -> String) {

    companion object {
        // Shared across all instances — each OkHttpClient owns its own connection
        // pool and dispatcher thread pool, so reusing one avoids paying for a new
        // pool every time a DriveApiClient gets (re)built (e.g. on sign-in).
        private val sharedClient = OkHttpClient()
    }

    private val client = sharedClient

    private suspend fun authorizedRequest(builder: Request.Builder): Request {
        val token = accessTokenProvider()
        return builder.header("Authorization", "Bearer $token").build()
    }

    /** Finds this app's dedicated Drive folder (DRIVE_APP_FOLDER_NAME),
     * creating it if it doesn't exist yet — a single predictable, visible
     * place in the user's My Drive where both apps' files live. */
    suspend fun findOrCreateAppFolder(): String {
        val query = URLEncoder.encode(
            "name = '$DRIVE_APP_FOLDER_NAME' and mimeType = '$FOLDER_MIME_TYPE' and trashed = false",
            "UTF-8",
        )
        val url = "$FILES_URL?q=$query&fields=${URLEncoder.encode("files(id,name)", "UTF-8")}&spaces=drive"
        val request = authorizedRequest(Request.Builder().url(url))
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw DriveApiException("findOrCreateAppFolder failed: ${response.code} ${response.body?.string()}")
            }
            val files = JSONObject(response.body!!.string()).optJSONArray("files") ?: JSONArray()
            if (files.length() > 0) return files.getJSONObject(0).getString("id")
        }

        val metadata = JSONObject().put("name", DRIVE_APP_FOLDER_NAME).put("mimeType", FOLDER_MIME_TYPE)
        val createRequest = authorizedRequest(
            Request.Builder()
                .url("$FILES_URL?fields=id")
                .post(metadata.toString().toRequestBody(JSON))
        )
        client.newCall(createRequest).execute().use { response ->
            if (!response.isSuccessful) {
                throw DriveApiException("findOrCreateAppFolder (create) failed: ${response.code} ${response.body?.string()}")
            }
            return JSONObject(response.body!!.string()).getString("id")
        }
    }

    suspend fun listEncFiles(folderId: String? = null): List<DriveFileMeta> {
        var q = "name contains '.enc' and trashed = false"
        if (folderId != null) q += " and '$folderId' in parents"
        val query = URLEncoder.encode(q, "UTF-8")
        val fields = URLEncoder.encode("files($META_FIELDS)", "UTF-8")
        val url = "$FILES_URL?q=$query&fields=$fields&spaces=drive"
        val request = authorizedRequest(Request.Builder().url(url))
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw DriveApiException("listEncFiles failed: ${response.code} ${response.body?.string()}")
            }
            val json = JSONObject(response.body!!.string())
            val files = json.optJSONArray("files") ?: JSONArray()
            return (0 until files.length()).map { i -> parseMeta(files.getJSONObject(i)) }
        }
    }

    suspend fun getMetadata(fileId: String): DriveFileMeta {
        val fields = URLEncoder.encode(META_FIELDS, "UTF-8")
        val url = "$FILES_URL/$fileId?fields=$fields"
        val request = authorizedRequest(Request.Builder().url(url))
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw DriveApiException("getMetadata failed: ${response.code} ${response.body?.string()}")
            }
            return parseMeta(JSONObject(response.body!!.string()))
        }
    }

    suspend fun downloadFile(fileId: String): ByteArray {
        val request = authorizedRequest(Request.Builder().url("$FILES_URL/$fileId?alt=media"))
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) throw DriveApiException("downloadFile failed: ${response.code}")
            return response.body!!.bytes()
        }
    }

    suspend fun createFile(name: String, bytes: ByteArray): String {
        val metadata = JSONObject().put("name", name).toString()
        val body = MultipartBody.Builder()
            .setType("multipart/related".toMediaType())
            .addPart(metadata.toRequestBody(JSON))
            .addPart(bytes.toRequestBody(OCTET_STREAM))
            .build()
        val request = authorizedRequest(
            Request.Builder().url("$UPLOAD_URL?uploadType=multipart").post(body)
        )
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw DriveApiException("createFile failed: ${response.code} ${response.body?.string()}")
            }
            return JSONObject(response.body!!.string()).getString("id")
        }
    }

    /** Replaces an existing Drive file's content in place — never creates a
     * duplicate. Requests headRevisionId directly in the response so callers
     * don't need a separate getMetadata() round-trip just to learn it. */
    suspend fun updateFile(fileId: String, bytes: ByteArray): String {
        val body = bytes.toRequestBody(OCTET_STREAM)
        val request = authorizedRequest(
            Request.Builder().url("$UPLOAD_URL/$fileId?uploadType=media&fields=headRevisionId").patch(body)
        )
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw DriveApiException("updateFile failed: ${response.code} ${response.body?.string()}")
            }
            return JSONObject(response.body!!.string()).getString("headRevisionId")
        }
    }

    private fun parseMeta(obj: JSONObject): DriveFileMeta = DriveFileMeta(
        id = obj.getString("id"),
        name = obj.getString("name"),
        modifiedTime = obj.optString("modifiedTime"),
        headRevisionId = obj.optString("headRevisionId"),
    )
}
