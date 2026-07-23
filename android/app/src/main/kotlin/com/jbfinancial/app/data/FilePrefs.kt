package com.jbfinancial.app.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "file_prefs")
private val LAST_FILE_URI_KEY = stringPreferencesKey("last_file_uri")
private val LAST_DRIVE_FILE_ID_KEY = stringPreferencesKey("last_drive_file_id")
private val LAST_DRIVE_FILE_NAME_KEY = stringPreferencesKey("last_drive_file_name")
private val LAST_SOURCE_KEY = stringPreferencesKey("last_source") // "saf" | "drive"

/** Remembers which encrypted file was last opened — either a SAF Uri
 * (local storage or the Drive app's own document provider) or a file id
 * opened directly through the Drive REST API — so the user only has to
 * pick it once. */
class FilePrefs(private val context: Context) {
    suspend fun getLastFileUri(): String? = context.dataStore.data.first()[LAST_FILE_URI_KEY]

    suspend fun setLastFileUri(uri: String) {
        context.dataStore.edit {
            it[LAST_FILE_URI_KEY] = uri
            it[LAST_SOURCE_KEY] = "saf"
            it.remove(LAST_DRIVE_FILE_ID_KEY)
            it.remove(LAST_DRIVE_FILE_NAME_KEY)
        }
    }

    suspend fun getLastSource(): String? = context.dataStore.data.first()[LAST_SOURCE_KEY]

    suspend fun getLastDriveFile(): Pair<String, String>? {
        val data = context.dataStore.data.first()
        val id = data[LAST_DRIVE_FILE_ID_KEY] ?: return null
        val name = data[LAST_DRIVE_FILE_NAME_KEY] ?: ""
        return id to name
    }

    suspend fun setLastDriveFile(fileId: String, name: String) {
        context.dataStore.edit {
            it[LAST_DRIVE_FILE_ID_KEY] = fileId
            it[LAST_DRIVE_FILE_NAME_KEY] = name
            it[LAST_SOURCE_KEY] = "drive"
            it.remove(LAST_FILE_URI_KEY)
        }
    }

    suspend fun clear() {
        context.dataStore.edit {
            it.remove(LAST_FILE_URI_KEY)
            it.remove(LAST_DRIVE_FILE_ID_KEY)
            it.remove(LAST_DRIVE_FILE_NAME_KEY)
            it.remove(LAST_SOURCE_KEY)
        }
    }
}
