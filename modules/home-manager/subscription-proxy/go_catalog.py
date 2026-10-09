"""Pure, deterministic OpenCode Go metadata validation and gateway reconciliation.

models.dev supplies Go-specific SDK/protocol and capability data. The actual Go
model endpoint supplies availability. Never infer a protocol from a model name
or from the pay-as-you-go Zen provider. Unknown metadata is quarantined.
"""
import copy
import re

GO_BASE = "https://opencode.ai/zen/go/v1"
METADATA_URL = "https://models.dev/api.json"
MODELS_URL = GO_BASE + "/models"
SDK_PROTOCOLS = {
    "@ai-sdk/openai-compatible": "chat",
    "@ai-sdk/openai": "responses",
    "@ai-sdk/anthropic": "messages",
}
MANAGED_GROUPS = {"xai": "opencode-go-responses", "claude": "opencode-go-messages"}


def positive_integer(value):
    return type(value) is int and 0 < value <= 10_000_000


def build_catalog(provider, available):
    if not isinstance(provider, dict) or provider.get("id") != "opencode-go" or provider.get("api") != GO_BASE:
        raise ValueError("Invalid Go-specific metadata source; refusing Zen/direct API routes.")
    models = provider.get("models")
    if not isinstance(models, dict) or not models:
        raise ValueError("Empty or invalid Go metadata.")
    if not isinstance(available, list) or not available or len(available) > 1000:
        raise ValueError("Empty or invalid Go availability catalog.")
    if any(not isinstance(i, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", i) for i in available):
        raise ValueError("Invalid Go model identifier.")
    if len(set(available)) != len(available):
        raise ValueError("Duplicate Go model identifiers.")
    entries, excluded = [], []
    for identifier in sorted(available):
        meta = models.get(identifier)
        identity_meta = meta if isinstance(meta, dict) else {}
        identity = " ".join(str(x) for x in (identifier, identity_meta.get("name", ""), identity_meta.get("family", ""))).lower()
        if "claude" in identity or "anthropic" in identity:
            excluded.append({"id": identifier, "reason": "Claude excluded"})
            continue
        if not isinstance(meta, dict) or meta.get("id") != identifier:
            excluded.append({"id": identifier, "reason": "No Go-specific capability/protocol metadata"})
            continue
        override = meta.get("provider") or {}
        if not isinstance(override, dict) or override.get("api", GO_BASE) != GO_BASE:
            raise ValueError("Go model metadata attempts a different upstream endpoint.")
        protocol = SDK_PROTOCOLS.get(override.get("npm", provider.get("npm")))
        if not protocol:
            excluded.append({"id": identifier, "reason": "Unsupported or unknown protocol"})
            continue
        limits, modalities = meta.get("limit", {}), meta.get("modalities", {})
        if (not positive_integer(limits.get("context")) or not positive_integer(limits.get("output"))
                or type(meta.get("reasoning")) is not bool or meta.get("tool_call") is not True
                or "text" not in modalities.get("input", []) or "text" not in modalities.get("output", [])):
            excluded.append({"id": identifier, "reason": "Incomplete or unsupported coding-model capabilities"})
            continue
        name = meta.get("name", identifier)
        if not isinstance(name, str) or len(name) > 200 or any(ord(c) < 32 for c in name):
            raise ValueError("Invalid Go model display name.")
        cost = meta.get("cost", {})
        costs = {}
        for target, source in (("input", "input"), ("output", "output"), ("cacheRead", "cache_read"), ("cacheWrite", "cache_write")):
            value = cost.get(source, 0)
            if type(value) not in (int, float) or not 0 <= value <= 100000:
                raise ValueError("Invalid Go model cost metadata.")
            costs[target] = value
        # Pi's uniform chat transport is translated by the gateway into the
        # model-specific native upstream protocol. This also preserves Pi's
        # session_id across ALL Go models, including Messages and Responses.
        pi = {"id": "go/" + identifier, "name": name, "reasoning": meta["reasoning"],
              "input": [m for m in ("text", "image") if m in modalities["input"]],
              "contextWindow": limits["context"], "maxTokens": min(limits["output"], 32768), "cost": costs}
        entries.append({"id": identifier, "protocol": protocol, "pi": pi})
    if not entries:
        raise ValueError("No validated non-Claude Go models; retaining last-good catalog.")
    return {"version": 1, "models": entries, "excluded": excluded}


def clean_config(value):
    """Drop management-only credential indexes (not writable configuration)."""
    if isinstance(value, dict):
        return {k: clean_config(v) for k, v in value.items() if k != "auth-index"}
    if isinstance(value, list):
        return [clean_config(v) for v in value]
    return value


def routing_config(catalog, api_keys):
    result = clean_config(copy.deepcopy(api_keys))
    providers = result.setdefault("openai-compatibility", [])
    matches = [p for p in providers if p.get("name") == "opencode-go"]
    if len(matches) != 1:
        raise ValueError("Expected exactly one official-UI opencode-go provider.")
    primary = matches[0]
    if primary.get("base-url") != GO_BASE or primary.get("prefix") != "go":
        raise ValueError("Go provider endpoint/prefix diverged; refusing to overwrite operator configuration.")
    headers = copy.deepcopy(primary.get("headers", {}))
    headers.update({"User-Agent": "$User-Agent", "x-opencode-session": "$session_id"})
    keys = [] if primary.get("disabled") else copy.deepcopy(primary.get("keys", []))
    if not isinstance(keys, list):
        raise ValueError("Invalid central Go key configuration.")

    def mappings(protocol):
        return [{"name": e["id"], "alias": e["id"], "display-name": e["pi"]["name"],
                 "max-context-length": e["pi"]["contextWindow"]}
                for e in catalog["models"] if e["protocol"] == protocol]

    primary["models"] = mappings("chat")
    primary["headers"] = headers
    for section, name in MANAGED_GROUPS.items():
        groups = result.setdefault(section, [])
        matches = [g for g in groups if g.get("name") == name]
        if len(matches) > 1:
            raise ValueError("Duplicate managed Go native-protocol group.")
        base = GO_BASE if section == "xai" else GO_BASE.removesuffix("/v1")
        if matches and (matches[0].get("prefix") != "go" or matches[0].get("base-url") != base):
            raise ValueError("Managed Go native group diverged; refusing to overwrite operator configuration.")
        group = matches[0] if matches else {"name": name}
        if not matches:
            groups.append(group)
        native_keys = copy.deepcopy(keys)
        if section == "claude":
            # Go's Messages API requires x-api-key. CLIProxyAPI otherwise
            # chooses Bearer auth on non-api.anthropic.com hosts. v8 supports
            # per-key header overrides: each pooled key gets ITS OWN value,
            # including on rotation. This secret exists only in central config.
            for key in native_keys:
                key_headers = copy.deepcopy(headers)
                key_headers.update(key.get("headers", {}))
                key_headers["x-api-key"] = key["api-key"]
                key["headers"] = key_headers
        group.update({"prefix": "go", "base-url": base, "keys": native_keys,
                      "headers": copy.deepcopy(headers), "models": mappings("responses" if section == "xai" else "messages"),
                      "request-retry": 0})
    # Only these three lists are owned by the reconciler. Preserve every
    # unrelated entry within them and never patch OAuth or other settings.
    return {section: result[section] for section in ("openai-compatibility", "xai", "claude")}
