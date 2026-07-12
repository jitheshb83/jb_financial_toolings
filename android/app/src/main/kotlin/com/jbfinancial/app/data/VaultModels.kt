package com.jbfinancial.app.data

data class VaultItemMeta(
    val id: Long,
    val type: String,
    val title: String,
    val folder: String?,
    val tags: String?,
    val updatedAt: String,
)

/** type -> ordered (key, label) pairs, mirrors ui/dialogs/vault_item_dialog.py FIELD_SCHEMAS. */
val VAULT_FIELD_SCHEMAS: Map<String, List<Pair<String, String>>> = mapOf(
    "login" to listOf("username" to "Username", "password" to "Password", "url" to "URL", "notes" to "Notes"),
    "secure_note" to listOf("notes" to "Note"),
    "card" to listOf(
        "cardholder" to "Cardholder name",
        "number" to "Card number",
        "expiry" to "Expiry (MM/YY)",
        "cvv" to "CVV",
        "notes" to "Notes",
    ),
    "identity" to listOf(
        "full_name" to "Full name",
        "id_number" to "ID number",
        "address" to "Address",
        "notes" to "Notes",
    ),
)

data class NetWorthPoint(val date: String, val totalValue: Double)
