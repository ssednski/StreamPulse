import { useCallback, useEffect, useRef, useState } from "react";
import { type DashboardData, type WindowOption, fetchDashboard } from "./api";

export interface DashboardState {
  data: DashboardData | null;
  error: string | null;
  loading: boolean;
  updatedAt: Date | null;
  refresh: () => void;
}

export function useDashboard(
  window: WindowOption,
  autoRefresh: boolean,
  intervalMs = 5000,
): DashboardState {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const controller = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    try {
      const next = await fetchDashboard(window, current.signal);
      if (current.signal.aborted) return;
      setData(next);
      setError(null);
      setUpdatedAt(new Date());
    } catch (err) {
      if (current.signal.aborted) return;
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      if (!current.signal.aborted) setLoading(false);
    }
  }, [window]);

  useEffect(() => {
    setLoading(true);
    void load();
    const timer = autoRefresh ? setInterval(() => void load(), intervalMs) : undefined;
    return () => {
      if (timer) clearInterval(timer);
      controller.current?.abort();
    };
  }, [load, autoRefresh, intervalMs]);

  return { data, error, loading, updatedAt, refresh: () => void load() };
}
