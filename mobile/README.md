# Tarapath Mobile App

This directory contains the React Native Expo mobile app for Tarapath. 

## Setup Instructions

Run these commands in your terminal to set up the Expo app from scratch (if not already done):

```bash
npx create-expo-app mobile --template blank
cd mobile
npx expo install expo-camera expo-location expo-image-picker react-native-webview
npm install @react-navigation/native @react-navigation/stack
npx expo install react-native-screens react-native-safe-area-context @react-native-async-storage/async-storage
```

*Note: Replace the default `App.js` with the one provided, and copy the `screens/` and `config.js` into your new `mobile/` project folder.*

## Finding Your PC's Local IP Address

To test the app locally, your mobile phone needs to connect to the FastAPI server running on your Windows PC. Both must be on the same WiFi network.

1. Open PowerShell on Windows and run: `ipconfig`
2. Look for the adapter you are currently using (e.g., "Wireless LAN adapter Wi-Fi")
3. Find the `IPv4 Address`. It will look something like `192.168.1.5` or `10.0.0.12`.
4. Open `mobile/config.js` and change `SERVER_URL` to match that IP:
   ```javascript
   export const SERVER_URL = 'http://192.168.1.5:8000';
   ```

## How to Test End-to-End on Windows

1. **Start the API Server**
   Open PowerShell and run the provided script from the project root:
   ```powershell
   .\start_api.ps1
   ```
   *Make sure `uvicorn` starts without errors and is listening on `0.0.0.0:8000`.*

2. **Start the Expo Server**
   Open another terminal, go to the `mobile` folder, and start Expo:
   ```bash
   cd mobile
   npx expo start
   ```

3. **Run on your Phone**
   - Download the **Expo Go** app on your iOS or Android device.
   - Scan the QR code shown in your terminal (using your Camera on iOS, or from within the Expo Go app on Android).
   - Once it loads, grant Camera and Location permissions.

4. **Take a test shot**
   - Step outside and point the camera at the stars.
   - Wait 3 seconds for the capture, and the API will plate-solve your photo and give you an estimated location!

## Known Limitation to Watch Out For

**Network/Firewall issues:** Windows Defender Firewall often blocks incoming connections on port 8000 by default. If the app is stuck on "Triangulating position..." and times out, you must allow Python/uvicorn through the Windows Firewall, or temporarily disable the public/private firewall for testing. 

Also, if you are using an iPhone on a local network, sometimes iOS blocks HTTP traffic (App Transport Security) or requires "Local Network" permission to be granted in settings.
