{lib, ...}: {
  telegram-context-clear = lib.cleanSource ./extensions/telegram-context-clear;
  usage-footer = lib.cleanSource ./extensions/usage-footer;
}
