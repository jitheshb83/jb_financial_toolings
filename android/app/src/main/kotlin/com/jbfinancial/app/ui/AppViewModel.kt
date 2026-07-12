package com.jbfinancial.app.ui

import android.app.Application
import android.net.Uri
import android.provider.OpenableColumns
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.jbfinancial.app.data.FilePrefs
import com.jbfinancial.app.data.FinanceRepository
import com.jbfinancial.app.data.NetWorthPoint
import com.jbfinancial.app.data.SafEncryptedFileStore
import com.jbfinancial.app.data.VaultItemMeta
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

sealed interface Screen {
    data object PickFile : Screen
    data object Unlock : Screen
    data object Main : Screen
}

data class AppUiState(
    val screen: Screen = Screen.PickFile,
    val fileUri: Uri? = null,
    val fileDisplayName: String? = null,
    val busy: Boolean = false,
    val errorMessage: String? = null,
    val vaultItems: List<VaultItemMeta> = emptyList(),
    val baseCurrency: String = "USD",
    val netWorthHistory: List<NetWorthPoint> = emptyList(),
)

class AppViewModel(application: Application) : AndroidViewModel(application) {
    private val filePrefs = FilePrefs(application)
    private var repository: FinanceRepository? = null

    private val _uiState = MutableStateFlow(AppUiState())
    val uiState: StateFlow<AppUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            filePrefs.getLastFileUri()?.let { uriString ->
                val uri = Uri.parse(uriString)
                _uiState.value = _uiState.value.copy(
                    fileUri = uri,
                    fileDisplayName = queryDisplayName(uri),
                    screen = Screen.Unlock,
                )
            }
        }
    }

    private suspend fun queryDisplayName(uri: Uri): String? = withContext(Dispatchers.IO) {
        runCatching {
            getApplication<Application>().contentResolver
                .query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
                ?.use { cursor -> if (cursor.moveToFirst()) cursor.getString(0) else null }
        }.getOrNull()
    }

    fun onFilePicked(uri: Uri) {
        SafEncryptedFileStore.persistPermission(getApplication(), uri)
        viewModelScope.launch {
            filePrefs.setLastFileUri(uri.toString())
            _uiState.value = _uiState.value.copy(
                fileUri = uri,
                fileDisplayName = queryDisplayName(uri),
                screen = Screen.Unlock,
                errorMessage = null,
            )
        }
    }

    fun pickDifferentFile() {
        _uiState.value = _uiState.value.copy(screen = Screen.PickFile, errorMessage = null)
    }

    fun unlock(password: String) {
        val uri = _uiState.value.fileUri ?: return
        val app: Application = getApplication()
        _uiState.value = _uiState.value.copy(busy = true, errorMessage = null)
        viewModelScope.launch {
            try {
                val tempDb = File(app.cacheDir, "working_${System.currentTimeMillis()}.sqlite3")
                val repo = FinanceRepository(SafEncryptedFileStore(app, uri), tempDb)
                repo.unlock(password)
                repository = repo
                _uiState.value = _uiState.value.copy(screen = Screen.Main, busy = false)
                refreshVault()
                refreshDashboard()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    busy = false,
                    errorMessage = e.message ?: "Could not unlock this file.",
                )
            }
        }
    }

    fun lock() {
        viewModelScope.launch {
            repository?.lock()
            repository = null
            _uiState.value = AppUiState(
                fileUri = _uiState.value.fileUri,
                fileDisplayName = _uiState.value.fileDisplayName,
                screen = Screen.Unlock,
            )
        }
    }

    fun refreshVault() {
        val repo = repository ?: return
        viewModelScope.launch {
            runCatching { repo.listVaultItems() }
                .onSuccess { items -> _uiState.value = _uiState.value.copy(vaultItems = items) }
                .onFailure { e -> _uiState.value = _uiState.value.copy(errorMessage = e.message) }
        }
    }

    fun refreshDashboard() {
        val repo = repository ?: return
        viewModelScope.launch {
            runCatching {
                val currency = repo.getBaseCurrency()
                val history = repo.netWorthHistory()
                currency to history
            }.onSuccess { (currency, history) ->
                _uiState.value = _uiState.value.copy(baseCurrency = currency, netWorthHistory = history)
            }.onFailure { e -> _uiState.value = _uiState.value.copy(errorMessage = e.message) }
        }
    }

    suspend fun getVaultPayload(id: Long): Map<String, String> =
        repository?.getVaultPayload(id) ?: emptyMap()

    fun addVaultItem(type: String, title: String, folder: String?, tags: String?, fields: Map<String, String>) {
        val repo = repository ?: return
        viewModelScope.launch {
            runCatching { repo.createVaultItem(type, title, folder, tags, fields) }
                .onSuccess { refreshVault() }
                .onFailure { e -> _uiState.value = _uiState.value.copy(errorMessage = e.message) }
        }
    }

    fun updateVaultItem(id: Long, title: String, folder: String?, tags: String?, fields: Map<String, String>) {
        val repo = repository ?: return
        viewModelScope.launch {
            runCatching { repo.updateVaultItem(id, title, folder, tags, fields) }
                .onSuccess { refreshVault() }
                .onFailure { e -> _uiState.value = _uiState.value.copy(errorMessage = e.message) }
        }
    }

    fun deleteVaultItem(id: Long) {
        val repo = repository ?: return
        viewModelScope.launch {
            runCatching { repo.deleteVaultItem(id) }
                .onSuccess { refreshVault() }
                .onFailure { e -> _uiState.value = _uiState.value.copy(errorMessage = e.message) }
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(errorMessage = null)
    }
}
