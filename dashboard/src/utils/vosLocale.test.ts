import { afterEach, describe, expect, it, vi } from "vitest";
import { listenForVosLocale } from "./vosLocale";
const { apply } = vi.hoisted(() => ({
  apply: vi.fn().mockResolvedValue("en"),
}));
vi.mock("./locale", () => ({ applyUserLocale: apply }));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  apply.mockClear();
});

describe("VOS locale", () => {
  it("uses the snapshot and follows live changes, then unsubscribes", async () => {
    let handler!: (state: { locale: string }) => void;
    const unsubscribe = vi.fn();
    vi.stubGlobal("window", {
      vos_platform: {
        getState: async () => ({ locale: "en-US" }),
        broadcast: {
          on: (_event: string, callback: typeof handler) => {
            handler = callback;
            return unsubscribe;
          },
        },
      },
    });
    const stop = listenForVosLocale();
    await vi.waitFor(() => expect(apply).toHaveBeenCalledWith("en-US"));
    handler({ locale: "zh-CN" });
    await vi.waitFor(() => expect(apply).toHaveBeenLastCalledWith("zh-CN"));
    stop();
    expect(unsubscribe).toHaveBeenCalledOnce();
  });

  it("does not overwrite a newer notification with a late initial snapshot", async () => {
    let snapshot!: (state: { locale: string }) => void;
    let handler!: (state: { locale: string }) => void;
    vi.stubGlobal("window", {
      vos_platform: {
        getState: () =>
          new Promise((resolve) => {
            snapshot = resolve;
          }),
        broadcast: {
          on: (_event: string, callback: typeof handler) => {
            handler = callback;
          },
        },
      },
    });
    const stop = listenForVosLocale();
    handler({ locale: "en" });
    snapshot({ locale: "zh-CN" });
    await vi.waitFor(() => expect(apply).toHaveBeenCalledOnce());
    expect(apply).toHaveBeenCalledWith("en");
    stop();
  });
});
