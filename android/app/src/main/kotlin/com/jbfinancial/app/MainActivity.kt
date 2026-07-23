package com.jbfinancial.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.foundation.layout.fillMaxSize
import com.google.android.gms.auth.api.signin.GoogleSignIn
import com.google.android.gms.common.api.ApiException
import com.jbfinancial.app.ui.AppViewModel
import com.jbfinancial.app.ui.DrivePickerScreen
import com.jbfinancial.app.ui.MainScreen
import com.jbfinancial.app.ui.PickFileScreen
import com.jbfinancial.app.ui.Screen
import com.jbfinancial.app.ui.UnlockScreen

class MainActivity : ComponentActivity() {
    private val viewModel: AppViewModel by viewModels()

    private val pickFileLauncher = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        uri?.let { viewModel.onFilePicked(it) }
    }

    private val driveSignInLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        val task = GoogleSignIn.getSignedInAccountFromIntent(result.data)
        try {
            val account = task.getResult(ApiException::class.java)
            viewModel.onDriveSignInResult(account)
        } catch (e: ApiException) {
            viewModel.onDriveSignInFailed(e.message ?: "Google sign-in failed.")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    val uiState by viewModel.uiState.collectAsState()

                    when (uiState.screen) {
                        Screen.PickFile -> PickFileScreen(
                            onPickFile = { pickFileLauncher.launch(arrayOf("*/*")) },
                            onSignInWithDrive = { driveSignInLauncher.launch(viewModel.driveSignInIntent) },
                        )
                        Screen.DrivePicker -> DrivePickerScreen(
                            files = uiState.driveFiles,
                            busy = uiState.busy,
                            errorMessage = uiState.errorMessage,
                            onFileChosen = { file -> viewModel.onDriveFileChosen(file) },
                        )
                        Screen.Unlock -> UnlockScreen(
                            fileName = uiState.fileDisplayName,
                            busy = uiState.busy,
                            errorMessage = uiState.errorMessage,
                            onUnlock = { password -> viewModel.unlock(password) },
                            onPickDifferentFile = { viewModel.pickDifferentFile() },
                        )
                        Screen.Main -> MainScreen(uiState = uiState, viewModel = viewModel)
                    }
                }
            }
        }
    }

    override fun onStop() {
        super.onStop()
        // Auto-lock whenever the app leaves the foreground, mirroring the
        // desktop app's idle-timeout auto-lock.
        viewModel.lock()
    }
}
