package com.jbfinancial.app.data

import android.accounts.Account
import android.content.Context
import android.content.Intent
import com.google.android.gms.auth.GoogleAuthUtil
import com.google.android.gms.auth.api.signin.GoogleSignIn
import com.google.android.gms.auth.api.signin.GoogleSignInAccount
import com.google.android.gms.auth.api.signin.GoogleSignInClient
import com.google.android.gms.auth.api.signin.GoogleSignInOptions
import com.google.android.gms.common.api.ApiException
import com.google.android.gms.common.api.Scope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

private const val DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"

/** Handles Google sign-in scoped narrowly to drive.file (files this app
 * itself creates/opens) and mints short-lived OAuth2 bearer tokens for
 * DriveApiClient's REST calls. Mirrors finance_app/sync/drive_auth.py's
 * role on desktop; Android's GoogleSignIn/GoogleAuthUtil stack handles
 * token storage/refresh itself, so there's no separate keychain-equivalent
 * needed here. */
class DriveAuthManager(private val context: Context) {

    val signInClient: GoogleSignInClient by lazy {
        val options = GoogleSignInOptions.Builder(GoogleSignInOptions.DEFAULT_SIGN_IN)
            .requestScopes(Scope(DRIVE_FILE_SCOPE))
            .build()
        GoogleSignIn.getClient(context, options)
    }

    val signInIntent: Intent
        get() = signInClient.signInIntent

    fun getLastSignedInAccount(): GoogleSignInAccount? =
        GoogleSignIn.getLastSignedInAccount(context)

    fun handleSignInResult(data: Intent?): GoogleSignInAccount {
        val task = GoogleSignIn.getSignedInAccountFromIntent(data)
        return task.getResult(ApiException::class.java)
    }

    suspend fun getAccessToken(account: GoogleSignInAccount): String = withContext(Dispatchers.IO) {
        val androidAccount: Account = account.account
            ?: throw IllegalStateException("Signed-in Google account has no underlying Account")
        GoogleAuthUtil.getToken(context, androidAccount, "oauth2:$DRIVE_FILE_SCOPE")
    }

    fun signOut(onComplete: () -> Unit) {
        signInClient.signOut().addOnCompleteListener { onComplete() }
    }
}
