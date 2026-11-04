{
  programs.gh = {
    enable = true;
    settings = {
      git_protocol = "ssh";
      aliases = {
        co = "pr checkout";
        labels = "!gh api --paginate repos/:owner/:repo/labels | jq -r .[].name";
        label-add = "!gh api /repos/technekes/$1/labels --field name=$2";
      };
    };
  };
}
