import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { listResolvedModels, request, getPreferences, t } = vi.hoisted(() => ({
  listResolvedModels: vi.fn(),
  request: vi.fn(),
  getPreferences: vi.fn(),
  t: (key: string) => key,
}));
vi.mock("react-i18next", () => ({ useTranslation: () => ({ t }) }));
vi.mock("../../../api/request", () => ({ request }));
vi.mock("../../../api/modules/provider", () => ({
  providerApi: { listResolvedModels },
}));
vi.mock("../../../api/modules/preferences", () => ({
  preferencesApi: { get: getPreferences },
}));
import { useProviders } from "./useProviders";

describe("managed model list freshness", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    request.mockReset().mockResolvedValue([]);
    getPreferences.mockReset().mockResolvedValue({});
    listResolvedModels.mockReset().mockResolvedValue([]);
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("updates an already-open empty list after Scheduler adds a model", async () => {
    const { result, unmount } = renderHook(() => useProviders());
    await act(async () => {});
    expect(result.current.resolvedModels).toEqual([]);
    const models = [{ id: "com.deepseek.api/deepseek-flash" }];
    listResolvedModels.mockResolvedValue(models);
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(result.current.resolvedModels).toEqual(models);
    expect(result.current.loading).toBe(false);
    unmount();
    const calls = listResolvedModels.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(listResolvedModels).toHaveBeenCalledTimes(calls);
  });

  it("refreshes on return to the page and does not poll hidden pages", async () => {
    const { unmount } = renderHook(() => useProviders());
    await act(async () => {});
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    await act(async () => { await vi.advanceTimersByTimeAsync(20_000); });
    expect(listResolvedModels).toHaveBeenCalledTimes(1);
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
    await act(async () => { document.dispatchEvent(new Event("visibilitychange")); });
    expect(listResolvedModels).toHaveBeenCalledTimes(2);
    await act(async () => { window.dispatchEvent(new Event("focus")); });
    expect(listResolvedModels).toHaveBeenCalledTimes(3);
    unmount();
  });

  it("keeps the last successful list when a background request fails", async () => {
    const models = [{ id: "com.deepseek.api/deepseek-flash" }];
    listResolvedModels.mockResolvedValue(models);
    const { result, unmount } = renderHook(() => useProviders());
    await act(async () => {});
    listResolvedModels.mockRejectedValue(new Error("temporary outage"));
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(result.current.resolvedModels).toEqual(models);
    unmount();
  });
});
