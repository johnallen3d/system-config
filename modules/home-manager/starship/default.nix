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
        "$shell"
        "$line_break"
        "$character"
      ];
      right_format = lib.concatStrings [
        "$nix_shell"
      ];
      git_status = {
        "stashed" = "";
      };
      shell = {
        disabled = false;
        bash_indicator = "";
        fish_indicator = "";
        zsh_indicator = "";
      };
      directory = {
        "truncation_length" = 8;
        "truncation_symbol" = "…/";
      };
    };
  };
}
