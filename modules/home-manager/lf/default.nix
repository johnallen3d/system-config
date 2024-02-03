{pkgs, ...}: {
  xdg.configFile."lf/icons".source = ./icons;

  programs.lf = {
    enable = true;

    settings = {
      preview = true;
      hidden = true;
      drawbox = true;
      icons = true;
      ignorecase = true;
    };

    commands = {
      extract = ''
        ''${{
            set -f
            case $f in
                *.tar.bz|*.tar.bz2|*.tbz|*.tbz2) tar xjvf $f;;
                *.tar.gz|*.tgz) tar xzvf $f;;
                *.tar.xz|*.txz) tar xJvf $f;;
                *.zip) unzip $f;;
                *.rar) unrar x $f;;
                *.7z) 7z x $f;;
            esac
        }}
      '';

      mkdir = ''
        ''${{
          printf "Directory name: "
          read DIR
          mkdir -p "$DIR"
        }}
      '';

      tar = ''
        ''${{
            set -f
            mkdir $1
            cp -r $fx $1
            tar --create --gzip --keep-old-files --file $1.tar.gz $1
            rm -rf $1
        }}
      '';

      touch = ''
        ''${{
          printf "File name: "
          read FILE
          touch "$FILE"
        }}
      '';

      yank-file = ''
        $cat "$fx" | pbcopy
      '';

      yank-path = ''
        $printf '%s' "$fx" | pbcopy
      '';

      z = ''
        %{{
          result="$(zoxide query --exclude $PWD $@ | sed 's/\\/\\\\/g;s/"/\\"/g')"
          lf -remote "send $id cd \"$result\""
        }}
      '';

      zip = ''
        ''${{
            set -f
            mkdir $1
            cp -r $fx $1
            zip -r $1.zip $1
            rm -rf $1
        }}
      '';
    };

    keybindings = {
      "." = "set hidden!";
      DD = "delete";
      gd = "cd ~/Downloads";
      gh = "cd";
      gs = "cd ~/dev/src/system-config";
      x = ":extract";
    };

    extraConfig = let
      previewer = pkgs.writeShellScriptBin "pv.sh" ''
        file=$1
        w=$2
        h=$3
        x=$4
        y=$5

        if [[ "$( ${pkgs.file}/bin/file -Lb --mime-type "$file")" =~ ^image ]]; then
            ${pkgs.kitty}/bin/kitty +kitten icat --silent --stdin no --transfer-mode file --place "''${w}x''${h}@''${x}x''${y}" "$file" < /dev/null > /dev/tty
            exit 1
        fi

        ${pkgs.pistol}/bin/pistol "$file"
      '';
      cleaner = pkgs.writeShellScriptBin "clean.sh" ''
        ${pkgs.kitty}/bin/kitty +kitten icat --clear --stdin no --silent --transfer-mode file < /dev/null > /dev/tty
      '';
    in ''
      set cleaner ${cleaner}/bin/clean.sh
      set previewer ${previewer}/bin/pv.sh
    '';
  };
}
