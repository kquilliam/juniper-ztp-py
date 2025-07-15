#!/usr/bin/python

"""
juniper_public.py

Zero Touch Provisioning (ZTP) automation script for Juniper devices.
This script connects to a Juniper device, gathers its identity and model information,
communicates with Netbox to validate, locate, and fetch rendered device configuration,
optionally upgrades the device software, then applies new configuration after a pre-check.
All relevant actions and failures are logged via syslog, and event-options are activated/deactivated
for ZTP retry/continuity depending on the result.
"""

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
    """
    Progress callback for SW.install() operations.
    Logs software installation progress to stdout and syslog.
    Args:
        dev (Device): Junos Device instance.
        report (str): Installation progress status.
    """
    print("host: {}, report: {}".format(dev.hostname, report))
    jcs.syslog("interact.notice", "ZTP - host: {}, report: {}".format(dev.hostname, report))

def check_configuration(config_data):
    """
    Loads candidate configuration and performs a commit-check on the device (does not apply changes).
    Args:
        config_data (str): Configuration in text format to load and check.
    Returns:
        bool: True if commit check passes, False otherwise.
    """
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
    """
    Loads and commits the provided configuration on the device.
    Args:
        config_data (str): Configuration in text format to load and apply.
    Returns:
        bool: True if commit succeeds, False otherwise.
    """
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

def reactivate_event(post_reboot=False):
    """
    Reactivates the event-options to generate another ZTP event after a delay, enabling retries.
    The log/syslog message differs depending on whether this is after a successful reboot or an error/retry.
    Args:
        post_reboot (bool): If True, indicates called after successful software upgrade & reboot. Default False.
    Returns:
        bool: True if activation succeeds, False otherwise.
    """
    dev = Device()
    dev.open()
    try:
        if post_reboot:
            msg = "ZTP - Reactivating Event Option after successful software upgrade so it will run after the reboot"
            print("Reactivating Event Option after successful software upgrade so it will run after the reboot")
        else:
            msg = "ZTP - Reactivating Event Option for ZTP. Will try again in 60 seconds."
            print("Reactivating Event Option for ZTP. Will try again in 60 seconds.")
        jcs.syslog("interact.notice", msg)
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

# Initial device connection to retrieve facts and identify this device in Netbox
with Device() as dev:
    serialnumber = (dev.facts['serialnumber'])
    model = (dev.facts['model'])
    version = (dev.facts['version'])
    print(f"This device's serial number: {serialnumber}")
    print(f"This device's model: {model}")
    print(f"This device's version: {version}")
    jcs.syslog("interact.notice", f"ZTP - This device's serial number: {serialnumber}")
    jcs.syslog("interact.notice", f"ZTP - This device's model: {model}")
    jcs.syslog("interact.notice", f"ZTP - This device's version: {version}")

# Variables to store package, VM host flag, and force_host flag for SW upgrade
pkg = ""
vmhost = False
force_host = False

# Compose Netbox API URL using serial number
url = "https://<netbox>/api/dcim/devices"
find_serial_url = f"{url}/?serial={serialnumber}"

# Static API Token for Netbox (for automation purposes)
nb_token = "YOUR_API_TOKEN_HERE"
headers = {
    "Authorization": f"Token {nb_token}"
}
print(f"Searching for Device in Netbox using Serial Number: {serialnumber}")
jcs.syslog("interact.notice", f"ZTP - Searching for Device in Netbox using Serial Number: {serialnumber}")

# Query Netbox for device by serial number
try:
    nb_device_response = requests.get(find_serial_url, headers=headers, verify=True)
except requests.exceptions.RequestException as e:
    print(f"Error making request: {e}")
    jcs.syslog("interact.notice", f"ZTP - Error making request: {e}")
    reactivate_event()
    sys.exit()

response_json = nb_device_response.json()
results = response_json.get("results", [])

# Check if device with matching serial exists in Netbox
if results:
    print("Device With This Serial Number Located in Netbox")
    jcs.syslog("interact.notice", "ZTP - Device With This Serial Number Located in Netbox")
    first_result = results[0]
    device_name = first_result.get("name")
    device_id = first_result.get("id")
    device_model = first_result.get("device_type", {}).get("model")
    print(f"Device Name: {device_name}")
    jcs.syslog("interact.notice", f"ZTP - Device Name: {device_name}")
    print(f"Netbox Device ID: {device_id}")
    jcs.syslog("interact.notice", f"ZTP - Netbox Device ID: {device_id}")
    print(f"Device Model: {device_model}")
    jcs.syslog("interact.notice", f"ZTP - Device Model: {device_model}")
else:
    print("No device found. Verify that this device's serial number is in Netbox.")
    jcs.syslog("interact.notice", "ZTP - No device found. Verify that this device's serial number is in Netbox.")
    reactivate_event() 
    exit()

# Ensure device model in Netbox matches actual device
if model != device_model:
    print(f"Device model in Netbox ({device_model}) does not match this device ({model}).")
    jcs.syslog("interact.notice", f"ZTP - Device model in Netbox ({device_model}) does not match this device ({model}).")
    reactivate_event()
    exit()

# Parse config_context to get upgrade and provisioning info from Netbox
for entry in results:
    config_context = entry.get("config_context", {})
    pkg = config_context.get("pkg")
    target_version = config_context.get("target_version")
    if config_context.get("vmhost") == True:
        vmhost = True
    if config_context.get("force_host") == True:
        force_host = True
    if pkg and target_version:
        pkg = pkg.replace("{target_version}", target_version)
        print(f"Located Target Version for this model: {target_version}")
        jcs.syslog("interact.notice", f"ZTP - Located Target Version for this model: {target_version}")
    else:
        print("No Target Version for this model found")
        jcs.syslog("interact.notice", "ZTP - No Target Version for this model found")
        reactivate_event()
        exit()

# Deactivate ZTP event-options to avoid repeated triggering during provisioning/run
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

# Upgrade device OS if not running target version
if version != target_version:
    pkg_ = f"http://<file-server>/juniper/firmware/{pkg}"
    print(f"Device needs to be upgraded to {target_version}")
    jcs.syslog("interact.notice", f"ZTP - Device needs to be upgraded to {target_version}")

    with Device() as dev:
        sw = SW(dev)
        print(f"Installing {target_version} for {model}")
        jcs.syslog("interact.notice", f"ZTP - Installing {pkg} for {model}")
        try:
            if vmhost:
                print("Device is a VM host. Installing VM host package.")
                jcs.syslog("interact.notice", "ZTP - Device is a VMhost. Installing VMhost package.")
                ok = sw.install(package=pkg_, no_copy=True, vmhost=True, progress=myprogress)
            if force_host:
                print("Device is a VM host. Forcing VM host package.")
                jcs.syslog("interact.notice", "Device is a VM host. Forcing VM host package.")
                ok = sw.install(package=pkg_, no_copy=True, force_host=True, progress=myprogress)
            else:
                ok = sw.install(package=pkg_, no_copy=True, progress=myprogress)
        except Exception as err:
            print("Error installing software: {}".format(err))
            jcs.syslog("interact.notice", f"ZTP - Error installing software: {err}")
            ok = False
        if ok is True:
            print("Rebooting device")
            jcs.syslog("interact.notice", "ZTP - Rebooting device")
            if vmhost:
                sw.reboot(in_min=0, vmhost=True)
            else:
                sw.reboot(in_min=0)
            time.sleep(30)
            reactivate_event(post_reboot=True)
            exit()
        else:
            print("Unable to install software")
            jcs.syslog("interact.notice", "ZTP - Unable to Install Software")
            reactivate_event()
            exit()
else:
    print(f"Device is already running version {version}. Continuing.")
    jcs.syslog("interact.notice", f"ZTP - Device is already running version {version}. Continuing.")

# Fetch rendered configuration from Netbox
find_config_url = f"{url}/{device_id}/render-config/?format=txt"

try:
    nb_config_response = requests.post(find_config_url, headers=headers, verify=True)
    nb_config_response.raise_for_status()
except requests.exceptions.HTTPError as e:
    print(f"HTTP Error: {e}")
    print("Verify device has a valid, rendered config in Netbox")
    jcs.syslog("interact.notice", f"ZTP - HTTP Error: {e}")
    jcs.syslog("interace.notice", "ZTP - Verify device has a valid, rendered config in Netbox")
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
        print("ZTP Process Completed. Device is ready for deployment.")
        jcs.syslog("interact.notice", "ZTP - Configuration applied successfully")
        jcs.syslog("interact.notice", "ZTP - ZTP Process Completed. Device is ready for deployment.")
    else:
        print("Failed to apply configuration")
        jcs.syslog("interact.notice", "ZTP - Failed to apply configuration.")
else:
    print("Configuration check failed")
    jcs.syslog("interact.notice", "ZTP - Configuration check failed, Check rendered configuration in Netbox for errors.")
    reactivate_event()
    exit()
