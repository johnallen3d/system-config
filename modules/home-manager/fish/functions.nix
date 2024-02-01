{...}: {
  programs.fish.functions = {
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
        cd ~/Dropbox/Notes/scratch
        nvim -c "lua require('gp').setup()" -c "GpChatNew" chat.md
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
    # nix = {
    #   body = ''
    #     nix-your-shell fish nix -- $argv
    #   '';
    # };
    # nix-shell = {
    #   body = ''
    #     nix-your-shell fish nix-shell -- $argv
    #   '';
    # };
    t = {
      body = ''
        if count $argv > /dev/null
          set title $argv[1]
        else
          set title (basename $PWD)
        end

        kitty @ set-tab-title $title
      '';
    };
  };
}
