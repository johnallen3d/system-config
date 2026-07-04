{lib}: let
  npm = name: "npm:${name}";
in rec {
  sharedPackageSpecs = [
    "git:github.com/DietrichGebert/ponytail"
    # (npm "@tintinweb/pi-tasks")
    # (npm "@tmustier/pi-skill-creator")
    (npm "pi-headroom")
    # (npm "pi-intercom")
    (npm "pi-markdown-preview")
  ];

  personalPackageSpecs =
    sharedPackageSpecs
    ++ [
      "git:github.com/badlogic/pi-telegram"
      (npm "@ramarivera/pi-grok-build")
      # (npm "@samfp/pi-memory")
      # (npm "context-mode")
      (npm "pi-claude-bridge")
      (npm "pi-mcp-adapter")
      (npm "pi-prompt-template-model")
      # (npm "pi-subagents")
      (npm "pi-web-access")
    ];

  workPackageSpecs =
    sharedPackageSpecs
    ++ [
      (npm "pi-ask-user")
      "git:github.com/amfaro/pi-workflows"
      # "git:github.com/amfaro/pi-workflows@feature/disable-pi-subagents"
    ];

  allPackageSpecs = lib.unique (personalPackageSpecs ++ workPackageSpecs);
}
