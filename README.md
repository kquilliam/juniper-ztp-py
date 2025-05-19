# Juniper Zero Touch Provisioning (ZTP) Automation

This repository provides an automation solution for Zero Touch Provisioning (ZTP) of Juniper network devices. It consists of:
- `juniper.py` – a Python script automating provisioning, Netbox integration, software upgrade, and configuration.
- `juniper.conf` – a Junos configuration file enabling the required system settings, authentication, events, and automation hooks.

## Overview

This setup enables automated onboarding and provisioning of new Juniper devices in environments managed with [Netbox](https://netbox.readthedocs.io/). When a device boots, it can:
- Self-configure management connectivity
- Fetch authentication and automation settings
- Download and run the provisioning script (`juniper.py`)
- Contact Netbox to retrieve its identity and rendered config
- Upgrade Junos OS if required
- Apply validated configuration
- Log all steps to syslog and facilitate retries for failed operations

---

## File Descriptions

### `juniper.py`

A Python 3 script leveraging [Juniper PyEZ](https://www.juniper.net/documentation/us/en/software/junos-pyez/index.html) to automate initial device provisioning. Main features:

- **Device Identification**: Gathers serial number, model, and OS version from the device.
- **Netbox API Integration**: Contacts Netbox over HTTPS to:
  - Validate the device exists by serial number.
  - Retrieve target OS version and configuration from device context.
  - Fetch rendered configuration to apply.
- **Software Upgrade**: Downloads and upgrades Junos OS using package details from Netbox (if current version doesn't match target).
- **Configuration Validation and Application**:
  - Checks candidate config for errors (commit-check).
  - Applies the configuration on success.
- **Event and Continuity Management**:
  - Deactivates/activates event-options to retry ZTP steps on failure or after reboot.
  - All actions and errors are logged through syslog via `jcs.syslog`.

**Customization Required**:  
API URLs, authentication tokens, and Artifactory credentials are hard-coded for demonstration – these must be secured and updated for actual deployment.

### `juniper.conf`

A Junos configuration fragment that prepares a device for ZTP automation:

- **Authentication**: Sets root (encrypted) password and creates a `ztp` super-user for script execution.
- **Management Connectivity**: Configures VME interface for DHCP to ensure the device can obtain an IP address.
- **Script/Service Enablement**:
  - Enables Python 3 scripts and allows script download via URL.
  - Activates NETCONF and SSH for remote access/automation.
- **Event-Options for Automation**:
  - Periodically triggers events to:
    - Refresh the ZTP script from a provisioning server.
    - Execute `juniper.py` as an event-script on a schedule.
    - Renew DHCP as needed.
- **Syslog**: Configures detailed syslog behavior and destinations for automation visibility.

---

## Usage

1. **Preload Device**:  
   Load `juniper.conf` into a factory-default Juniper device as part of a DHCP option. This sets up networking, users, and event triggers.

2. **Provisioning Script Hosting**:  
   Ensure `juniper.py` is available via HTTP for devices to fetch, e.g., via a local web server referenced in the config.

3. **Netbox Preparation**:  
   Create the matching device record in Netbox with appropriate serial/model/config context—this must include any OS package details for upgrade.

4. **Verify Dependencies**:  
   Device must support Python and have [Juniper PyEZ](https://github.com/Juniper/py-junos-eznc) (and dependencies) installed or available. This is true for most newer Juniper devices out of the box but unsure of the cutoff.

5. **Security Notices**:  
   - Replace demonstration API tokens, device/user credentials, passwords, and URLs with secure values for production.
   - Lock down provisioning hosts and restrict physical access.

---

## Prerequisites

- Out-of-band/management connectivity (DHCP-compatible)
- DHCP server providing option 43 and 66 to retrieve `juniper.conf`
  - Option 43 suboptions: `1:juniper.conf,3:http,5:80`
- Access to Netbox API with relevant token
- HTTP server hosting `juniper.py`
- Correct device records/configuration in Netbox
- Config context in Netbox is linked to the proper device type and is in the following format for an EX4600:
```
{
    "target_version": "21.4R3-S10.13",
    "pkg": "qfx5100/jinstall-host-qfx-5-flex-{target_version}-signed.tgz",
    "force_host": true
}
```
---

## Disclaimer

**Do not use demonstration credentials or tokens in production.**  
Always review, adapt, and secure before deploying this automation in an operational environment.
