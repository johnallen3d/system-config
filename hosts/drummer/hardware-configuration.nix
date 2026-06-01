{lib, ...}: {
  # Placeholder hardware config kept in-repo so pure `nix flake check` can
  # evaluate `nixosConfigurations.drummer` without reading `/etc`.
  #
  # On the real drummer host, replace these defaults with the generated values
  # from `nixos-generate-config` before relying on this file for a rebuild.
  fileSystems."/" = lib.mkDefault {
    device = "/dev/disk/by-label/nixos";
    fsType = "ext4";
  };

  fileSystems."/boot" = lib.mkDefault {
    device = "/dev/disk/by-label/boot";
    fsType = "vfat";
  };

  swapDevices = lib.mkDefault [];
}
