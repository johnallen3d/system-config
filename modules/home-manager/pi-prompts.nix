{lib, ...}: {
  home.file.".config/pi/prompts" = {
    recursive = true;
    source = ./pi-prompts;
  };

  home.activation.piWorkPromptCleanup = lib.hm.dag.entryAfter ["writeBoundary"] ''
    rm -rf "$HOME/.config/pi-work/prompts"
  '';
}
