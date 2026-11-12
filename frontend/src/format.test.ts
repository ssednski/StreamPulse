import { describe, expect, it } from "vitest";
import { formatBitrate, formatInt, formatMs, formatPercent } from "./format";

describe("formatters", () => {
  it("formats integers with separators", () => {
    expect(formatInt(3599)).toBe("3,599");
    expect(formatInt(12.4)).toBe("12");
  });

  it("formats ratios as percentages", () => {
    expect(formatPercent(0.0267)).toBe("2.7%");
    expect(formatPercent(0.0076, 2)).toBe("0.76%");
    expect(formatPercent(1, 0)).toBe("100%");
  });

  it("switches between ms and seconds", () => {
    expect(formatMs(850)).toBe("850 ms");
    expect(formatMs(2605.9)).toBe("2.6 s");
  });

  it("formats bitrate in kbps or Mbps", () => {
    expect(formatBitrate(800)).toBe("800 kbps");
    expect(formatBitrate(3331.6)).toBe("3.3 Mbps");
  });
});
