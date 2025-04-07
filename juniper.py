#!/usr/bin/python

from jnpr.junos import Device
from jnpr.junos.utils.config import Config
from jnpr.junos.utils.sw import SW
from jnpr.junos.exception import ConfigLoadError
from jnpr.junos.exception import ConnectError
from jnpr.junos.exception import CommitError
from jnpr.junos.exception import LockError
import jcs
import requests
import time
import sys
def myprogress(dev, report):
    print("host: {}, report: {}".format(dev.hostname, report))

def check_configuration(config_data):
    dev = Device()
    dev.open()
    try:
        jcs.syslog("interact.notice", "ZTP - Performing Commit Check")
        print("Performing Commit Check")
        with Config(dev) as cu:
            cu.lock()
            cu.load(config_data, format="text", overwrite=True)
            cu.commit_check()
            cu.unlock()
        return True
    except LockError as err:
        print("Error locking configuration: {}".format(err))
        jcs.syslog("interact.notice", "ZTP - Error locking configuration: {}".format(err))
        reactivate_event()
        return False
    except ConfigLoadError as err:
        print("Error loading configuration: {}".format(err))
        jcs.syslog("interact.notice", "ZTP - Error loading configuration: {}".format(err))
        reactivate_event()
        return False

def apply_configuration(config_data):
    dev = Device()
    dev.open()
    try:
        with Config(dev) as cu:
            cu.lock()
            cu.load(config_data, format="text", overwrite=True, comment='Committing Configuration Retrieved from Netbox')
            cu.commit()
            cu.unlock()
        return True
    except LockError as err:
        print("Error locking configuration: {}".format(err))
        jcs.syslog("interact.notice", "ZTP - Error locking configuration: {}".format(err))
        reactivate_event()
        return False
    except (ConfigLoadError, CommitError) as err:
        print("Error applying configuration: {}".format(err))
        jcs.syslog("interact.notice", "ZTP - Error applying configuration: {}".format(err))
        reactivate_event()
        return False

def reactivate_event():
    dev = Device()
    dev.open()
    try:
        print("Reactivating Event Option for ZTP. Will try again in 60 seconds.")
        jcs.syslog("interact.notice", "ZTP - Reactivating Event Option for ZTP. Will try again in 60 seconds.")
        with Config(dev) as cu:
            cu.lock()
            cu.load("activate event-options generate-event ZTP")
            cu.commit()
            cu.unlock()
        return True
    except LockError as err:
        print("Error locking configuration: {}".format(err))
        jcs.syslog("interact.notice", "ZTP - Error locking configuration: {}".format(err))
        return False
    except (ConfigLoadError, CommitError) as err:
        print("Error activating configuration: {}".format(err))
        jcs.syslog("interact.notice", "ZTP - Error activating configuration: {}".format(err))
        return False

with Device() as dev:
    serialnumber = (dev.facts['serialnumber'])
    model = (dev.facts['model'])
    version = (dev.facts['version'])
    print(f"Located Device Serial Number: {serialnumber} on {model}")
    jcs.syslog("interact.notice", f"ZTP - Located Device Serial Number: {serialnumber} on {model}")

if "QFX5120" in model:
    pkg = "junos-install-qfx-arm-64-22.4R3-S6.5.tgz"
    vmhost = True
    
if "EX2300-C" in model:
    pkg = "junos-arm-32-23.4R2-S4.11.tgz"
    vmhost = False

if "EX3400" in model:
    pkg = "junos-arm-32-23.4R2-S4.11.tgz"
    vmhost = False

if "EX4100" in model:
    if "EX4100-F-12" in model:
        pkg = "junos-install-ex-arm-64-23.4R2-S4.11.tgz"
    else:
        if "EX4100-H" in model:
            pkg = "junos-install-ex-arm-64-24.4R1.10.tgz"
        else:
            pkg = "junos-install-ex-arm-64-23.4R2-S4.11.tgz"
    vmhost = False

if "EX4300" in model:
    if "MP" in model:
        pkg = "jinstall-host-ex-4300mp-x86-64-23.4R2-S4.11-secure-signed.tgz"
    else:
        pkg = "jinstall-ex-4300-21.4R3-S10.9-signed.tgz"
    vmhost = False

if "EX4400" in model:
    pkg = "junos-install-ex-x86-64-23.4R2-S4.11.tgz"
    vmhost = False

if "EX4600" in model:
    pkg = "jinstall-host-ex-4600-21.4R3-S10.13-signed.tgz"
    vmhost = True

try:
    pkg
except NameError:
    print("No software defined for this model. Exiting.")
    jcs.syslog("interact.notice", "ZTP - No software defined for this model. Exiting.")
    sys.exit()

with Device() as dev:
    cu = Config(dev)
    print("Deactivating Event Option to Keep From Overrunning")
    jcs.syslog("interact.notice", "ZTP - Deactivating Event Option to Keep From Overrunning")
    try:
        cu.lock()
        cu.load("deactivate event-options generate-event ZTP")
        cu.commit()
    except LockError as err:
        print("Error locking configuration: {}".format(err))
        jcs.syslog("interact.notice", "ZTP - Error locking configuration: {}".format(err))
        reactivate_event()
        dev.close()
        sys.exit()
    except ConfigLoadError as err:
        print("Error loading configuration: {}".format(err))
        jcs.syslog("interact.notice", "ZTP - Error loading configuration: {}".format(err))
        reactivate_event()
        dev.close()
        sys.exit()

if version not in pkg:
    remote_path = "<web_server>"
    pkg = remote_path + "/" + pkg
    
    with Device() as dev:
        sw = SW(dev)
        print(f"Installing {pkg} for {model}")
        jcs.syslog("interact.notice", f"ZTP - Installing {pkg} for {model}")
        if vmhost:
            ok = sw.install(package=pkg, no_copy=True, vmhost=True, progress=myprogress)
        else:
            ok = sw.install(package=pkg, progress=myprogress )
        if ok:
            time.sleep(30)
            cu = Config(dev)
            cu.lock()
            cu.load("activate event-options generate-event ZTP")
            cu.commit()
            cu.unlock()
            print("Rebooting device")
            if vmhost:
                sw.reboot(in_min=0,vmhost=True)
            else:
                sw.reboot(in_min=0)
            exit()
        else:
            msg = "Unable to install software"
            reactivate_event()
            exit()
else:
    print(f"Device is already running version {version}. Continuing.")
    jcs.syslog("interact.notice", f"ZTP - Device is already running version {version}. Continuing.")

url = "<netbox_url>/api/dcim/devices"
find_serial_url = f"{url}/?serial={serialnumber}"

nb_token = "<netbox_token>"
headers = {
    "Authorization": f"Token {nb_token}"
}
# Make the GET request with the headers containing your auth token
print(f"Searching for Device in Netbox using Serial Number: {serialnumber}")
jcs.syslog("interact.notice", f"ZTP - Searching for Device in Netbox using Serial Number: {serialnumber}")

try:
    nb_device_response = requests.get(find_serial_url, headers=headers)
except requests.exceptions.RequestException as e:
    print(f"Error making request: {e}")
    jcs.syslog("interact.notice", f"ZTP - Error making request: {e}")
    reactivate_event()
    sys.exit()

# Check if the request was successful
#if nb_device_response.status_code == 200:
    # Process successful response
data = nb_device_response.json()
response_json = nb_device_response.json()
results = response_json.get("results", [])

if results:
    print("Device With This Serial Number Located in Netbox")
    jcs.syslog("interact.notice", "ZTP - Device With This Serial Number Located in Netbox")
    # Assuming you want to get the first result
    first_result = results[0]
    # Now you can work with the first result
    device_name = first_result.get("name")
    device_id = first_result.get("id")
    print(f"Device Name: {device_name}")
    jcs.syslog("interact.notice", f"ZTP - Device Name: {device_name}")
    print(f"Netbox Device ID: {device_id}")
    jcs.syslog("interact.notice", f"ZTP - Netbox Device ID: {device_id}")
else:
    print("No device found. Verify that this device's serial number is in Netbox.")
    jcs.syslog("interact.notice", "ZTP - No device found. Verify that this device's serial number is in Netbox.")
    reactivate_event() 
    exit()

find_config_url = f"{url}/{device_id}/render-config/?format=txt"

try:
    nb_config_response = requests.post(find_config_url, headers=headers)
    nb_config_response.raise_for_status()
except requests.exceptions.HTTPError as e:
    print(f"HTTP Error: {e}")
    jcs.syslog("interact.notice", f"ZTP - HTTP Error: {e}")
    reactivate_event()
    sys.exit()
except requests.exceptions.RequestException as e:
    print(f"Error making request: {e}")
    jcs.syslog("interact.notice", f"ZTP - Error making request: {e}")
    reactivate_event()
    sys.exit()

print("Device Configuration Retrieved")
jcs.syslog("interact.notice", "ZTP - Device Configuration Retrieved")
config_data = nb_config_response.text
if check_configuration(config_data):
    print("Configuration is valid")
    jcs.syslog("interact.notice", "ZTP - Configuration is valid")
    if apply_configuration(config_data):
        print("Configuration applied successfully")
        jcs.syslog("interact.notice", "ZTP - Configuration applied successfully")
    else:
        print("Failed to apply configuration")
        jcs.syslog("interact.notice", "ZTP - Failed to apply configuration")
else:
    print("Configuration check failed")
    jcs.syslog("interact.notice", "ZTP - Configuration check failed, Check rendered configuration in Netbox for errors.")
    reactivate_event()
    exit()
