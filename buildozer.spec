
[app]
icon.filename = %(source.dir)s/icon.png
title = Jumpy Bird
package.name = flappybirdhd
package.domain = org.mahin
version = 1.0

source.dir = .
source.include_exts = py
source.exclude_dirs = .github, .buildozer, bin

requirements = python3,kivy==2.3.0

orientation = portrait
fullscreen = 1

android.permissions =
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True

p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
