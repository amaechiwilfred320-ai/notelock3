[app]
# NoteLock Android application settings
title = NoteLock
package.name = notelock
package.domain = org.notelock

source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,txt

version = 1.0
requirements = python3,kivy,reportlab,pyjnius

orientation = portrait
fullscreen = 0

# App icon (keep notelock_icon.png beside this file)
icon.filename = ./notelock_icon.png

# Microphone and internet access for speech recognition
android.permissions = RECORD_AUDIO,INTERNET

android.minapi = 23
android.api = 35
android.archs = arm64-v8a,armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
