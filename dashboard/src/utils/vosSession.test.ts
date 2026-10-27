import { afterEach, describe, expect, it, vi } from "vitest";
import { checkVosAccount } from "./vosSession";

afterEach(() => vi.unstubAllGlobals());

describe("VOS account alignment", () => {
  it("clears the gateway session when the platform switches accounts", async () => {
    const reload = vi.fn();
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    const unsubscribe = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("window", {
      location: { reload },
      vos_platform: {
        platform: { getUser: vi.fn().mockResolvedValue({ sub: "new-user" }) },
        broadcast: { on: vi.fn().mockReturnValue(unsubscribe) },
      },
    });
    const cleanup = await checkVosAccount("previous-user");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("__va/logout"),
      {
        method: "POST",
        credentials: "same-origin",
      },
    );
    expect(reload).toHaveBeenCalledOnce();
    cleanup();
    expect(unsubscribe).toHaveBeenCalledOnce();
  });

  it("keeps a matching platform subject without another login", async () => {
    const reload = vi.fn();
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("window", {
      location: { reload },
      vos_platform: {
        platform: { getUser: vi.fn().mockResolvedValue({ id: 42 }) },
      },
    });
    await checkVosAccount("42");
    expect(fetchMock).not.toHaveBeenCalled();
    expect(reload).not.toHaveBeenCalled();
  });
});
