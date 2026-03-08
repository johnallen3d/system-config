# Workaround for macOS Tahoe (26.x) SIGKILL during Home Manager activation.
#
# Tahoe kills bash processes that rapidly spawn too many subprocesses
# (fork+exec of mkdir + ln per file) when creating symlinks in $HOME.
# The threshold is ~80 files when using `find -exec bash ... +` (one bash
# for all files). Using `find -exec ... \;` (one bash per file) keeps each
# invocation under the limit.
#
# TODO: remove once home-manager fixes upstream or Apple changes this behavior.
{
  config,
  lib,
  pkgs,
  ...
}: {
  home.activation.linkGeneration = lib.mkForce (
    lib.hm.dag.entryAfter ["writeBoundary"] (
      let
        link = pkgs.writeShellScript "link" ''
          ${config.lib.bash.initHomeManagerLib}

          newGenFiles="$1"
          shift
          for sourcePath in "$@" ; do
            relativePath="''${sourcePath#$newGenFiles/}"
            targetPath="$HOME/$relativePath"
            if [[ -e "$targetPath" && ! -L "$targetPath" ]] ; then
              if [[ -n "$HOME_MANAGER_BACKUP_COMMAND" ]] ; then
                verboseEcho "Running $HOME_MANAGER_BACKUP_COMMAND $targetPath."
                run $HOME_MANAGER_BACKUP_COMMAND "$targetPath" || errorEcho "Running `$HOME_MANAGER_BACKUP_COMMAND` on '$targetPath' failed."
              elif [[ -n "$HOME_MANAGER_BACKUP_EXT" ]] ; then
                backup="$targetPath.$HOME_MANAGER_BACKUP_EXT"
                if [[ -e "$backup" && -n "$HOME_MANAGER_BACKUP_OVERWRITE" ]]; then
                  run rm $VERBOSE_ARG "$backup"
                fi
                run mv $VERBOSE_ARG "$targetPath" "$backup" || errorEcho "Moving '$targetPath' failed!"
              fi
            fi

            if [[ -e "$targetPath" && ! -L "$targetPath" ]] && cmp -s "$sourcePath" "$targetPath" ; then
              verboseEcho "Skipping '$targetPath' as it is identical to '$sourcePath'"
            else
              run mkdir -p $VERBOSE_ARG "$(dirname "$targetPath")"
              run ln -Tsf $VERBOSE_ARG "$sourcePath" "$targetPath" || exit 1
            fi
          done
        '';

        cleanup = pkgs.writeShellScript "cleanup" ''
          ${config.lib.bash.initHomeManagerLib}

          homeFilePattern="$(readlink -e ${lib.escapeShellArg builtins.storeDir})/*-home-manager-files/*"

          newGenFiles="$1"
          shift 1
          for relativePath in "$@" ; do
            targetPath="$HOME/$relativePath"
            if [[ -e "$newGenFiles/$relativePath" ]] ; then
              verboseEcho "Checking $targetPath: exists"
            elif [[ ! "$(readlink "$targetPath")" == $homeFilePattern ]] ; then
              warnEcho "Path '$targetPath' does not link into a Home Manager generation. Skipping delete."
            else
              verboseEcho "Checking $targetPath: gone (deleting)"
              run rm $VERBOSE_ARG "$targetPath"

              targetDir="$(dirname "$relativePath")"
              if [[ "$targetDir" != "." ]] ; then
                pushd "$HOME" > /dev/null
                run rmdir $VERBOSE_ARG \
                    -p --ignore-fail-on-non-empty \
                    "$targetDir"
                popd > /dev/null
              fi
            fi
          done
        '';
      in
      ''
        function linkNewGen() {
          _i "Creating home file links in %s" "$HOME"

          local newGenFiles
          newGenFiles="$(readlink -e "$newGenPath/home-files")"
          find "$newGenFiles" \( -type f -or -type l \) \
            -exec bash ${link} "$newGenFiles" {} \;
        }

        function cleanOldGen() {
          if [[ ! -v oldGenPath || ! -e "$oldGenPath/home-files" ]] ; then
            return
          fi

          _i "Cleaning up orphan links from %s" "$HOME"

          local newGenFiles oldGenFiles
          newGenFiles="$(readlink -e "$newGenPath/home-files")"
          oldGenFiles="$(readlink -e "$oldGenPath/home-files")"

          find "$oldGenFiles" '(' -type f -or -type l ')' -printf '%P\0' \
            | xargs -0 bash ${cleanup} "$newGenFiles"
        }

        cleanOldGen
        linkNewGen
      ''
    )
  );
}
