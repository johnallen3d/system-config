{lib, ...}: {
  home.file.".config/pi/prompts/pkg-install.md".source = ./pi-prompts/pkg-install.md;
  home.file.".config/pi/prompts/wrap.md".source = ./pi-prompts/wrap.md;
  home.file.".config/pi-work/prompts/implement.md".source = ./pi-prompts/implement.md;

  home.activation.piPromptDirMigration = lib.hm.dag.entryBefore ["writeBoundary"] ''
    if [ -L "$HOME/.config/pi/prompts" ]; then
      rm -f "$HOME/.config/pi/prompts"
    fi

    if [ -L "$HOME/.config/pi-work/prompts" ]; then
      rm -f "$HOME/.config/pi-work/prompts"
    fi
  '';
}
