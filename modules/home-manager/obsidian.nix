{
  lib,
  pkgs,
  ...
}: let
  managedTheme = import ./managed-theme.nix {inherit lib;};
  obsidianConfigDir = "Library/Mobile Documents/iCloud~md~obsidian/Documents/Personal/.obsidian";
  mkObsidianManifest = variant:
    builtins.toJSON {
      name = managedTheme.themeName variant;
      version = "1.0.0";
      minAppVersion = "1.0.0";
      author = "system-config";
      authorUrl = "https://github.com/johnallen3d/system-config";
    }
    + "\n";
  mkObsidianThemeCss = variant: let
    p = managedTheme.palettes.${variant};
  in ''
    body {
      --accent-h: 280;
      --accent-s: 32%;
      --accent-l: 78%;

      --font-text-theme: Inter, sans-serif;
      --font-interface-theme: Inter, sans-serif;

      --background-primary: ${p.bg};
      --background-primary-alt: ${p.bgDark};
      --background-secondary: ${p.bgDark};
      --background-secondary-alt: ${p.bgDark1};
      --background-modifier-border: ${p.border};
      --background-modifier-border-hover: ${p.borderBright};
      --background-modifier-border-focus: ${p.purple};
      --background-modifier-form-field: ${p.bgDark};
      --background-modifier-form-field-highlighted: ${p.bgHighlight};
      --background-modifier-hover: ${p.bgHighlight};
      --background-modifier-active-hover: ${p.bgHighlight};
      --background-modifier-message: ${p.bgHighlight};
      --background-modifier-success: ${p.green};
      --background-modifier-error: ${p.red};
      --background-modifier-error-hover: ${p.redDark};
      --background-modifier-cover: rgba(25, 23, 36, 0.6);
      --background-modifier-box-shadow: rgba(0, 0, 0, 0.3);

      --text-normal: ${p.fg};
      --text-muted: ${p.muted};
      --text-faint: ${p.comment};
      --text-on-accent: ${p.accentText};
      --text-on-accent-inverted: ${p.bg};
      --text-selection: ${p.fg};
      --text-accent: ${p.accent};
      --text-accent-hover: ${p.purple};
      --text-highlight-bg: ${p.selectionBar};
      --text-highlight-fg: ${p.fg};
      --text-error: ${p.red};
      --text-success: ${p.green};
      --text-warning: ${p.yellow};

      --interactive-normal: ${p.bgHighlight};
      --interactive-hover: ${p.bgVisual};
      --interactive-accent: ${p.accent};
      --interactive-accent-hover: ${p.purple};
      --interactive-success: ${p.green};

      --scrollbar-bg: transparent;
      --scrollbar-thumb-bg: ${p.bgVisual};
      --scrollbar-active-thumb-bg: ${p.gutter};

      --titlebar-background: ${p.bgDark1};
      --titlebar-background-focused: ${p.bgDark1};
      --tab-container-background: ${p.bgDark1};
      --tab-background-active: ${p.bg};
      --tab-background-inactive: ${p.bgDark};
      --tab-outline-color: ${p.border};
      --tab-text-color-focused-active: ${p.fg};
      --tab-text-color-focused-active-current: ${p.fg};
      --tab-text-color-focused-active-hover: ${p.fg};
      --tab-text-color-focused: ${p.muted};
      --tab-text-color-focused-highlighted: ${p.accent};

      --nav-item-background-active: ${p.bgHighlight};
      --nav-item-background-hover: ${p.bgVisual};
      --nav-item-color-active: ${p.fg};
      --nav-item-color-hover: ${p.fg};
      --nav-indentation-guide-color: ${p.border};
      --nav-indentation-guide-color-hover: ${p.borderBright};

      --icon-color: ${p.muted};
      --icon-color-hover: ${p.fg};
      --icon-color-active: ${p.accent};
      --icon-color-focused: ${p.accent};

      --h1-color: ${p.purple};
      --h2-color: ${p.blue};
      --h3-color: ${p.cyan};
      --h4-color: ${p.green};
      --h5-color: ${p.yellow};
      --h6-color: ${p.orange};

      --blockquote-border-color: ${p.purple};
      --blockquote-background-color: ${p.bgDark};
      --code-normal: ${p.orange};
      --code-comment: ${p.comment};
      --code-function: ${p.cyan};
      --code-keyword: ${p.purple};
      --code-string: ${p.green};
      --code-value: ${p.orange};
      --link-color: ${p.blue};
      --link-color-hover: ${p.cyan};
      --tag-color: ${p.purple};
      --tag-background: ${p.bgHighlight};
      --hr-color: ${p.border};
      --table-border-color: ${p.border};
      --table-header-border-color: ${p.borderBright};
      --table-row-alt-background: ${p.bgDark};
      --list-marker-color: ${p.purple};
      --metadata-label-text-color: ${p.muted};
      --metadata-input-text-color: ${p.fg};
      --metadata-input-background-active: ${p.bgHighlight};
      --prompt-border-color: ${p.border};
      --prompt-background: ${p.bgDark1};
      --modal-border-color: ${p.border};
      --modal-background: ${p.bg};
      --ribbon-background: ${p.bgDark1};
      --ribbon-background-collapsed: ${p.bgDark1};
    }

    .theme-dark {
      color-scheme: dark;
    }
  '';
  obsidianAppearance =
    builtins.toJSON {
      accentColor = "";
      baseFontSize = 17;
      cssTheme = managedTheme.activeTheme.name;
      enabledCssSnippets = ["tasks"];
      nativeMenus = true;
      showViewHeader = true;
      textFontFamily = "Inter";
      theme = "obsidian";
    }
    + "\n";
  obsidianThemeFiles = lib.mergeAttrsList (map (variant: {
      "${obsidianConfigDir}/themes/${managedTheme.themeName variant}/manifest.json".text = mkObsidianManifest variant;
      "${obsidianConfigDir}/themes/${managedTheme.themeName variant}/theme.css".text = mkObsidianThemeCss variant;
    }) managedTheme.variantNames);
in {
  home.file = lib.mkIf pkgs.stdenv.isDarwin (
    {
      "${obsidianConfigDir}/appearance.json" = {
        force = true;
        text = obsidianAppearance;
      };
    }
    // obsidianThemeFiles
  );
}
