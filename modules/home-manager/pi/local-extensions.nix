{lib, ...}: {
  skills-manager = lib.cleanSource ./extensions/skills-manager;
  runtime-model-info = lib.cleanSource ./extensions/runtime-model-info;
}
