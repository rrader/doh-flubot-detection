apk=flubot.apk

# disable Play Protect
adb -s 192.168.2.217:5555 root
adb -s 192.168.2.217:5555 shell settings put global package_verifier_user_consent 1

pkg=$(aapt dump badging $apk|awk -F" " '/package/ {print $2}'|awk -F"'" '/name=/ {print $2}')
act=$(aapt dump badging $apk|awk -F" " '/launchable-activity/ {print $2}'|awk -F"'" '/name=/ {print $2}')

adb -s 192.168.2.217:5555 shell am kill $pkg
adb -s 192.168.2.217:5555 shell pm disable $pkg
adb -s 192.168.2.217:5555 shell pm hide $pkg
adb -s 192.168.2.217:5555 shell settings reset secure enabled_accessibility_services com.tencent.mobileqq/Flash:com.tencent.mobileqq/com.tencent.mobileqq.pcdf91408
