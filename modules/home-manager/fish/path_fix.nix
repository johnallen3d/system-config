{
  lib,
  osConfig,
  ...
}: {
  # prepend nix bin paths workaround described here:
  # https://github.com/LnL7/nix-darwin/issues/122#issuecomment-1659465635
  # this wouldn't be necessary if either of these werged:
  # https://github.com/nix-community/home-manager/pull/4582
  # https://github.com/nix-community/home-manager/pull/4681
  programs.fish.loginShellInit = let
    # This naive quoting is good enough in this case. There shouldn't be any
    # double quotes in the input string, and it needs to be double quoted in case
    # it contains a space (which is unlikely!)
    dquote = str: "\"" + str + "\"";

    makeBinPathList = map (path: path + "/bin");
  in ''
    fish_add_path --move --prepend --path ${lib.concatMapStringsSep " " dquote (makeBinPathList osConfig.environment.profiles)}
    set fish_user_paths $fish_user_paths
  '';
}
