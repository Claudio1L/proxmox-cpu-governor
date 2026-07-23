DOMAIN = "proxmox_cpu_governor"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PRIVATE_KEY = "private_key"

DEFAULT_PORT = 22
DEFAULT_USERNAME = "homeassistant"
DEFAULT_PRIVATE_KEY = "/root/.ssh/id_ed25519"

GOVERNOR_PERFORMANCE = "performance"
GOVERNOR_POWERSAVE = "powersave"

SUPPORTED_GOVERNORS = [
    GOVERNOR_PERFORMANCE,
    GOVERNOR_POWERSAVE,
]
