# External runtime-loading fixture

`Avocado.glb` is the Microsoft Avocado model distributed by Khronos glTF Sample Assets.
License: CC0 1.0 Universal. The GLB is unmodified; the app normalizes its displayed size.

- Source: https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/Avocado
- License: https://creativecommons.org/publicdomain/zero/1.0/
- Credit: Microsoft (2017).

This directory is outside Unity's Assets/StreamingAssets/Resources folders. The model
must NOT be compiled into the APK. Copy it into the installed app's Imports/model.glb
after installation. Loading should work with Wi-Fi disabled and no external service.
