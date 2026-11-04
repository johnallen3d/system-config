# The ctrl+cmd+n project picker for Rex (see ../dotfiles/config/rex/actions/project-picker.lua):
# pick a zoxide folder, on this host by default or another Rex host with Tab.
# Like rex-tab-picker it runs in a float on the focused session's host, so it
# is installed everywhere. A remote host's Rex server can't reach the config
# host, so the config's action passes in the host list and the config host's
# folders, and does the switch itself: the picker reports the highlighted
# folder in the terminal title as rex-project-picker:HOST/DIR, both in hex, and
# --open finds or creates the session for it on the config host. Other hosts
# are listed over SSH by their Rex label; rex and ssh come from the caller's
# PATH: the system ssh reads options, such as macOS UseKeychain, that Nix's
# OpenSSH rejects.
{
  pkgs,
  palette,
}: let
  inherit (pkgs) lib;
  # Rosé Pine names for the managed theme's colours, as in rex-tab-picker.
  p = lib.mapAttrs (_: key: palette.${key}) {
    base = "bg";
    overlay = "bgHighlight";
    hl_med = "bgVisual";
    hl_high = "gutter";
    text = "text";
    subtle = "muted";
    muted = "comment";
    rose = "orange";
    foam = "cyan";
    iris = "purple";
  };
  rgb = hex: lib.concatMapStringsSep ";" (i: toString (lib.fromHexString (builtins.substring i 2 hex))) [1 3 5];
  fg = name: "\\033[38;2;${rgb p.${name}}m";
in
  pkgs.writeShellApplication {
    name = "rex-project-picker";
    runtimeInputs = with pkgs; [coreutils fzf jq zoxide];
    text = ''
      # Usage: rex-project-picker HOME_LABEL HOME_FOLDERS HOST...
      #        rex-project-picker --open HOST DIR   (prints the session ID)
      # The host list lives in a state file whose first line is the target;
      # Tab rotates it and reloads the list through this script's subcommands.
      state=''${RPP_STATE:-}
      home=''${RPP_HOME:-}
      current=$(hostname -s)

      target() { head -n 1 "$state"; }

      # Folder rows as PATH<TAB>DISPLAY, with home shown as ~ on any host.
      list() {
        local host
        host=$(target)
        if [ "$host" = "$current" ]; then
          zoxide query -l
        elif [ "$host" = "$home" ]; then
          printf '%s' "$RPP_HOME_FOLDERS"
        else
          ssh -o BatchMode=yes -o ConnectTimeout=3 "$host" zoxide query -l 2>/dev/null || true
        fi | awk '{ d = $0; sub("^/(home|Users)/[^/]+", "~", d); print $0 "\t" d }'
      }

      hex() { printf '%s' "$1" | od -An -v -tx1 | tr -d ' \n'; }
      # Tell the config's Enter action what is highlighted; empty when nothing is.
      record() {
        local pick=""
        [ -z "$1" ] || pick="$(hex "$(target)")/$(hex "$1")"
        printf '\033]2;rex-project-picker:%s\007' "$pick" > /dev/tty
      }

      prompt() { printf ' 󰍉  %s  ' "$(target)"; }
      ghost() { printf 'Search folders on %s' "$(target)"; }

      key="${fg "subtle"}\033[1m" label="\033[22m${fg "muted"}"
      hint() { printf '%b%s%b %s   ' "$key" "$1" "$label" "$2"; }
      footer() {
        local next
        next=$(sed -n 2p "$state")
        hint '↑↓' move
        [ -z "$next" ] || hint '⇥' "$next"
        hint '⏎' open
        hint esc close
      }

      case "''${1:-}" in
        --list) list; exit ;;
        --record) record "''${2:-}"; exit ;;
        --next)
          { tail -n +2 "$state"; head -n 1 "$state"; } > "$state.tmp" && mv "$state.tmp" "$state"
          printf 'change-prompt(%s)+change-ghost(%s)+change-footer(%s)+reload(%q --list)' \
            "$(prompt)" "$(ghost)" "$(footer)" "$0"
          exit ;;
        --open)
          # Runs on the config host, whose home server is HOST when it is the
          # config host's own label.
          host=$2 dir=$3
          server=()
          [ "$host" = "$current" ] || server=(-S "$host")
          name=''${dir##*/}
          id=$(rex "''${server[@]}" ls --json |
            jq -r --arg name "$name" 'first(.sessions[] | select(.label == $name) | .session_id) // empty')
          [ -n "$id" ] || id=$(rex "''${server[@]}" new "$name" -c "$dir" --json | jq -r .session_id)
          printf '%s' "$id"
          exit ;;
      esac

      [ $# -ge 2 ] || { echo "usage: rex-project-picker HOME_LABEL HOME_FOLDERS HOST..." >&2; exit 2; }
      export RPP_HOME=$1 RPP_HOME_FOLDERS=$2
      home=$1
      shift 2
      state=$(mktemp); export RPP_STATE=$state
      trap 'rm -f "$state"' EXIT
      { echo "$current"; printf '%s\n' "$home" "$@"; } | awk 'NF && !seen[$0]++' > "$state"

      self=$(printf %q "$0")
      binds=(--bind "focus:execute-silent($self --record {1})" --bind "result:execute-silent($self --record {1})")
      [ "$(wc -l < "$state")" -lt 2 ] || binds+=(--bind "tab:transform($self --next)")

      # Enter and Escape belong to the config's project_picker mode, so fzf
      # only browses; the float closes when the config's action finishes.
      list | fzf --delimiter '\t' --with-nth 2 --no-sort \
        --layout reverse --border rounded --padding 1,2 --info inline-right \
        --border-label "$(printf " ${fg "iris"}\033[1mNew session\033[0m ")" --border-label-pos 3 \
        --prompt "$(prompt)" --ghost "$(ghost)" --footer "$(footer)" \
        --pointer '┃' --marker ' ' --gutter ' ' --scrollbar '┃' --separator '─' --ansi \
        --color 'bg:${p.base},bg+:${p.overlay},fg:${p.subtle},fg+:${p.text},hl:${p.rose},hl+:${p.rose}' \
        --color 'border:${p.hl_med},label:${p.iris},prompt:${p.foam},pointer:${p.iris},query:${p.text}' \
        --color 'info:${p.muted},separator:${p.overlay},scrollbar:${p.hl_high},ghost:${p.muted}' \
        --color 'gutter:${p.base},footer:${p.muted},footer-border:${p.overlay}' \
        "''${binds[@]}" > /dev/null || true
    '';
  }
