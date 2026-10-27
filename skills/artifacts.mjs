/** Octop's authenticated Markdown media/download URL for an agent-produced file. */
export function artifactUrl(path) {
  const agent = process.env.OCTOP_AGENT_ID;
  if (!agent) return undefined;
  return `/api/agents/${encodeURIComponent(agent)}/workspace/download?path=${encodeURIComponent(path)}`;
}
