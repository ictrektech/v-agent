import { afterEach, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api/modules/auth", () => ({
  authApi: {
    getAuthStatus: vi.fn().mockResolvedValue({ setup_required: false }),
    me: vi
      .fn()
      .mockResolvedValue({
        id: 1,
        username: "vos",
        role: "admin",
        locale: "en",
      }),
  },
}));
vi.mock("../api/request", () => ({
  getAuthToken: vi.fn(() => "runtime-token"),
  clearAuthToken: vi.fn(),
  setAuthToken: vi.fn(),
}));
vi.mock("../utils/vosSession", () => ({
  checkVosAccount: vi.fn().mockResolvedValue(() => {}),
}));
vi.mock("../utils/locale", () => ({
  applyUserLocale: vi.fn().mockResolvedValue("en"),
}));

import AuthGuard from "./AuthGuard";
import { clearAuthToken, setAuthToken } from "../api/request";
import { checkVosAccount } from "../utils/vosSession";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  localStorage.clear();
});

it("enters through the VOS gateway session and clears the previous account before mounting", async () => {
  vi.stubEnv("VITE_VOS", "1");
  localStorage.setItem("v-agent:namespace", "previous-account");
  const request = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      access_token: "own-runtime-token",
      namespace: "current-account",
      subject: "current-subject",
    }),
  });
  vi.stubGlobal("fetch", request);
  render(
    <MemoryRouter>
      <AuthGuard>
        <div>VOS workspace</div>
      </AuthGuard>
    </MemoryRouter>,
  );
  expect(await screen.findByText("VOS workspace")).toBeInTheDocument();
  expect(clearAuthToken).toHaveBeenCalledOnce();
  expect(checkVosAccount).toHaveBeenCalledWith("current-subject");
  expect(setAuthToken).toHaveBeenCalledWith("own-runtime-token", false);
  expect(localStorage.getItem("v-agent:namespace")).toBe("current-account");
});
