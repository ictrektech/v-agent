/** VOS package version and public releases from this fork only. */
const SOURCE = 'https://github.com/ictrektech/v-agent/releases';
let cached;
export async function releaseStatus(current, { force = false, fetcher = fetch } = {}) {
  if (!force && cached && cached.current_version === current && Date.now() - cached.checked < 300000) return cached;
  const value = { current_version: current, latest_version: null, has_update: false, is_editable: false,
    service_mode: null, desktop: false, source: SOURCE, last_check_time: new Date().toISOString(),
    release_notes: null, stable_only: true, error: null, error_code: null };
  try {
    const response = await fetcher('https://api.github.com/repos/ictrektech/v-agent/releases/latest', {
      headers: { accept: 'application/vnd.github+json' }, signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) throw new Error(`GitHub release: HTTP ${response.status}`);
    const release = await response.json();
    const version = String(release.tag_name ?? '').replace(/^v/, '');
    if (!/^\d+\.\d+\.\d+$/.test(version) || release.draft || release.prerelease ||
      !release.assets?.some(asset => asset.name === `v-agent_${version}_pull.tar`)) throw new Error('No stable VOS package release');
    value.latest_version = version;
    const a = version.split('.').map(Number), b = current.split('.').map(Number);
    value.has_update = a.some((n,i) => n > b[i] && a.slice(0,i).every((n,j) => n === b[j]));
    value.release_notes = release.body ?? null;
  } catch (error) { value.error = error.message; value.error_code = 'fork_release_unreachable'; }
  cached = { ...value, checked: Date.now() };
  return cached;
}
