import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, WINDOWS, fetchDashboard } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("fetchDashboard", () => {
  it("sends window and step as GraphQL variables", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ data: { summary: { sessions: 1 } } }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const data = await fetchDashboard(WINDOWS[2]);

    expect(data).toEqual({ summary: { sessions: 1 } });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/graphql");
    expect(JSON.parse(init.body).variables).toEqual({ w: 360, step: 15 });
  });

  it("surfaces GraphQL errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ errors: [{ message: "window_minutes must be positive" }] })),
      ),
    );
    await expect(fetchDashboard(WINDOWS[0])).rejects.toThrow("window_minutes must be positive");
  });

  it("surfaces HTTP failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("nope", { status: 502 })));
    await expect(fetchDashboard(WINDOWS[0])).rejects.toBeInstanceOf(ApiError);
  });
});
