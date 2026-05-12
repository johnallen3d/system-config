{lib}: let
  npm = name: "npm:${name}";
in rec {
  sharedPackageSpecs = [
    (npm "@tintinweb/pi-tasks")
    (npm "@tmustier/pi-skill-creator")
    (npm "pi-answer")
    (npm "pi-intercom")
    (npm "pi-markdown-preview")
    (npm "pi-web-access")
  ];

  personalPackageSpecs = sharedPackageSpecs ++ [
    "git:github.com/badlogic/pi-telegram"
    (npm "@samfp/pi-memory")
    (npm "context-mode")
    (npm "pi-claude-bridge")
    (npm "pi-mcp-adapter")
    (npm "pi-prompt-template-model")
    (npm "pi-subagents")
    (npm "pi-web-access")
  ];

  workPackageSpecs = sharedPackageSpecs ++ [
    "git:github.com/amfaro/skills"
  ];

  allPackageSpecs = lib.unique (personalPackageSpecs ++ workPackageSpecs);
}
