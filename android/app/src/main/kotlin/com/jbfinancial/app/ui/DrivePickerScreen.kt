package com.jbfinancial.app.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.jbfinancial.app.data.DriveFileMeta

@Composable
fun DrivePickerScreen(
    files: List<DriveFileMeta>,
    busy: Boolean,
    errorMessage: String?,
    onFileChosen: (DriveFileMeta) -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize().padding(24.dp)) {
        Text("Choose a file from Google Drive", style = MaterialTheme.typography.titleLarge)
        if (busy) {
            CircularProgressIndicator(modifier = Modifier.padding(top = 16.dp))
        }
        if (errorMessage != null) {
            Text(
                errorMessage,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(top = 16.dp),
            )
        }
        if (!busy && errorMessage == null && files.isEmpty()) {
            Text(
                "No .enc files found on Drive yet. Create one on the desktop app first, then link it there.",
                modifier = Modifier.padding(top = 16.dp),
            )
        }
        LazyColumn(
            modifier = Modifier.padding(top = 16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(files) { file ->
                Text(
                    file.name,
                    style = MaterialTheme.typography.bodyLarge,
                    modifier = Modifier.fillMaxWidth().clickable { onFileChosen(file) }.padding(vertical = 12.dp),
                )
            }
        }
    }
}
