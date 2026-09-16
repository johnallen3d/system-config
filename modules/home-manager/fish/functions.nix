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
    "glow-watch" = {
      body = ''
        set -l file $argv[1]

        if test -z "$file"
            echo "usage: glow-watch FILE"
            return 1
        end

        if not test -f "$file"
            echo "no such file: $file"
            return 1
        end

        command clear
        glow "$file"

        while fswatch -1 "$file" >/dev/null
            command clear
            glow "$file"
        end
      '';
    };
    notes = {
      body = ''
        cd ~/notes
        set -lx PATH (string match -v -- '*/.npm/_npx/*' $PATH)
        command pi --model openai-codex/gpt-5.6-luna --thinking low --extension "$HOME/.config/pi-notes/git/github.com/badlogic/pi-telegram/index.ts" $argv
      '';
    };
  };
}
