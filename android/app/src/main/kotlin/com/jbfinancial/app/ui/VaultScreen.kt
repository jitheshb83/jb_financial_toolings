package com.jbfinancial.app.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.jbfinancial.app.data.VAULT_FIELD_SCHEMAS
import com.jbfinancial.app.data.VaultItemMeta
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VaultScreen(
    items: List<VaultItemMeta>,
    onAdd: (type: String, title: String, folder: String?, tags: String?, fields: Map<String, String>) -> Unit,
    onUpdate: (id: Long, title: String, folder: String?, tags: String?, fields: Map<String, String>) -> Unit,
    onDelete: (id: Long) -> Unit,
    loadPayload: suspend (Long) -> Map<String, String>,
) {
    var showEditor by remember { mutableStateOf(false) }
    var editingItem by remember { mutableStateOf<VaultItemMeta?>(null) }
    var editingFields by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()

    Scaffold(
        floatingActionButton = {
            FloatingActionButton(onClick = {
                editingItem = null
                editingFields = emptyMap()
                showEditor = true
            }) { Icon(Icons.Default.Add, contentDescription = "Add") }
        },
    ) { padding ->
        LazyColumn(modifier = Modifier.fillMaxSize().padding(padding)) {
            items(items, key = { it.id }) { item ->
                ListItem(
                    headlineContent = { Text(item.title) },
                    supportingContent = { Text(listOfNotNull(item.type, item.folder).joinToString(" · ")) },
                    trailingContent = {
                        Row {
                            IconButton(onClick = {
                                coroutineScope.launch {
                                    val payload = loadPayload(item.id)
                                    val secret = payload["password"] ?: payload.values.firstOrNull()
                                    if (secret != null) copyWithAutoClear(context, item.title, secret)
                                }
                            }) { Icon(Icons.Default.ContentCopy, contentDescription = "Copy secret") }
                            IconButton(onClick = { onDelete(item.id) }) {
                                Icon(Icons.Default.Delete, contentDescription = "Delete")
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 4.dp).clickable {
                        coroutineScope.launch {
                            editingFields = loadPayload(item.id)
                            editingItem = item
                            showEditor = true
                        }
                    },
                )
            }
        }
    }

    if (showEditor) {
        VaultItemEditorDialog(
            initialType = editingItem?.type ?: "login",
            initialTitle = editingItem?.title ?: "",
            initialFolder = editingItem?.folder ?: "",
            initialTags = editingItem?.tags ?: "",
            initialFields = editingFields,
            onDismiss = { showEditor = false },
            onSave = { type, title, folder, tags, fields ->
                val current = editingItem
                if (current == null) {
                    onAdd(type, title, folder.ifBlank { null }, tags.ifBlank { null }, fields)
                } else {
                    onUpdate(current.id, title, folder.ifBlank { null }, tags.ifBlank { null }, fields)
                }
                showEditor = false
            },
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun VaultItemEditorDialog(
    initialType: String,
    initialTitle: String,
    initialFolder: String,
    initialTags: String,
    initialFields: Map<String, String>,
    onDismiss: () -> Unit,
    onSave: (type: String, title: String, folder: String, tags: String, fields: Map<String, String>) -> Unit,
) {
    var type by remember { mutableStateOf(initialType) }
    var title by remember { mutableStateOf(initialTitle) }
    var folder by remember { mutableStateOf(initialFolder) }
    var tags by remember { mutableStateOf(initialTags) }
    var fieldValues by remember { mutableStateOf(initialFields) }
    var typeMenuExpanded by remember { mutableStateOf(false) }

    LaunchedEffect(type) {
        // Reset fields not part of the new type's schema when switching type.
        val allowedKeys = VAULT_FIELD_SCHEMAS[type]?.map { it.first }.orEmpty().toSet()
        fieldValues = fieldValues.filterKeys { it in allowedKeys }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (initialTitle.isEmpty()) "Add Vault Item" else "Edit Vault Item") },
        text = {
            Column {
                ExposedDropdownMenuBox(expanded = typeMenuExpanded, onExpandedChange = { typeMenuExpanded = it }) {
                    OutlinedTextField(
                        value = type,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("Type") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = typeMenuExpanded) },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    DropdownMenu(expanded = typeMenuExpanded, onDismissRequest = { typeMenuExpanded = false }) {
                        VAULT_FIELD_SCHEMAS.keys.forEach { option ->
                            DropdownMenuItem(text = { Text(option) }, onClick = {
                                type = option
                                typeMenuExpanded = false
                            })
                        }
                    }
                }
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("Title") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                )
                OutlinedTextField(
                    value = folder,
                    onValueChange = { folder = it },
                    label = { Text("Folder") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                )
                OutlinedTextField(
                    value = tags,
                    onValueChange = { tags = it },
                    label = { Text("Tags") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                )
                VAULT_FIELD_SCHEMAS[type].orEmpty().forEach { (key, label) ->
                    OutlinedTextField(
                        value = fieldValues[key] ?: "",
                        onValueChange = { fieldValues = fieldValues + (key to it) },
                        label = { Text(label) },
                        visualTransformation = if (key == "password") {
                            androidx.compose.ui.text.input.PasswordVisualTransformation()
                        } else {
                            androidx.compose.ui.text.input.VisualTransformation.None
                        },
                        modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                    )
                }
            }
        },
        confirmButton = {
            Button(onClick = { onSave(type, title, folder, tags, fieldValues) }, enabled = title.isNotBlank()) {
                Text("Save")
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
