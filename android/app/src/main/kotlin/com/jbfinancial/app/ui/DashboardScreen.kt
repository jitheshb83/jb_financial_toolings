package com.jbfinancial.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.jbfinancial.app.data.NetWorthPoint
import java.text.NumberFormat
import java.util.Locale

@Composable
fun DashboardScreen(baseCurrency: String, history: List<NetWorthPoint>) {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("Net Worth", style = MaterialTheme.typography.titleLarge)

        val latest = history.lastOrNull()
        val formatter = remember(baseCurrency) {
            NumberFormat.getCurrencyInstance(Locale.US).apply {
                currency = runCatching { java.util.Currency.getInstance(baseCurrency) }.getOrNull()
                    ?: currency
            }
        }
        Text(
            text = latest?.let { formatter.format(it.totalValue) } ?: "No data yet",
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.padding(vertical = 8.dp),
        )
        Text(
            "This reflects the desktop app's most recent snapshot — recorded there, read-only here.",
            style = MaterialTheme.typography.bodySmall,
        )

        if (history.size >= 2) {
            NetWorthSparkline(
                history = history,
                modifier = Modifier.fillMaxWidth().height(120.dp).padding(vertical = 16.dp),
            )
        }

        HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))

        LazyColumn(modifier = Modifier.fillMaxSize()) {
            items(history.reversed()) { point ->
                ListItem(
                    headlineContent = { Text(point.date) },
                    trailingContent = { Text(formatter.format(point.totalValue)) },
                )
            }
        }
    }
}

@Composable
private fun NetWorthSparkline(history: List<NetWorthPoint>, modifier: Modifier = Modifier) {
    val values = history.map { it.totalValue }
    val min = values.min()
    val max = values.max()
    val range = (max - min).takeIf { it != 0.0 } ?: 1.0
    val color = MaterialTheme.colorScheme.primary

    Canvas(modifier = modifier) {
        val stepX = size.width / (values.size - 1).coerceAtLeast(1)
        val points = values.mapIndexed { index, value ->
            val x = index * stepX
            val y = size.height - ((value - min) / range * size.height).toFloat()
            androidx.compose.ui.geometry.Offset(x, y)
        }
        for (i in 0 until points.size - 1) {
            drawLine(color = color, start = points[i], end = points[i + 1], strokeWidth = 4f)
        }
    }
}
