{...}: {
  programs.fish.functions = {
    argo_pass = {
      body = ''
        set ARGOCD_PASSWORD $(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)
        echo $ARGOCD_PASSWORD | pbcopy
      '';
    };
    # https://github.com/fish-shell/fish-shell/wiki/Bash-Style-Command-Substitution-and-Chaining-(!!-!$)
    bind_bang = {
      body = ''
        switch (commandline -t)
        case "!"
          commandline -t -- $history[1]
          commandline -f repaint
        case "*"
          commandline -i !
        end
      '';
    };
    bind_dollar = {
      body = ''
        switch (commandline -t)
        case "!"
          commandline -t ""
          commandline -f history-token-search-backward
        case "*"
          commandline -i '$'
        end
      '';
    };
    cd = {
      body = ''
        builtin cd $argv

        if test $status = 0
          ll
        end
      '';
    };
    chat = {
      body = ''
        cd ~/.local/share/nvim/gp/chats/
        nvim scratch.md
      '';
    };
    fish_user_key_bindings = {
      body = ''
        bind ! bind_bang
        bind '$' bind_dollar
        # fzf_key_bindings
      '';
    };
    ip = {
      body = ''
        switch (uname)
        case Darwin
          ifconfig | grep inet | grep broadcast | awk '{print $2}'
        case Linux
          ipconfig getifaddr en0 || \
            ipconfig getifaddr en1 || \
            ipconfig getifaddr en2 || \
            ipconfig getifaddr en3
        end
      '';
    };
    la = {
      body = ''
        if type -q lsd
          lsd -la $argv
        else
          command ls -la $argv
        end
      '';
    };
    ll = {
      body = ''
        if type -q lsd
          lsd -1a $argv
        else
          command ls -1a $argv
        end
      '';
    };
    ls = {
      body = ''
        if type -q lsd
          lsd -1 $argv
        else
          command ls -1 $argv
        end
      '';
    };
    mkdir = {
      body = ''
        command mkdir $argv

        if test $status = 0
          switch $argv[(count $argv)]
            case '-*'
            case '*'
              cd $argv[(count $argv)]
              return
          end
        end
      '';
    };
    nix-rebuild = {
      body = ''
        argparse 'switch-only' -- $argv
        or return

        if not set -q _flag_switch_only
          nix flake update
        end

        set -xg NIXPKGS_ALLOW_UNFREE 1
        darwin-rebuild switch --impure --flake ~/dev/src/system-config/
      '';
    };
  };
}
