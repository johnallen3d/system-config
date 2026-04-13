# Pi Nix Integration Skill

Local skill for managing pi packages, extensions, skills, and themes within the nix-darwin system-config project.

## Purpose

This skill bridges the gap between nix declarative configuration and pi's package management system. It provides guidance for:

- Adding pi packages to nix configuration 
- Managing local project skills
- Understanding the integrated pi+nix workflow
- Troubleshooting pi installation issues

## Key Insight

Unlike standard pi usage where you run `pi install npm:package-name` directly, this project declares pi packages in `modules/home-manager/packages/pi.nix` and auto-installs them on first pi run.

## Usage

The skill auto-triggers when you ask about:
- Adding pi packages to this project
- Managing pi extensions or skills locally  
- Understanding pi integration with nix
- Troubleshooting pi in this nix environment

Or invoke explicitly with `/skill:pi-nix-integration`

## Scope

Project-local skill available only within this system-config directory.