{lib}: let
  npm = name: "npm:${name}";
  # Temporary pin: pi-answer@0.1.6 is broken upstream (workspace dependency
  # published to npm), so keep declared installs on the last good release.
  npmPinned = name: version: "npm:${name}@${version}";
in rec {
  sharedPackageSpecs = [
    (npm "@tintinweb/pi-tasks")
    (npm "@tmustier/pi-skill-creator")
    (npmPinned "pi-answer" "0.1.4")
    (npm "pi-intercom")
    (npm "pi-markdown-preview")
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
