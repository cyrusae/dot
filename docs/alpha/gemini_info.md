The equivalent command for the **Gemini CLI** (specifically the `@google/gemini-cli` package) requires a few adjustments because Gemini uses a hierarchical configuration system rather than a direct flag for a custom JSON config file.

Here is the closest equivalent command:

```bash
gemini -p "{prompt}" --allowed-mcp-server-names dot --output-format stream-json --approval-mode yolo
```

---

### Breakdown of the Translation

| Claude Flag | Gemini CLI Equivalent | Notes |
| :--- | :--- | :--- |
| `-p "{prompt}"` | **`-p "{prompt}"`** | Works identically for non-interactive prompts. |
| `--mcp-config ./mcp-config.json` | **`.gemini/settings.json`** | Gemini CLI does not have a `--mcp-config` flag. It automatically loads settings from `./.gemini/settings.json`. You must place your MCP server definitions there. |
| `--allowedTools "mcp__dot__*"` | **`--allowed-tools "dot__*"`** | Gemini uses a double underscore (`__`) as the separator for MCP tools. Use `serverName__*` to allow all tools from a specific server. |
| `--output-format stream-json` | **`--output-format stream-json`** | Supported in the latest versions for machine-readable streaming. |
| `--dangerously-skip-permissions` | **`--yolo`** (or **`-y`**) | This enables "Yolo Mode," which auto-approves all tool execution and shell commands. |

### Key Differences to Note

1.  **Config File Location:**
    Since there is no direct flag to point to a specific file like `./mcp-config.json`, the standard workflow is to create a folder named `.gemini` in your current project directory and save your configuration as `settings.json` inside it. Gemini CLI will pick this up automatically as "Workspace Settings," which override your global user settings.
    
    > **Tip:** If you absolutely need to use a specific file path, you can use a symlink: 
    > `ln -s ./mcp-config.json ./.gemini/settings.json && gemini ...`

2.  **Tool Wildcards:**
    In Gemini, the tool's Fully Qualified Name (FQN) follows the format `serverName__toolName`. If your MCP server is named `mcp`, the wildcard `mcp__*` matches all tools provided by that server.

3.  **The Policy Engine:**
    While `--allowed-tools` works for quick one-liners, the Gemini CLI has moved toward a **Policy Engine** for security. For complex permission sets, it is recommended to define a `[[rule]]` in a `.toml` file within `./.gemini/policies/` where you can set `decision = "allow"` for specific tools or servers.

---

In the **Gemini CLI**, the tool prefix is derived directly from the **key (name)** you assign to the server in your `settings.json`. If your server is named `dot`, the tools are namespaced as `dot__tool_name`.

### The Updated Command

Using the most current flags (including the modern replacement for the deprecated `--yolo`), the command would be:

```bash
gemini -p "{prompt}" --allowed-mcp-server-names dot --output-format stream-json --approval-mode yolo
```

---

### Key Details on the Naming

* **The Prefix:** Gemini CLI uses the server name followed by a **double underscore** (`__`). If your server name is `dot`, the wildcard for all its tools is `dot__*`.
* **A Cleaner Way:** Instead of using the `--allowed-tools` wildcard, you can use the newer **`--allowed-mcp-server-names dot`** flag. This explicitly white-lists every tool provided by that specific server name without needing to worry about the underscore syntax.
* **Why Claude used `mcp__dot`:** In some Claude implementations or specific wrapper tools, a global `mcp__` prefix is sometimes added to external tools to distinguish them from native ones. Gemini CLI treats MCP servers as top-level entities, so the name you give it is exactly what it uses.

### Configuration Check

Since Gemini CLI doesn't have a `--mcp-config` flag to point to a random file, ensure your "dot" server is defined in your local workspace settings:

**`./.gemini/settings.json`**

```json
{
  "mcpServers": {
    "dot": {
      "command": "node",
      "args": ["/path/to/your/dot-server/index.js"]
    }
  }
}
```

### Pro-Tip: The Policy Engine

If you find yourself running this command often, you can avoid the long flags entirely by creating a policy file in your project:

**`./.gemini/policies/mcp.toml`**

```toml
[[rule]]
description = "Allow all tools from the dot server"
match = "dot__*"
decision = "allow"
```

With this policy in place, you can drop the `--allowed-mcp-server-names` flag entirely from your CLI calls.
