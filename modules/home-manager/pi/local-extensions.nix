{lib, ...}: {
  skills-manager = lib.cleanSource ./extensions/skills-manager;
  runtime-model-info = lib.cleanSource ./extensions/runtime-model-info;
  session-capture = lib.cleanSourceWith {
    src = ./extensions/session-capture;
    filter = path: _type:
      let
        name = builtins.baseNameOf (toString path);
      in
      !(name == "session-capture.fixtures.json" || name == "session-capture-check.ts");
  };
}
