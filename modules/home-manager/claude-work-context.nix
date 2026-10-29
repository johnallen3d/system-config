# Mac-equivalent context for work and personal Claude on both hosts.
# Settings remain writable/host-local.
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
      "subscriptionProxyClients"
    ] ''
      if [ -z "''${DRY_RUN_CMD:-}" ]; then
        for profile in claude-gmatter claude-personal; do
          ${pkgs.python3}/bin/python3 ${./claude-work-context/merge.py} \
            --policy ${./claude-work-context/policy.json} --profile "$profile"
        done
      fi
    '';
}
