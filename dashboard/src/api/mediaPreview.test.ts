import { beforeEach, describe, expect, it, vi } from "vitest";
const { requestBlob } = vi.hoisted(() => ({ requestBlob: vi.fn() }));
vi.mock("./request", () => ({ requestBlob }));
import { requestMediaBlob } from "./mediaPreview";
const original = "file:///home/current/workspace/output/kitten_window.png";
const preview = `/agents/expert/media/preview?${new URLSearchParams({
  source: original,
})}`;
describe("delivered media compatibility", () => {
  beforeEach(() => {
    requestBlob.mockReset();
  });
  it("uses the existing authorized download for an old absolute preview returning 404", async () => {
    const png = new Blob(["PNG"]);
    requestBlob
      .mockRejectedValueOnce(new Error("404 NOT_FOUND"))
      .mockResolvedValueOnce(png);
    expect(await requestMediaBlob(preview)).toBe(png);
    const path = requestBlob.mock.calls[1][0];
    expect(path).toMatch(/^\/agents\/expert\/workspace\/download\?/);
    expect(new URLSearchParams(path.split("?")[1]).get("path")).toBe(original);
  });
  it.each(["401 Unauthorized", "403 Forbidden", "500 Server error"])(
    "does not retry %s",
    async (message) => {
      requestBlob.mockRejectedValue(new Error(message));
      await expect(requestMediaBlob(preview)).rejects.toThrow(message);
      expect(requestBlob).toHaveBeenCalledTimes(1);
    },
  );
  it.each(["outbound/deleted.png", "https://example.com/image.png"])(
    "does not invent a replacement for %s",
    async (source) => {
      requestBlob.mockRejectedValue(new Error("404 NOT_FOUND"));
      await expect(
        requestMediaBlob(
          `/agents/expert/media/preview?${new URLSearchParams({ source })}`,
        ),
      ).rejects.toThrow();
      expect(requestBlob).toHaveBeenCalledTimes(1);
    },
  );
  it("does not retry a successful preview", async () => {
    const png = new Blob(["PNG"]);
    requestBlob.mockResolvedValue(png);
    expect(await requestMediaBlob(preview)).toBe(png);
    expect(requestBlob).toHaveBeenCalledTimes(1);
  });
});
