{
  pkgs,
  brew_bin,
  ...
}:
pkgs.writeShellScriptBin "toggle-air-pods" ''
  # bluetooth address for blueutil
  airpords_pro_address=48-e1-5c-e1-58-be

  # output devices id's for SwitchAudioSource
  macbook_pro_id=72
  airpods_pro_id=96

  # TODO: blueutil currently not working 🤷
  ${brew_bin}/bin/SwitchAudioSource -i "$macbook_pro_id"
  ${brew_bin}/bin/blueutil --disconnect "$airpords_pro_address"
  ${brew_bin}/bin/blueutil --connect "$airpords_pro_address"
  ${brew_bin}/bin/SwitchAudioSource -i "$airpods_pro_id"
''
