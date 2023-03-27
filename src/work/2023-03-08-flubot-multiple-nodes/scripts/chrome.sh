adb connect $1:5555
adb -s $1:5555 root
adb -s $1:5555 shell settings put global verifier_verify_adb_installs 0
adb -s $1:5555 install chrome.apk
