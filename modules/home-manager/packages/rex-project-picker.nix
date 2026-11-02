# The cmd+shift+n project picker for Rex (see ../dotfiles/config/rex/init.lua):
# pick a zoxide folder, on this host by default or another Rex host with Tab,
# and switch to the session named after it, creating one there if needed.
# Like rex-tab-picker it runs in a float on the focused session's host, so it
# is installed everywhere. Other hosts are reached over SSH by their Rex label;
# rex and ssh come from the caller's PATH: the system ssh reads options,
# such as macOS UseKeychain, that Nix's OpenSSH rejects.
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
      # The host list lives in a state file whose first line is the target;
      # Tab rotates it and reloads the list through this script's subcommands.
      state=''${RPP_STATE:-}
      current=$(hostname -s)

      target() { head -n 1 "$state"; }

      # Folder rows as PATH<TAB>DISPLAY, with home shown as ~ on any host.
      list() {
        local host
        host=$(target)
        if [ "$host" = "$current" ]; then
          zoxide query -l
        else
          ssh -o BatchMode=yes -o ConnectTimeout=3 "$host" zoxide query -l 2>/dev/null || true
        fi | awk '{ d = $0; sub("^/(home|Users)/[^/]+", "~", d); print $0 "\t" d }'
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
        --next)
          { tail -n +2 "$state"; head -n 1 "$state"; } > "$state.tmp" && mv "$state.tmp" "$state"
          printf 'change-prompt(%s)+change-ghost(%s)+change-footer(%s)+reload(%q --list)' \
            "$(prompt)" "$(ghost)" "$(footer)" "$0"
          exit ;;
      esac

      state=$(mktemp); export RPP_STATE=$state
      trap 'rm -f "$state"' EXIT
      { echo "$current"; rex hosts list --json 2>/dev/null | jq -r '.hosts[].host.label' || true; } |
        awk '!seen[$0]++' > "$state"

      binds=()
      [ "$(wc -l < "$state")" -lt 2 ] || binds=(--bind "tab:transform($(printf %q "$0") --next)")

      dir=$(list | fzf --delimiter '\t' --with-nth 2 --accept-nth 1 --no-sort \
        --layout reverse --border rounded --padding 1,2 --info inline-right \
        --border-label "$(printf " ${fg "iris"}\033[1mNew session\033[0m ")" --border-label-pos 3 \
        --prompt "$(prompt)" --ghost "$(ghost)" --footer "$(footer)" \
        --pointer '┃' --marker ' ' --gutter ' ' --scrollbar '┃' --separator '─' --ansi \
        --color 'bg:${p.base},bg+:${p.overlay},fg:${p.subtle},fg+:${p.text},hl:${p.rose},hl+:${p.rose}' \
        --color 'border:${p.hl_med},label:${p.iris},prompt:${p.foam},pointer:${p.iris},query:${p.text}' \
        --color 'info:${p.muted},separator:${p.overlay},scrollbar:${p.hl_high},ghost:${p.muted}' \
        --color 'gutter:${p.base},footer:${p.muted},footer-border:${p.overlay}' \
        "''${binds[@]}") || exit 0
      [ -n "$dir" ] || exit 0

      host=$(target)
      server=()
      [ "$host" = "$current" ] || server=(-S "$host")
      name=''${dir##*/}
      id=$(rex "''${server[@]}" ls --json |
        jq -r --arg name "$name" 'first(.sessions[] | select(.label == $name) | .session_id) // empty')
      [ -n "$id" ] || id=$(rex "''${server[@]}" new "$name" -c "$dir" --json | jq -r .session_id)
      exec rex "''${server[@]}" "do" session.select session_id="$id"
    '';
  }
