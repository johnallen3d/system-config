{lib}: let
  npm = name: "npm:${name}";
in rec {
  sharedPackageSpecs = [
    (npm "pi-headroom")
  ];

  personalPackageSpecs =
    sharedPackageSpecs
    ++ [
      (npm "pi-prompt-template-model")
      (npm "pi-web-search")
    ];

  notesPackageSpecs = [
    "git:github.com/badlogic/pi-telegram"
  ];

  workPackageSpecs =
    sharedPackageSpecs
    ++ [
      "git:github.com/amfaro/agent-kit"
    ];

  allPackageSpecs = lib.unique (personalPackageSpecs ++ workPackageSpecs);
}
