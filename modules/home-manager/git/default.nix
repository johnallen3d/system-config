{
  full_name,
  pkgs,
  ...
}: {
  programs.git = {
    enable = true;
    userName = "${full_name}";
    userEmail = "john@threedogconsulting.com";
    signing = {
      # signByDefault = true;
      key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFHBm+OH64z4tbmeAbNKge88yfQ82na+sLLfaSisfSpa";
    };
    extraConfig = {
      color = {
        ui = "always";
      };
      "color \"diff\"" = {
        commit = "green";
        meta = "yellow";
        frag = "cyan";
        old = "red";
        new = "green";
        whitespace = "red reverse";
      };
      "color \"diff-highlight\"" = {
        oldNormal = "red bold";
        oldHighlight = "red bold 52";
        newNormal = "green bold";
        newHighlight = "green bold 22";
      };
      commit = {
        gpgSign = true;
      };
      "credential \"https://github.com\"" = {
        helper = "!/etc/profiles/per-user/john.allen/bin/gh auth git-credential";
      };
      "credential \"https://gist.github.com\"" = {
        helper = "!/etc/profiles/per-user/john.allen/bin/gh auth git-credential";
      };
      github = {
        user = "johnallen3d";
      };
      gpg = {
        format = "ssh";
      };
      "gpg \"ssh\"" = {
        # program = "/Applications/1Password.app/Contents/MacOS/op-ssh-sign";
        program = "${pkgs._1password-gui}/bin/op-ssh-sign";
      };
      init = {
        defaultBranch = "main";
      };
      fetch = {
        prune = true;
      };
      log = {
        date = "iso";
      };
      pull = {
        rebase = true;
      };
      push = {
        default = "simple";
      };
      rebase = {
        autosquash = true;
      };
      rerere = {
        enabled = true;
        autoupdate = true;
      };
    };
    aliases = {
      lol = "log --color --pretty=format:\"%C(yellow)%h%C(reset) %s%C(bold red)%d%C(reset) %C(green)%ad%C(reset) %C(blue)[%an]%C(reset)\" --relative-date --decorate --oneline";
      head = "lol -n 10";
      blog = "log --graph --format=format:'%C(bold magenta)%h%C(reset) %C(white)%ai%C(reset) %C(bold dim white)%aN%C(auto)%+D%C(reset)%n%C(bold white)%s%C(reset)%+b%n'";
      graph = "log --color --graph --pretty=format:\"%h | %ad | %an | %s%d\" --date=short";
      hist = "log --pretty=oneline --graph";
      unstage = "reset HEAD --";
      restore = "checkout --";
      undo = "reset HEAD^";
      bv = "branch -vv --format='%(color:red)%(objectname:short) %(color:yellow)%(refname:short)%(color:reset) (%(color:green)%(committerdate:relative)%(color:reset)) %(color:cyan)%(upstream:short)%(color:reset)'";
      # url =! "bash -c 'git config --get remote.origin.url | sed -E "s/.+:\\(.+\\)\\.git$/https:\\\\/\\\\/github\\\\.com\\\\/\\\\1/g"'";
    };
    ignores = [
      "*~"
      ".*.sw*"
      ".un~"
      ".DS_Store"
      "tags"
      "tags.lock"
      "tags.temp"
      ".pry_history"
    ];
  };

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
