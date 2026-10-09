# Mac-equivalent work context on both hosts. Settings remain writable/host-local.
{
  lib,
  pkgs,
  ...
}: {
  home.file.".config/claude-gmatter/work-context-policy.json".source = ./claude-work-context/policy.json;

  # Run after the existing seed/UI writers; append restrictions, never replace
  # permission blocks, saved models, window preferences, hooks, or credentials.
  # The four context flags are deliberately owned to replicate Mac's footprint.
  home.activation.claudeWorkContext =
    lib.hm.dag.entryAfter [
      "writeBoundary"
      "claudeProfileDefaults"
      "claudeGmatterSettings"
    ] ''
      if [ -z "''${DRY_RUN_CMD:-}" ]; then
        ${pkgs.python3}/bin/python3 ${./claude-work-context/merge.py} \
          --policy ${./claude-work-context/policy.json}
      fi
    '';
}
