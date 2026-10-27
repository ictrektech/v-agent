/** Keep the application session aligned with the platform's current account. */
interface VosBridge {
  platform?: {
    getUser?: () => Promise<{ sub?: string; id?: string | number } | null>;
  };
  broadcast?: {
    on?: (event: string, callback: () => void) => (() => void) | void;
  };
}

export async function checkVosAccount(subject: string): Promise<() => void> {
  const base = import.meta.env.BASE_URL;
  const reset = async () => {
    await fetch(`${base}__va/logout`, {
      method: "POST",
      credentials: "same-origin",
    });
    window.location.reload();
  };
  const deadline = Date.now() + 4000;
  let bridge: VosBridge | undefined;
  while (Date.now() < deadline) {
    bridge = (window as unknown as { vos_platform?: VosBridge }).vos_platform;
    if (bridge) break;
    await new Promise((resolve) => window.setTimeout(resolve, 50));
  }
  if (!bridge) return () => {};
  const verify = async () => {
    if (!bridge?.platform?.getUser) return;
    const user = await bridge.platform.getUser();
    if (!user || String(user.sub ?? user.id ?? "") !== subject) await reset();
  };
  const unsubscribe = bridge.broadcast?.on?.("user-change", () => {
    void verify();
  });
  await verify();
  return typeof unsubscribe === "function" ? unsubscribe : () => {};
}
