# v-agent

An Octop-based VOS AI assistant with separate experts, conversations, memory, databases and workspaces for each user.

Open v-agent in VOS. Platform identity signs in silently. Choose the default assistant or create an expert, describe a task, and manage generated files in the expert workspace.

V-Scheduler models visible to the current VOS user refresh every minute. Chat Completions, Responses and Messages interfaces require no separate model API key. Vision models retain their image input metadata. Completion-only models are excluded from agent tool execution.

Bundled V-Office, AI Album, HybRAG and Image Studio skills and MCP tools use the current user's authorization. These apps must be installed and accept this OIDC client where restricted. Missing apps, unavailable services and denied permissions produce errors. Third-party connectors retain their own authorization flows.

Each VOS subject has a separate Linux account, mount/PID namespace, Octop process and persistent home. Platform tokens remain in gateway memory. Networking is shared with the app container, and downstream services enforce user permissions.
