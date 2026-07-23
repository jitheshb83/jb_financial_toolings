package com.jbfinancial.app.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.jbfinancial.app.R

@Composable
fun PickFileScreen(onPickFile: () -> Unit, onSignInWithDrive: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Image(
            painter = painterResource(R.drawable.logo_full),
            contentDescription = null,
            modifier = Modifier.width(100.dp).padding(bottom = 16.dp),
        )
        Text("Open your finance data file", style = MaterialTheme.typography.titleLarge)
        Text(
            "Pick the .enc file created by the desktop app — from local storage, " +
                "from the Google Drive app if it's synced there, or sign in to open it " +
                "directly from Google Drive.",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(top = 8.dp, bottom = 24.dp),
        )
        Button(onClick = onPickFile, modifier = Modifier.fillMaxWidth()) { Text("Choose file") }
        Button(
            onClick = onSignInWithDrive,
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
        ) { Text("Sign in with Google Drive") }
    }
}

@Composable
fun UnlockScreen(
    fileName: String?,
    busy: Boolean,
    errorMessage: String?,
    onUnlock: (String) -> Unit,
    onPickDifferentFile: () -> Unit,
) {
    var password by remember { mutableStateOf("") }

    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Image(
            painter = painterResource(R.drawable.logo_full),
            contentDescription = null,
            modifier = Modifier.width(100.dp).padding(bottom = 16.dp),
        )
        Text("Unlock", style = MaterialTheme.typography.titleLarge)
        if (fileName != null) {
            Text(fileName, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 4.dp))
        }
        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("Master password") },
            visualTransformation = PasswordVisualTransformation(),
            singleLine = true,
            modifier = Modifier.fillMaxWidth().padding(top = 16.dp, bottom = 8.dp),
        )
        if (errorMessage != null) {
            Text(errorMessage, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(bottom = 8.dp))
        }
        Button(
            onClick = { onUnlock(password) },
            enabled = !busy && password.isNotEmpty(),
            modifier = Modifier.fillMaxWidth(),
        ) {
            if (busy) {
                CircularProgressIndicator(modifier = Modifier.padding(end = 8.dp))
            }
            Text("Unlock")
        }
        TextButton(onClick = onPickDifferentFile, modifier = Modifier.padding(top = 8.dp)) {
            Text("Choose a different file")
        }
    }
}
