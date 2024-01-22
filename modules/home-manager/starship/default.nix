{lib, ...}: {
  programs.starship = {
    enable = true;
    enableIonIntegration = false;
    enableNushellIntegration = false;
    settings = {
      format = lib.concatStrings [
        "$directory"
        "$git_branch"
        "$git_commit"
        "$git_state"
        "$git_status"
        "$cmd_duration"
        "$line_break"
        "$character"
      ];
      git_status = {
        "stashed" = "";
      };
      directory = {
        "truncation_length" = 8;
        "truncation_symbol" = "…/";
      };
    };
  };
}
