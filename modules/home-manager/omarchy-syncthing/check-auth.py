"""Require existing Syncthing GUI authentication before opening the LAN socket."""

import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener


def validate_config(path):
    gui = ET.parse(path).getroot().find("gui")
    if gui is None or not gui.findtext("user") or not gui.findtext("password"):
        raise RuntimeError("Syncthing LAN access requires a GUI username and password")
    if gui.findtext("insecureAdminAccess", "false").lower() != "false":
        raise RuntimeError("Syncthing LAN access requires secure GUI admin access")


def require_auth(url):
    # Do not consult proxy variables or send credentials, and never print bodies.
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(Request(url), timeout=10):
            pass
    except HTTPError as error:
        if error.code in (401, 403):
            return
        raise RuntimeError("Unexpected Syncthing GUI authentication response") from None
    raise RuntimeError("Syncthing protected REST endpoint permits unauthenticated access")


def main():
    home = Path.home()
    path = home / ".local/state/syncthing/config.xml"
    if not path.exists():
        path = home / ".config/syncthing/config.xml"
    validate_config(path)
    require_auth("http://127.0.0.1:8384/rest/config")


if __name__ == "__main__":
    main()
