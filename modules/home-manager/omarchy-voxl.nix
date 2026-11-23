# Omarchy's headless browser desktop: a virtual X display with one shared,
# persistent Chromium that agents drive over CDP and John reaches in a browser
# tab through voxl (https://github.com/tembo/voxl), published on the tailnet.
{
  config,
  lib,
  pkgs,
  voxl,
  ...
}: let
  cfg = config.omarchyVoxl;
  display = ":1";
  voxlPackage = (pkgs.callPackage "${voxl}/default.nix" {}).overrideAttrs {
    # Upstream's tsc type-check fails on nixpkgs' newer TypeScript (typed-array
    # generics); esbuild still bundles the client, so skip only the check.
    preBuild = "";
  };
  # Xvfb with XTEST scroll axes, for voxl's smooth scrolling.
  xvfb = pkgs.callPackage "${voxl}/xvfb.nix" {};
  # The largest desktop voxl may resize to; it fits the screen to the viewer.
  maxSize = "3840x2400";
  url = "https://${cfg.host}:${toString cfg.port}/";
  cdp = "http://127.0.0.1:${toString cfg.cdpPort}";
  # The sign-in password, encrypted with systemd-creds' per-user host key;
  # it is decrypted only into the service's private credentials tmpfs.
  credName = "voxl-password";
  credFile = "%h/.config/voxl/password.cred";
  systemdCreds = "/usr/bin/systemd-creds";
  voxlStart = pkgs.writeShellScript "voxl-start" ''
    VOXL_PASSWORD=$(cat "$CREDENTIALS_DIRECTORY/${credName}")
    export VOXL_PASSWORD
    exec ${lib.getExe voxlPackage} "$@"
  '';

  # Everything here belongs on the virtual display, never Hyprland's session.
  onDisplay = {
    Environment = ["DISPLAY=${display}"];
    UnsetEnvironment = ["WAYLAND_DISPLAY"];
  };
  sharedUnit = {
    BindsTo = ["voxl-xvfb.service"];
    After = ["voxl-xvfb.service"];
  };
  waitForDisplay = pkgs.writeShellScript "voxl-wait-display" ''
    for _ in $(seq 100); do
      [ -S /tmp/.X11-unix/X${lib.removePrefix ":" display} ] && exit 0
      sleep 0.1
    done
    echo "voxl-xvfb: display ${display} did not appear" >&2
    exit 1
  '';
in {
  options.omarchyVoxl = {
    host = lib.mkOption {
      type = lib.types.str;
      example = "omarchy.taila14c2.ts.net";
      description = "This host's MagicDNS name; Tailscale Serve publishes voxl there.";
    };
    port = lib.mkOption {
      type = lib.types.port;
      default = 6901;
      description = "Loopback voxl port and the tailnet HTTPS port Serve publishes.";
    };
    cdpPort = lib.mkOption {
      type = lib.types.port;
      default = 9222;
      description = "Loopback Chrome DevTools Protocol port of the shared browser.";
    };
  };

  config = {
    home.packages = [voxlPackage];

    # Host-local encrypted password (never plaintext on disk, in the repo, or
    # in the store), made once if missing; the plaintext env file it replaced
    # is migrated, then removed. Before systemd reloads, so voxl's condition
    # sees it. Show or change it on Omarchy:
    #   systemd-creds --user decrypt --name=${credName} ~/.config/voxl/password.cred -
    #   read -rs p && printf %s "$p" | systemd-creds --user encrypt --name=${credName} - ~/.config/voxl/password.cred; unset p
    #   systemctl --user restart voxl
    home.activation.voxlPassword = lib.hm.dag.entryBetween ["reloadSystemd"] ["writeBoundary"] ''
      dir=${config.xdg.configHome}/voxl
      cred=$dir/password.cred
      legacy=$dir/env
      if [ -z "''${DRY_RUN:-}" ]; then
        if [ ! -e "$cred" ]; then
          install -d -m 700 "$dir"
          if [ -f "$legacy" ]; then
            sed -n 's/^VOXL_PASSWORD=//p' "$legacy"
          else
            od -An -tx1 -N16 /dev/urandom
          fi | tr -d ' \n' | (umask 077; ${systemdCreds} --user encrypt --name=${credName} - "$cred")
        fi
        if [ -s "$cred" ] && [ -e "$legacy" ]; then
          rm -f "$legacy"
        fi
      fi
    '';

    # Tailnet-only HTTPS front (browsers allow WebCodecs only on HTTPS).
    # Persistent in tailscaled; other Serve ports untouched.
    home.activation.voxlServe = lib.hm.dag.entryAfter ["linkGeneration"] ''
      if [ -z "''${DRY_RUN:-}" ]; then
        if ! /usr/bin/tailscale serve --bg --https=${toString cfg.port} --yes http://127.0.0.1:${toString cfg.port} >/dev/null; then
          echo "voxl: could not publish ${url} (Tailscale Serve)" >&2
        fi
      fi
    '';

    systemd.user.services = {
      voxl-xvfb = {
        Unit.Description = "Virtual X display ${display} for the shared agent browser";
        Service = {
          ExecStart = "${xvfb}/bin/Xvfb ${display} -screen 0 ${maxSize}x24 -shmem -nolisten tcp";
          ExecStartPost = "${waitForDisplay}";
          Restart = "always";
          RestartSec = 2;
        };
        Install.WantedBy = ["default.target"];
      };

      # Window management so popups and OAuth windows get placement and focus.
      voxl-wm = {
        Unit = sharedUnit // {Description = "Openbox on ${display}";};
        Service =
          onDisplay
          // {
            ExecStart = "${pkgs.openbox}/bin/openbox";
            Restart = "always";
            RestartSec = 2;
          };
        Install.WantedBy = ["default.target"];
      };

      # One profile, one process: agents attach over CDP instead of launching
      # their own, so John's logins are the agents' logins.
      agent-browser = {
        Unit = sharedUnit // {Description = "Shared agent Chromium on ${display} (CDP ${cdp})";};
        Service =
          onDisplay
          // {
            ExecStart = lib.concatStringsSep " " [
              (lib.getExe pkgs.chromium)
              "--user-data-dir=%h/.local/share/agent-browser/chromium"
              "--remote-debugging-address=127.0.0.1"
              "--remote-debugging-port=${toString cfg.cdpPort}"
              "--ozone-platform=x11"
              # No desktop keyring here; keep cookies readable across restarts.
              "--password-store=basic"
              "--no-first-run"
              "--no-default-browser-check"
              "--start-maximized"
            ];
            Restart = "always";
            RestartSec = 2;
          };
        Install.WantedBy = ["default.target"];
      };

      voxl = {
        Unit =
          sharedUnit
          // {
            Description = "voxl browser desktop for ${display} (${url})";
            Documentation = ["https://github.com/tembo/voxl"];
            ConditionPathExists = credFile;
          };
        Service =
          onDisplay
          // {
            LoadCredentialEncrypted = "${credName}:${credFile}";
            ExecStart = lib.concatStringsSep " " [
              "${voxlStart}"
              "--basic-auth-user=${config.home.username}"
              "--addr=127.0.0.1"
              "--port=${toString cfg.port}"
              "--allowed-hosts=${cfg.host}"
              "--title=${lib.head (lib.splitString "." cfg.host)}-agent-desktop"
              "--enable-resize=true"
              "--audio-enabled=false"
            ];
            Restart = "always";
            RestartSec = 2;
            UMask = "0077";
          };
        Install.WantedBy = ["default.target"];
      };
    };

    agentProjects.personalHostInstructions = ''

      ## Shared browser (Omarchy)

      - One persistent Chromium runs on the virtual display `${display}`, with
        John's logins. For web work that needs a login or a human, attach with
        Playwright `connect_over_cdp("${cdp}")` (JS `connectOverCDP`), use
        `browser.contexts[0]`, open your own page, and close only your pages.
        Never close that browser or launch another on its profile. Throwaway
        headless runs (screenshots, tests) may launch their own browser.
      - When a login, 2FA, or CAPTCHA blocks you, leave that page open and ask
        John to finish it at ${url}, then wait for John to confirm.
      - Headed GUI apps for John go on `DISPLAY=${display}` with
        `WAYLAND_DISPLAY` unset; nobody sees the Hyprland session.
    '';
  };
}
