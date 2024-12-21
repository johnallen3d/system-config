{lib, ...}: {
  programs.starship = {
    enable = true;
    enableIonIntegration = false;
    enableNushellIntegration = false;
    enableTransience = true;
    settings = {
      format = lib.concatStrings [
        "$directory"
        "$git_branch"
        "$git_commit"
        "$git_state"
        "$git_status"
        "$cmd_duration"
        "$shell"
        "$hostname"
        "$line_break"
        "$character"
      ];
      right_format = lib.concatStrings [
        "$nix_shell"
        "$python"
        "$kubernetes"
      ];
      character = {
        success_symbol = "[](bold green) ";
        error_symbol = "[✗](bold red) ";
      };
      git_status = {
        "stashed" = "";
      };
      kubernetes = {
        disabled = true;
      };
      python = {
        pyenv_version_name = true;
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
