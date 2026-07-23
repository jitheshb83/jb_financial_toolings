package com.jbfinancial.app.ui

import android.app.Application
import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.google.android.gms.auth.api.signin.GoogleSignInAccount
import com.jbfinancial.app.data.DriveApiClient
import com.jbfinancial.app.data.DriveAuthManager
import com.jbfinancial.app.data.DriveEncryptedFileStore
import com.jbfinancial.app.data.DriveFileMeta
import com.jbfinancial.app.data.EncryptedFileStore
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
    data object DrivePicker : Screen
    data object Unlock : Screen
    data object Main : Screen
}

enum class FileSource { SAF, DRIVE }

data class AppUiState(
    val screen: Screen = Screen.PickFile,
    val fileSource: FileSource? = null,
    val fileUri: Uri? = null,
    val driveFileId: String? = null,
    val fileDisplayName: String? = null,
    val driveFiles: List<DriveFileMeta> = emptyList(),
    val busy: Boolean = false,
    val errorMessage: String? = null,
    val vaultItems: List<VaultItemMeta> = emptyList(),
    val baseCurrency: String = "USD",
    val netWorthHistory: List<NetWorthPoint> = emptyList(),
)

class AppViewModel(application: Application) : AndroidViewModel(application) {
    private val filePrefs = FilePrefs(application)
    private val driveAuthManager = DriveAuthManager(application)
    private var driveApiClient: DriveApiClient? = null
    private var repository: FinanceRepository? = null

    private val _uiState = MutableStateFlow(AppUiState())
    val uiState: StateFlow<AppUiState> = _uiState.asStateFlow()

    val driveSignInIntent: Intent
        get() = driveAuthManager.signInIntent

    init {
        viewModelScope.launch {
            when (filePrefs.getLastSource()) {
                "drive" -> {
                    val (fileId, name) = filePrefs.getLastDriveFile() ?: return@launch
                    val account = driveAuthManager.getLastSignedInAccount()
                    if (account == null) {
                        // Signed-out since last use — fall back to PickFile so the
                        // user can re-authenticate rather than crashing on unlock.
                        return@launch
                    }
                    driveApiClient = buildDriveClient(account)
                    _uiState.value = _uiState.value.copy(
                        fileSource = FileSource.DRIVE,
                        driveFileId = fileId,
                        fileDisplayName = name,
                        screen = Screen.Unlock,
                    )
                }
                else -> {
                    filePrefs.getLastFileUri()?.let { uriString ->
                        val uri = Uri.parse(uriString)
                        _uiState.value = _uiState.value.copy(
                            fileSource = FileSource.SAF,
                            fileUri = uri,
                            fileDisplayName = queryDisplayName(uri),
                            screen = Screen.Unlock,
                        )
                    }
                }
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

    private fun buildDriveClient(account: GoogleSignInAccount): DriveApiClient =
        DriveApiClient(accessTokenProvider = { driveAuthManager.getAccessToken(account) })

    fun onFilePicked(uri: Uri) {
        SafEncryptedFileStore.persistPermission(getApplication(), uri)
        viewModelScope.launch {
            filePrefs.setLastFileUri(uri.toString())
            _uiState.value = _uiState.value.copy(
                fileSource = FileSource.SAF,
                fileUri = uri,
                driveFileId = null,
                fileDisplayName = queryDisplayName(uri),
                screen = Screen.Unlock,
                errorMessage = null,
            )
        }
    }

    fun onDriveSignInResult(account: GoogleSignInAccount) {
        driveApiClient = buildDriveClient(account)
        _uiState.value = _uiState.value.copy(screen = Screen.DrivePicker, busy = true, errorMessage = null)
        viewModelScope.launch {
            runCatching {
                // Both apps store their files in the same dedicated, visible
                // "JB Financial" Drive folder rather than searching the whole
                // drive.file-scoped space.
                val folderId = driveApiClient!!.findOrCreateAppFolder()
                driveApiClient!!.listEncFiles(folderId)
            }
                .onSuccess { files -> _uiState.value = _uiState.value.copy(driveFiles = files, busy = false) }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        busy = false,
                        errorMessage = e.message ?: "Could not list Google Drive files.",
                    )
                }
        }
    }

    fun onDriveSignInFailed(message: String) {
        _uiState.value = _uiState.value.copy(errorMessage = message)
    }

    fun onDriveFileChosen(file: DriveFileMeta) {
        viewModelScope.launch {
            filePrefs.setLastDriveFile(file.id, file.name)
            _uiState.value = _uiState.value.copy(
                fileSource = FileSource.DRIVE,
                driveFileId = file.id,
                fileUri = null,
                fileDisplayName = file.name,
                screen = Screen.Unlock,
                errorMessage = null,
            )
        }
    }

    fun pickDifferentFile() {
        _uiState.value = _uiState.value.copy(screen = Screen.PickFile, errorMessage = null)
    }

    fun unlock(password: String) {
        val source = _uiState.value.fileSource ?: return
        val app: Application = getApplication()
        _uiState.value = _uiState.value.copy(busy = true, errorMessage = null)
        viewModelScope.launch {
            try {
                val tempDb = File(app.cacheDir, "working_${System.currentTimeMillis()}.sqlite3")
                val store: EncryptedFileStore = when (source) {
                    FileSource.SAF -> SafEncryptedFileStore(app, _uiState.value.fileUri!!)
                    FileSource.DRIVE -> DriveEncryptedFileStore(driveApiClient!!, _uiState.value.driveFileId!!)
                }
                val repo = FinanceRepository(store, tempDb)
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
                fileSource = _uiState.value.fileSource,
                fileUri = _uiState.value.fileUri,
                driveFileId = _uiState.value.driveFileId,
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
