# Proxmox CPU Governor for Home Assistant

A custom Home Assistant integration that allows selecting the CPU governor of a Proxmox VE host directly from Home Assistant.

Currently supported governors:

- `performance`
- `powersave`

The integration exposes a Home Assistant `select` entity that updates the governor over SSH.

## Requirements

The integration assumes the Proxmox host is already prepared.

You must:

- create a dedicated user (recommended: `homeassistant`)
- install the helper script
- configure SSH key authentication
- allow the user to execute the helper script without password

The integration does **not** modify the Proxmox host automatically.

---

# Installation

## 1. Create the helper script

Create:

```bash
/usr/local/sbin/ha-cpu-governor
```

Contents:

```bash
#!/bin/bash

set -e

case "$1" in
    performance|powersave)
        governor="$1"
        ;;
    *)
        echo "Usage: $0 {performance|powersave}"
        exit 1
        ;;
esac

for policy in /sys/devices/system/cpu/cpufreq/policy*; do
    echo "$governor" > "$policy/scaling_governor"
done
```

Make it executable:

```bash
chmod +x /usr/local/sbin/ha-cpu-governor
```

---

## 2. Create the Home Assistant user

Example:

```bash
useradd -m homeassistant
```

---

## 3. Configure sudo

Add:

```text
homeassistant ALL=(root) NOPASSWD: /usr/local/sbin/ha-cpu-governor
```

using:

```bash
visudo
```

---

## 4. Configure SSH keys

Generate an SSH key on Home Assistant.

Copy the public key:

```bash
ssh-copy-id homeassistant@YOUR_PROXMOX_HOST
```

Verify:

```bash
ssh homeassistant@YOUR_PROXMOX_HOST
```

---

## 5. Test manually

Run:

```bash
ssh homeassistant@YOUR_PROXMOX_HOST \
"sudo -n /usr/local/sbin/ha-cpu-governor performance"
```

Then:

```bash
cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor
```

Expected:

```text
performance
```

Repeat with:

```bash
powersave
```

---

## Home Assistant

Install through HACS as a custom repository.

Add the integration from:

Settings → Devices & Services → Add Integration

Configure:

- Host
- Port
- Username
- Private SSH key

After setup, a `select` entity will be created to switch between available CPU governors.
