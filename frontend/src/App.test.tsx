import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { DashboardData, Kpis } from "./api";

const kpis = (over: Partial<Kpis> = {}): Kpis => ({
  sessions: 100,
  errors: 2,
  errorRate: 0.02,
  adRequests: 200,
  adImpressions: 190,
  adFillRate: 0.95,
  avgStartupMs: 2100,
  rebufferRatio: 0.004,
  ...over,
});

const fixture = (errorRate = 0.0267): DashboardData => ({
  summary: { ...kpis({ sessions: 3599, errorRate }), p95StartupMs: 5952, avgBitrateKbps: 3331.6 },
  timeseries: [
    { ts: "2026-11-12T17:00:00Z", ...kpis() },
    { ts: "2026-11-12T17:05:00Z", ...kpis({ sessions: 120 }) },
  ],
  byDevice: [{ key: "tv", ...kpis() }],
  byCdn: [
    { key: "akamai", ...kpis({ errorRate: 0.013 }) },
    { key: "fastly", ...kpis({ errorRate: 0.054 }) },
  ],
  topErrors: [{ errorCode: "NETWORK_TIMEOUT", count: 41 }],
});

function mockApi(data: DashboardData) {
  const fetchMock = vi.fn().mockImplementation(
    async () => new Response(JSON.stringify({ data }), { status: 200 }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("App", () => {
  beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
  afterEach(() => vi.unstubAllGlobals());

  it("renders KPI tiles from the GraphQL response", async () => {
    mockApi(fixture());
    render(<App />);

    expect(await screen.findByText("3,599")).toBeInTheDocument();
    expect(screen.getByText("2.7%")).toBeInTheDocument();
    expect(screen.getByText("p95 6.0 s")).toBeInTheDocument();
    expect(screen.getByText("NETWORK_TIMEOUT")).toBeInTheDocument();
  });

  it("flags degraded quality with text, not just colour", async () => {
    mockApi(fixture(0.08));
    render(<App />);

    expect(await screen.findByText(/service quality is degraded/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Degraded/).length).toBeGreaterThan(0);
  });

  it("refetches with a new window when the selector changes", async () => {
    const fetchMock = mockApi(fixture());
    render(<App />);
    await screen.findByText("3,599");

    fireEvent.click(screen.getByRole("button", { name: "24 hours" }));

    await waitFor(() => {
      const bodies = fetchMock.mock.calls.map(([, init]) => JSON.parse(init.body).variables);
      expect(bodies).toContainEqual({ w: 1440, step: 60 });
    });
  });

  it("offers a table view of the trends and breakdown", async () => {
    mockApi(fixture());
    render(<App />);
    await screen.findByText("3,599");

    fireEvent.click(screen.getAllByRole("button", { name: "Table" })[0]);
    expect(await screen.findByRole("columnheader", { name: "Ad fill" })).toBeInTheDocument();
  });

  it("shows an error banner when the API fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("boom", { status: 500 })));
    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent("HTTP 500");
  });
});
