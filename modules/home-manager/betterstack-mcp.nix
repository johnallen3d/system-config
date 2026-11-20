# Better Stack's remote MCP, shared by the Claude and Pi work profiles. OAuth
# tokens stay in each harness's machine-local credential store, never in Nix.
# X-MCP-Tools-Only limits the server to a read-only allowlist; its full
# catalog (158 tools) would load ~75k tokens of schemas per Claude session:
# https://betterstack.com/docs/getting-started/integrations/mcp/
{
  url = "https://mcp.betterstack.com";
  headers."X-MCP-Tools-Only" = builtins.concatStringsSep "," [
    "documentation"
    "teams"
    "sources"
    "source_fields"
    "query"
    "query_windows"
    "query_help"
    "metrics_query_help"
    "errors_query_help"
    "applications"
    "errors"
    "error"
    "incidents"
    "incident"
    "incident_timeline"
    "incident_comments"
    "monitors"
    "monitor"
    "on_calls"
    "on_call"
  ];
}
