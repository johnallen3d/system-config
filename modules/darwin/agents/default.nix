{
  pkgs,
  home,
  brew_bin,
  ...
}: let
  AGENT_LANG = "en_US.UTF-8";
  AGENT_PATH = with pkgs;
    (lib.makeBinPath [
      bash
      coreutils
      findutils
      gnused
      lua
      sketchybar
    ])
    + ":"
    + lib.concatStringsSep ":" [
      brew_bin
      "/usr/bin"
      "/bin"
      "/usr/sbin"
      "/sbin"
    ];

  service_log_path = "${home}/Library/Logs/org.nixos";

  service_err_path = service: "${service_log_path}/${service}.err.log";
  service_out_path = service: "${service_log_path}/${service}.out.log";
in {
  launchd.user.agents = {
    "borders" = {
      environment = {
        LANG = "${AGENT_LANG}";
        PATH = "${AGENT_PATH}";
      };
      serviceConfig = {
        ProgramArguments = ["${brew_bin}/borders"];
        KeepAlive = true;
        RunAtLoad = true;
        StandardErrorPath = service_err_path "borders";
        StandardOutPath = service_out_path "borders";
      };
    };

    "bottombar" = {
      environment = {
        LANG = "${AGENT_LANG}";
        PATH = "${home}/bin:${AGENT_PATH}";
      };
      serviceConfig = {
        ProgramArguments = ["${home}/bin/bottombar"];
        KeepAlive = true;
        RunAtLoad = true;
        StandardErrorPath = service_err_path "bottombar";
        StandardOutPath = service_out_path "bottombar";
      };
    };

    "mpd" = {
      environment = {
        LANG = "${AGENT_LANG}";
        PATH = "${AGENT_PATH}";
      };
      serviceConfig = {
        ProgramArguments = [
          "${pkgs.mpd}/bin/mpd"
          "${home}/.config/mpd/mpd.conf"
          "--no-daemon"
        ];
        KeepAlive = true;
        RunAtLoad = true;
        StandardErrorPath = service_err_path "mpd";
        StandardOutPath = service_out_path "mpd";
      };
    };

    "sketchybar" = {
      environment = {
        LANG = "${AGENT_LANG}";
        PATH = "${AGENT_PATH}";
      };
      serviceConfig = {
        ProgramArguments = [
          "${pkgs.sketchybar}/bin/sketchybar"
          "--config"
          "${home}/.config/sketchybar/sketchybarrc.lua"
        ];
        KeepAlive = true;
        RunAtLoad = true;
        StandardErrorPath = service_err_path "sketchybar";
        StandardOutPath = service_out_path "sketchybar";
      };
    };
  };
}
