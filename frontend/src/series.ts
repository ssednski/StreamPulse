/**
 * The first and last buckets of a window are partial (the window starts and "now" falls
 * mid-bucket), so they understate counts and look like a crash at the right edge.
 * Charts hide them; the table view still shows every bucket.
 */
export function trimPartialBuckets<T>(points: T[]): T[] {
  return points.length > 3 ? points.slice(1, -1) : points;
}
