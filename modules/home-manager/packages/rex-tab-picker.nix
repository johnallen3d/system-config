# The cmd+k tab picker for Rex (see ../dotfiles/config/rex/actions/tab-picker.lua). It runs
# in a float on whichever host the focused session lives on, so it is
# installed on every host even though the Rex config is Mac-only.
{
  pkgs,
  palette,
}:
pkgs.rustPlatform.buildRustPackage {
  pname = "rex-tab-picker";
  version = "0.1.0";
  src = pkgs.lib.cleanSourceWith {
    src = ./rex-tab-picker;
    filter = path: _: baseNameOf path != "target";
  };
  cargoLock.lockFile = ./rex-tab-picker/Cargo.lock;
  # Rosé Pine names for the managed theme's colours, read at compile time.
  env.RTP_PALETTE = pkgs.lib.concatStringsSep ";" (pkgs.lib.mapAttrsToList (name: key: "${name}=${palette.${key}}") {
    base = "bg";
    surface = "bgDark";
    overlay = "bgHighlight";
    hl_med = "bgVisual";
    hl_high = "gutter";
    text = "text";
    subtle = "muted";
    muted = "comment";
    love = "red";
    gold = "yellow";
    rose = "orange";
    pine = "green";
    foam = "cyan";
    iris = "purple";
  });
  meta.mainProgram = "rex-tab-picker";
}
