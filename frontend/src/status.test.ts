import { describe, expect, it } from "vitest";
import { adFillStatus, errorRateStatus, rebufferStatus, startupStatus } from "./status";

describe("status thresholds", () => {
  it.each([
    [0.01, "good"],
    [0.02, "warning"],
    [0.049, "warning"],
    [0.05, "critical"],
  ])("error rate %s is %s", (rate, expected) => {
    expect(errorRateStatus(rate)).toBe(expected);
  });

  it.each([
    [2000, "good"],
    [2500, "warning"],
    [4000, "critical"],
  ])("start time %s ms is %s", (ms, expected) => {
    expect(startupStatus(ms)).toBe(expected);
  });

  it("treats a window with no ad requests as healthy rather than 0% fill", () => {
    expect(adFillStatus(0, 0)).toBe("good");
    expect(adFillStatus(0.85, 100)).toBe("warning");
    expect(adFillStatus(0.7, 100)).toBe("critical");
  });

  it("flags rebuffering", () => {
    expect(rebufferStatus(0.005)).toBe("good");
    expect(rebufferStatus(0.03)).toBe("critical");
  });
});
