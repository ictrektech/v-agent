import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { buildDashboardChatWsUrl } from "./wsChat";

vi.mock("../request", () => ({ getAuthToken: () => "fixture-token" }));

beforeEach(() => vi.stubGlobal("BASE_URL", ""));
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("dashboard chat WebSocket routing", () => {
  it("keeps the VOS app prefix so the handshake reaches the app", () => {
    vi.stubEnv("BASE_URL", "/app/com.ictrek.v-octop/");
    const url = new URL(buildDashboardChatWsUrl("fixture-agent"));
    expect(url.pathname).toBe(
      "/app/com.ictrek.v-octop/api/agents/fixture-agent/chat/ws",
    );
    expect(url.searchParams.get("token")).toBe("fixture-token");
  });

  it("still supports a standalone installation", () => {
    vi.stubEnv("BASE_URL", "/");
    expect(new URL(buildDashboardChatWsUrl("fixture-agent")).pathname).toBe(
      "/api/agents/fixture-agent/chat/ws",
    );
  });
});
