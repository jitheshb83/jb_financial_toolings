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

/** Remembers the SAF Uri of the last-opened encrypted file, so the user only
 * has to pick it once (the granted permission is persisted separately via
 * SafEncryptedFileStore.persistPermission). */
class FilePrefs(private val context: Context) {
    suspend fun getLastFileUri(): String? = context.dataStore.data.first()[LAST_FILE_URI_KEY]

    suspend fun setLastFileUri(uri: String) {
        context.dataStore.edit { it[LAST_FILE_URI_KEY] = uri }
    }

    suspend fun clear() {
        context.dataStore.edit { it.remove(LAST_FILE_URI_KEY) }
    }
}
