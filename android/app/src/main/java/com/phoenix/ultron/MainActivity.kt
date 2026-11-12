package com.phoenix.ultron

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.pm.PackageManager
import android.graphics.Color
import android.media.AudioManager
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.webkit.CookieManager
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity : Activity() {
    private lateinit var webView: WebView
    private lateinit var root: FrameLayout
    private lateinit var diagnosticPanel: LinearLayout
    private lateinit var diagnosticText: TextView
    private var hasLoadError = false

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.rgb(8, 9, 12)
        window.navigationBarColor = Color.rgb(8, 9, 12)
        setVolumeControlStream(AudioManager.STREAM_MUSIC)

        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 410)
        }

        root = FrameLayout(this)
        root.setBackgroundColor(Color.rgb(8, 9, 12))

        webView = WebView(this)
        webView.setBackgroundColor(Color.rgb(8, 9, 12))
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            mediaPlaybackRequiresUserGesture = false
            allowFileAccess = false
            loadsImagesAutomatically = true
            javaScriptCanOpenWindowsAutomatically = true
            setSupportMultipleWindows(false)
            loadWithOverviewMode = true
            useWideViewPort = true
            cacheMode = android.webkit.WebSettings.LOAD_DEFAULT
            mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
        }
        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true)

        diagnosticPanel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 18, 24, 18)
            setBackgroundColor(Color.rgb(30, 12, 15))
            visibility = View.GONE
        }
        diagnosticText = TextView(this).apply {
            setTextColor(Color.WHITE)
            textSize = 13f
            text = "ULTRON diagnostic"
        }
        val retryButton = Button(this).apply {
            text = "RETRY ULTRON"
            setOnClickListener {
                hasLoadError = false
                showDiagnostic("Retrying ULTRON…")
                webView.reload()
            }
        }
        diagnosticPanel.addView(diagnosticText)
        diagnosticPanel.addView(retryButton)

        root.addView(webView, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ))
        root.addView(diagnosticPanel, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.WRAP_CONTENT,
            Gravity.BOTTOM
        ))
        setContentView(root)

        webView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                super.onPageStarted(view, url, favicon)
                if (!hasLoadError) showDiagnostic("Loading ULTRON…")
            }

            override fun onPageCommitVisible(view: WebView?, url: String?) {
                super.onPageCommitVisible(view, url)
                if (!hasLoadError) diagnosticPanel.visibility = View.GONE
            }

            override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
                super.onReceivedError(view, request, error)
                if (request?.isForMainFrame == true) {
                    hasLoadError = true
                    showDiagnostic("Page load failed. Code: ${error?.errorCode}\n${error?.description ?: "Unknown WebView error"}\n\nURL: ${request.url}")
                }
            }

            override fun onReceivedHttpError(view: WebView?, request: WebResourceRequest?, response: android.webkit.WebResourceResponse?) {
                super.onReceivedHttpError(view, request, response)
                if (request?.isForMainFrame == true) {
                    hasLoadError = true
                    showDiagnostic("Server returned HTTP ${response?.statusCode ?: "error"} ${response?.reasonPhrase ?: ""}\n\nURL: ${request.url}")
                }
            }

            override fun onRenderProcessGone(view: WebView?, detail: android.webkit.RenderProcessGoneDetail?): Boolean {
                hasLoadError = true
                showDiagnostic("Android System WebView stopped unexpectedly. Crashed: ${detail?.didCrash() == true}. Please tap RETRY ULTRON.")
                return true
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest) {
                runOnUiThread {
                    if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                        val allowed = request.resources.filter {
                            it == PermissionRequest.RESOURCE_AUDIO_CAPTURE
                        }.toTypedArray()
                        if (allowed.isNotEmpty()) request.grant(allowed) else request.deny()
                    } else {
                        request.deny()
                    }
                }
            }

            override fun onConsoleMessage(message: android.webkit.ConsoleMessage): Boolean {
                if (message.messageLevel() == android.webkit.ConsoleMessage.MessageLevel.ERROR) {
                    runOnUiThread {
                        hasLoadError = true
                        showDiagnostic(
                            "ULTRON page JavaScript error:\n${message.message()}\nLine: ${message.lineNumber()}\nSource: ${message.sourceId()}"
                        )
                    }
                }
                return true
            }
        }

        webView.loadUrl("https://ultron-ai-5rkc.onrender.com")
    }

    private fun showDiagnostic(message: String) {
        if (!::diagnosticPanel.isInitialized) return
        diagnosticText.text = message
        diagnosticPanel.visibility = View.VISIBLE
    }

    private fun restoreMediaRoute() {
        val audio = getSystemService(AUDIO_SERVICE) as AudioManager
        audio.mode = AudioManager.MODE_NORMAL
        @Suppress("DEPRECATION")
        audio.isSpeakerphoneOn = false
    }

    override fun onResume() {
        super.onResume()
        restoreMediaRoute()
        if (::webView.isInitialized) webView.onResume()
    }

    override fun onPause() {
        restoreMediaRoute()
        if (::webView.isInitialized) webView.onPause()
        super.onPause()
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (::webView.isInitialized && webView.canGoBack()) webView.goBack()
        else super.onBackPressed()
    }

    override fun onDestroy() {
        if (::webView.isInitialized) {
            webView.stopLoading()
            webView.destroy()
        }
        super.onDestroy()
    }
}