# Juniper Zero Touch Provisioning (ZTP) Automation

This repository demonstrates an automation solution for Zero Touch Provisioning (ZTP) of Juniper network devices. It provides public-ready example files you can adapt for secure production deployment.

**Note:** All example files use the placeholders `<file-server>` (for firmware/script hosting) and `<netbox>` (for your Netbox API endpoint).  
For your deployment, use Find & Replace to substitute these with your actual server addresses.
## Provided Example Files

- `juniper_public.py` – A Python script automating device provisioning, Netbox integration, software upgrade, and configuration **with all private info removed**.
- `juniper_public.conf` – A Junos configuration file to enable required system settings, authentication, events, and automation hooks (with no secrets or internal IPs).

## How It Works

This setup allows automated onboarding and provisioning of new Juniper devices in Netbox-managed environments:
- Device boots, configures management via DHCP, and fetches credentials & automation settings from config.
- Device downloads and runs the provisioning script.
- The script queries Netbox over HTTPS via the `<netbox>` API endpoint (must be set by operator).
- Retrieves target OS version, configuration, and upgrade info.
- Optionally upgrades Junos OS if required.
- Applies rendered configuration to the device.
- Logs all steps to syslog and supports automated retries.

---

## File Descriptions

### `juniper_public.py`

A Python 3 script (see file for full implementation) automating the following tasks:
- **Device Identification**: Gathers serial, model, and OS info.
- **Netbox API Integration**:  
    - Looks up the device by serial number.
    - Retrieves config context for software image and settings.
    - Fetches rendered configuration.
- **Software Upgrade**:  
    - Upgrades Junos OS using URLs constructed from config context.
    - Supports VM host and force_host upgrade parameters.
- **Configuration Application**:  
    - Validates new configuration (commit-check) before applying.
    - Handles errors and logs outcomes.
- **Security**:  
    - No internal tokens, real URLs, or credentials included.
    - By default, certificate validation (`verify=True`) is **enabled** for all API calls.

### `juniper_public.conf`

A Junos configuration sample for ZTP automation:
- Sets up root authentication (encrypted password must be added by the operator).
- Creates a super-user for provisioning.
- Configures management via DHCP.
- Enables Python 3 scripts and URL-based script fetching.
- Schedules event scripts to automate retries and script updates.
- Updates the script using an HTTP URL (replace with your own HTTP/HTTPS location).
- Uses documentation/example name-servers and no real secrets/IPs.

---

## Usage

1. **Edit and Deploy Configuration**:  
   - Before use, replace placeholder URLs, tokens, and credentials in the example files with your own secure/environment-specific data.
   - Load the configuration (juniper_public.conf) to new Juniper devices.
   - Host the provisioning script (juniper_public.py) on a reachable HTTP or HTTPS server (see `<file-server>` placeholder in the files).

2. **Prepare Netbox**:  
   - Deploy your own Netbox instance (see [Netbox documentation](https://netbox.readthedocs.io/)).
   - Add device records with appropriate configuration context.

3. **Verify Dependencies**:  
   Ensure your device supports:
   - Python 3
   - [Juniper PyEZ](https://github.com/Juniper/py-junos-eznc) (`jnpr.junos`)
   - `requests` and `jcs` Python libraries

4. **Security Notice**:  
   - Do **not** use demonstration, default, or placeholder secrets in production.
   - Provide strong and unique credentials, enable API certificate validation, and restrict device and script access.

---

## Example Netbox Config Context

Use a context like below in your Netbox device record (replace versions and filenames with valid data):

```
{
    "target_version": "21.4R3-S10.13",
    "pkg": "qfx5100/jinstall-host-qfx-5-flex-{target_version}-signed.tgz",
    "force_host": true,
    "vmhost": true
}
```

---

## Disclaimer

These files are for demonstration purposes only and are scrubbed of all private data. You must supply your own secure credentials, endpoints, and deployment-specific values before production use.
