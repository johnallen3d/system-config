{...}: {
  programs.direnv = {
    enable = true;
    enableNixDirenvIntegration = true;
    nix-direnv.enable = true;
  };

  home = {
    sessionVariables = {
      DIRENV_LOG_FORMAT = "";
    };
  };
}
