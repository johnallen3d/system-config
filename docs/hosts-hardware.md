# Host hardware

Collected 2026-11-06. Config: `hosts/<name>.nix`.

|              | Mac (`m4-mbp`)          | Omarchy (mini PC)     | Miller (Mac Pro)        | Drummer (Mac Pro)      |
| ------------ | ----------------------- | --------------------- | ----------------------- | ---------------------- |
| Model        | MacBook Pro 14" (2024)  | Getorli AT103         | Mac Pro (Late 2013)     | Mac Pro (Late 2013)    |
| CPU          | M4 Pro, 12-core (8P+4E) | i5-13420H, 8C/12T     | Xeon E5-1650 v2, 6C/12T | Xeon E5-1650 v2, 6C/12T |
| GPU          | M4 Pro 16-core          | Intel UHD (iGPU)      | 2× FirePro D500, 3 GB   | 2× FirePro D500, 3 GB  |
| Memory       | 48 GB                   | 16 GB                 | 64 GB                   | 64 GB                  |
| Storage      | 1 TB SSD                | 512 GB NVMe           | 2 TB NVMe (OWC)         | 1 TB SSD (Apple)       |
| Network      | Wi-Fi                   | 1 GbE                 | Wi-Fi                   | 1 GbE + Wi-Fi          |
| OS           | macOS 27.0              | Omarchy 4.0.4         | Omarchy 4.5.0           | Omarchy 4.5.0          |
| Tailscale IP | 100.95.69.110           | 100.97.112.40         | 100.113.199.114         | 100.78.246.113         |
| Role         | Primary workstation     | Always-on; singletons | Proxy client            | Proxy client           |

Notes:

- Omarchy runs the singletons (Pi Pocket, subscription proxy server, credits,
  Syncthing LAN forwarder); Miller and Drummer mirror it without them.
- Refresh on Linux with `lscpu`, `free -h`, `lspci -k`, `lsblk`, and
  `/sys/class/dmi/id/*`; on macOS with `system_profiler SPHardwareDataType`.
