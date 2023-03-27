import os
import time
import datetime
import random
import numpy as np
import json

# https://moz.com/top-500/download?table=top500Domains
with open('sites.txt') as s:
    sites = [a.strip() for a in s.readlines()]

doh_providers = [
    "https://dns.google/dns-query",
    "https://cloudflare-dns.com/dns-query",
    "https://dns.quad9.net/dns-query",
    "https://unfiltered.adguard-dns.com/dns-query",
    "https://doh.cleanbrowsing.org/doh/security-filter/",
    "https://freedns.controld.com/p0",
]

current1 = random.choice(sites)
current2 = random.choice(sites)

a1 = '192.168.2.149:5555' # machine with DoH in Chrome configured
a2 = '192.168.2.217:5555' # infected machine with DoH in Chrome

os.system(f'adb connect {a1}')
os.system(f'adb connect {a2}')

os.system(f'adb -s {a1} root')
os.system(f'adb -s {a2} root')

doh_provider = random.choice(doh_providers)


def clear_dns_cache(host):
    os.system(f'adb -s {host} shell am force-stop com.android.chrome')
    os.system(f'adb -s {host} shell ndc resolver clearnetdns wlan0')
    os.system(f'adb -s {host} shell ndc resolver clearnetdns wifi_eth')

    
def change_doh(host, template):
    os.system(f'adb -s {host} shell am force-stop com.android.chrome')
    os.system(f'adb -s {host} pull "/data/data/com.android.chrome/app_chrome/Local State" ./state.json')

    with open("state.json") as f:
      state = json.load(f)

    state["dns_over_https"] = {
        "mode": "secure",
        "templates": template,
    }

    with open("state.json", "w") as f:
      json.dump(state, f)

    os.system(f'adb -s {host} push ./state.json "/data/data/com.android.chrome/app_chrome/Local State"')
    os.system(f'adb -s {host} shell am start -n "com.android.chrome/com.google.android.apps.chrome.Main"')
    time.sleep(2)


def clear_data(host):
    os.system(f'adb -s {host} shell am force-stop com.android.chrome')
    os.system(f'adb -s {host} shell pm clear com.android.chrome')

    os.system(f'adb -s {host} shell am set-debug-app --persistent com.android.chrome')
    os.system(f"""adb -s {host} shell 'echo "chrome --disable-fre --no-default-browser-check --no-first-run" > /data/local/tmp/chrome-command-line'""")
    os.system(f'adb -s {host} shell am start -n "com.android.chrome/com.google.android.apps.chrome.Main"')


def log(f, text):
    dt = datetime.datetime.now().strftime("%d-%b-%Y (%H:%M:%S.%f)")
    f.write(f"{dt}: {text}\n")
    print(f"LOG: {text}")

browsing = False
pages = 0

with open("exp.log", "w") as logf:
  log(logf, "Starting")
  log(logf, f"Clear dns cache on {a1} and {a2}")
  clear_dns_cache(a1)
  clear_dns_cache(a2)
  log(logf, f"Clear Chrome data for {a1} and {a2}")
  clear_data(a1)
  clear_data(a2)

  time.sleep(10)

  doh_provider = random.choice(doh_providers)
  log(logf, f"Change DoH provider on {a1} to {doh_provider}")
  change_doh(a1, doh_provider) 
  log(logf, f"Change DoH provider on {a2} to {doh_provider}")
  change_doh(a2, doh_provider) 

  while True:
    delay = np.random.poisson(10, 1)
    time.sleep(delay[0])
    current1 = random.choice(sites)
    current2 = random.choice(sites)
    if not browsing:
        log(logf, "Continue browsing on {a1} and {a2}")
        browsing = True
    if random.random() < 0.5:
        log(logf, f"Open {current1} on {a1}")
        os.system(f'adb -s {a1} shell input keyevent 82')
        os.system(f'adb -s {a1} shell am start -a "android.intent.action.VIEW" -d "https://{current1}" --es "com.android.browser.application_id" "com.android.browser"')
    else:
        log(logf, f"Open {current2} on {a2}")
        os.system(f'adb -s {a2} shell input keyevent 82')
        os.system(f'adb -s {a2} shell am start -a "android.intent.action.VIEW" -d "https://{current2}" --es "com.android.browser.application_id" "com.android.browser"')
