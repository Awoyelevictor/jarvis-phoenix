package com.phoenix.ultron
import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.pm.PackageManager
import android.media.AudioManager
import android.os.Bundle
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient

class MainActivity : Activity() {
 private lateinit var webView: WebView
 @SuppressLint("SetJavaScriptEnabled")
 override fun onCreate(savedInstanceState: Bundle?) {
  super.onCreate(savedInstanceState)
  window.statusBarColor = android.graphics.Color.rgb(8,9,12)
  window.navigationBarColor = android.graphics.Color.rgb(8,9,12)
  setVolumeControlStream(AudioManager.STREAM_MUSIC)
  if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED)
   requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO),410)
  webView = WebView(this)
  webView.setBackgroundColor(android.graphics.Color.rgb(8,9,12))
  webView.settings.javaScriptEnabled = true
  webView.settings.domStorageEnabled = true
  webView.settings.mediaPlaybackRequiresUserGesture = false
  webView.settings.allowFileAccess = false
  webView.webViewClient = WebViewClient()
  webView.webChromeClient = object : WebChromeClient() {
   override fun onPermissionRequest(request: PermissionRequest) {
    runOnUiThread {
     if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
      val allowed = request.resources.filter { it == PermissionRequest.RESOURCE_AUDIO_CAPTURE }.toTypedArray()
      if (allowed.isNotEmpty()) request.grant(allowed) else request.deny()
     } else request.deny()
    }
   }
  }
  setContentView(webView)
  webView.loadUrl("https://ultron-ai-5rkc.onrender.com")
 }
 private fun restoreMediaRoute() {
  val audio = getSystemService(AUDIO_SERVICE) as AudioManager
  audio.mode = AudioManager.MODE_NORMAL
  @Suppress("DEPRECATION") audio.isSpeakerphoneOn = false
 }
 override fun onResume() { super.onResume(); restoreMediaRoute() }
 override fun onPause() { restoreMediaRoute(); super.onPause() }
 @Deprecated("Deprecated in Java")
 override fun onBackPressed() { if (::webView.isInitialized && webView.canGoBack()) webView.goBack() else super.onBackPressed() }
 override fun onDestroy() { if (::webView.isInitialized) webView.destroy(); super.onDestroy() }
}