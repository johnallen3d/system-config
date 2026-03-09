{...}: {
  programs.fish.functions = {
    # worktrunk shell integration (from `wt config shell init fish`)
    wt = {
      body = ''
        set -l use_source false
        set -l args

        for arg in $argv
            if test "$arg" = "--source"; set use_source true; else; set -a args $arg; end
        end

        test -n "$WORKTRUNK_BIN"; or set -l WORKTRUNK_BIN (type -P wt 2>/dev/null)
        if test -z "$WORKTRUNK_BIN"
            echo "wt: command not found" >&2
            return 127
        end
        set -l directive_file (mktemp)

        if test $use_source = true
            env WORKTRUNK_DIRECTIVE_FILE=$directive_file cargo run --bin wt --quiet -- $args
        else
            env WORKTRUNK_DIRECTIVE_FILE=$directive_file $WORKTRUNK_BIN $args
        end
        set -l exit_code $status

        if test -s "$directive_file"
            eval (cat "$directive_file" | string collect)
            if test $exit_code -eq 0
                set exit_code $status
            end
        end

        rm -f "$directive_file"
        return $exit_code
      '';
    };
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
    fish_user_key_bindings = {
      body = ''
        bind ! bind_bang
        bind '$' bind_dollar
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
    fetch = {
      body = ''
        macchina $argv
      '';
    };
    nix-rebuild = {
      body = ''
        argparse 'switch-only' -- $argv
        or return

        if not set -q _flag_switch_only
          nix flake update
        end

        sudo darwin-rebuild switch --impure --flake ~/dev/src/system-config/
      '';
    };
  };
}
