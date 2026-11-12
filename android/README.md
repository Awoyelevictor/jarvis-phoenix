# ULTRON Android

A lightweight native Android WebView shell for the existing ULTRON service.

- Package: `com.phoenix.ultron`
- App label: ULTRON
- Loads the existing hosted ULTRON interface.
- Requests microphone permission and forwards WebView audio capture permission.
- Keeps Android in normal audio mode and exposes the media/music volume stream.
- Includes an original vector launcher icon with a red-lit metallic machine face.

## Build

Run the **Build ULTRON Android APK** workflow in GitHub Actions. Download the
`ULTRON-debug-APK` artifact and install `app-debug.apk` on Android.

This first build is an installable debug APK. A signed release APK/AAB can be
configured later for distribution.
