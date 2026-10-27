import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { buildWsUrl as browser } from "../../hooks/useBrowserStream";
import { buildWsUrl as desktop } from "../../hooks/useDesktopStream";
import { buildWsUrl as mobile } from "../../hooks/useMobileStream";
import { buildWsUrl as terminal } from "../../pages/Control/Terminal/useTerminal";
import { buildWsUrl as adb } from "../../pages/Control/RemoteAndroid/useAdbShell";

vi.mock("../request", () => ({ getAuthToken: () => "fixture-token" }));
beforeEach(() => vi.stubGlobal("BASE_URL", ""));
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

for (const prefix of ["/app/com.ictrek.v-octop", ""]) {
  describe(`control WebSockets under ${prefix || "standalone"}`, () => {
    it.each([
      ["browser", () => browser(1280, 720), "/browser-stream/ws"],
      ["bridge browser", () => browser(1280, 720, "peer"), "/bridge/connections/peer/browser-stream/ws"],
      ["desktop", desktop, "/desktop-stream/ws"],
      ["mobile", mobile, "/mobile-stream/ws"],
      ["terminal", () => terminal("expert", "session"), "/agents/expert/terminal/ws"],
      ["adb", () => adb("device", 120, 32), "/mobile/adb/shell/ws"],
    ] as const)("routes %s through the installed app", (_name, build, path) => {
      vi.stubEnv("BASE_URL", `${prefix}/`);
      expect(new URL(build()).pathname).toBe(`${prefix}/api${path}`);
    });
    it("retains browser authentication and viewport", () => {
      vi.stubEnv("BASE_URL", `${prefix}/`);
      const url = new URL(browser(1280, 720));
      expect(url.searchParams.get("token")).toBe("fixture-token");
      expect(url.searchParams.get("width")).toBe("1280");
      expect(url.searchParams.get("height")).toBe("720");
    });
  });
}
