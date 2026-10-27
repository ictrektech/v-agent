import { applyUserLocale } from "./locale";

interface LocaleState {
  locale?: unknown;
}
interface LocaleBridge {
  getState?: () => Promise<LocaleState>;
  broadcast?: {
    on: (
      event: string,
      handler: (state: LocaleState) => void,
    ) => (() => void) | void;
  };
}

/** VOS owns the embedded application's language, including live changes. */
export function listenForVosLocale(): () => void {
  let active = true;
  let revision = 0;
  let stop: (() => void) | void;
  let timer: ReturnType<typeof setInterval> | undefined;
  let pending = Promise.resolve();
  const started = Date.now();
  const update = (state: LocaleState) => {
    if (
      typeof state.locale !== "string" ||
      !/^(zh|en)(-|$)/i.test(state.locale)
    )
      return;
    const locale = state.locale;
    pending = pending
      .then(async () => {
        if (active) await applyUserLocale(locale);
      })
      .catch(() => undefined);
  };
  const connect = () => {
    const bridge = (window as unknown as { vos_platform?: LocaleBridge })
      .vos_platform;
    if (!bridge) return false;
    stop = bridge.broadcast?.on("locale-change", (state) => {
      revision++;
      update(state);
    });
    const snapshotRevision = revision;
    void bridge
      .getState?.()
      .then((state) => {
        if (revision === snapshotRevision) update(state);
      })
      .catch(() => undefined);
    return true;
  };
  if (!connect())
    timer = setInterval(() => {
      if (connect() || Date.now() - started >= 10000) clearInterval(timer);
    }, 50);
  return () => {
    active = false;
    clearInterval(timer);
    stop?.();
  };
}
