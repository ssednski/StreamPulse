import { describe, expect, it } from "vitest";
import { trimPartialBuckets } from "./series";

describe("trimPartialBuckets", () => {
  it("drops the first and last bucket", () => {
    expect(trimPartialBuckets([1, 2, 3, 4, 5])).toEqual([2, 3, 4]);
  });

  it("leaves very short series alone", () => {
    expect(trimPartialBuckets([1, 2, 3])).toEqual([1, 2, 3]);
    expect(trimPartialBuckets([])).toEqual([]);
  });
});
