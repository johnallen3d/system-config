{
  home,
  user,
  brew_bin,
  ...
}: let
  NIX_BIN = "/etc/profiles/per-user/${user}/bin/";

  AGENT_PATH = "${NIX_BIN}:${home}/.cargo/bin:${brew_bin}:/opt/homebrew/sbin:/usr/bin:/bin:/usr/sbin:/sbin";
  AGENT_LANG = "en_US.UTF-8";

  service_log_path = "${home}/Library/Logs/org.nixos";

  service_err_path = service: "${service_log_path}/${service}.err.log";
  service_out_path = service: "${service_log_path}/${service}.out.log";
in {
  launchd.user.agents = {
    "bottombar" = {
      environment = {
        LANG = "${AGENT_LANG}";
        PATH = "${AGENT_PATH}";
      };
      serviceConfig = {
        ProgramArguments = ["${home}/bin/bottombar"];
        KeepAlive = true;
        RunAtLoad = true;
        StandardErrorPath = service_err_path "bottombar";
        StandardOutPath = service_out_path "bottombar";
      };
    };
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
    "mpd" = {
      environment = {
        LANG = "${AGENT_LANG}";
        PATH = "${AGENT_PATH}";
      };
      serviceConfig = {
        ProgramArguments = [
          "${NIX_BIN}/mpd"
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
        ProgramArguments = ["${NIX_BIN}/sketchybar"];
        KeepAlive = true;
        RunAtLoad = true;
        StandardErrorPath = service_err_path "sketchybar";
        StandardOutPath = service_out_path "sketchybar";
      };
    };
  };
}
