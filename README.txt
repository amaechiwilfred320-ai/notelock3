NOTELOCK BUILDOSER KIT

Contents:
- buildozer.spec: Android build configuration with the NoteLock icon configured.
- notelock_icon.png: NoteLock NL icon on a white background.

HOW TO USE
1. Extract this folder.
2. Copy your NoteLock main.py into this same folder.
3. On Linux or WSL, install Buildozer and its Android build dependencies.
4. Open a terminal in this folder and run:

   buildozer android debug

5. When the build succeeds, the APK will be placed in the bin/ folder.

IMPORTANT
- The icon file must remain named notelock_icon.png and stay beside buildozer.spec.
- This kit does not contain main.py. Copy your corrected NoteLock application code into this folder before building.
- Windows desktop speech recognition dependencies should not be added to the Android requirements. Android uses its native speech recognition service.
- A first Android build can take a while and requires internet access to download build dependencies.
