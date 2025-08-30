# AGENTS.md

## Build/Test/Lint Commands
This is an opencode configuration directory - no build commands needed.
For testing configurations: manually verify JSON syntax in `opencode.json`

## Code Style Guidelines
- Use JSON format for configuration files
- Follow JSON schema standards for `opencode.json` 
- Use kebab-case for MCP server names (`mcp-server-motherduck`)
- Use snake_case for environment variables (`DEFAULT_MODEL`)
- Maintain proper indentation (2 spaces for JSON)

## Database Query Guidelines
- ONLY use `zen` MCP server for query authoring (has specialized DuckDB model)
- Use `mcp-server-motherduck` ONLY for query execution, never authoring
- Do NOT use general-purpose models (GPT/Claude/etc.) to write DuckDB queries
- When query authoring is requested, use local specialized models via zen server

## Agent Guidelines  
- Reference existing agent definitions in `agent/` directory
- Follow YAML frontmatter format with description field
- Use clear, imperative language in agent descriptions
- Include concrete examples in agent descriptions
- Maintain consistency with commit-message-author and documentation-specialist patterns

## File Organization
- Configuration: `opencode.json` (main config)
- Agent definitions: `agent/*.md` files
- Follow established naming conventions for new agents