import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { apiClient } from "./client";
import type { Session, Snapshot, Operation, HealthResponse } from "./types";
import { ApiClientError } from "../utils/errors";

export const QUERY_KEYS = {
  health: ["health"] as const,
  session: ["session"] as const,
  snapshot: ["snapshot"] as const,
  operation: (id: string) => ["operation", id] as const,
};

export function useHealth() {
  return useQuery<HealthResponse, ApiClientError>({
    queryKey: QUERY_KEYS.health,
    queryFn: () => apiClient.getHealth(),
    retry: 1,
    refetchInterval: 10000,
  });
}

export function useSession() {
  return useQuery<Session, ApiClientError>({
    queryKey: QUERY_KEYS.session,
    queryFn: () => apiClient.getSession(),
    retry: false,
    staleTime: Infinity,
  });
}

/**
 * useSnapshot hook handles:
 * - Polling every 2s while page is visible and user is authenticated
 * - Retaining last successful data during temporary errors
 * - Ensuring older state_revision never overwrites newer state_revision
 */
export function useSnapshot(enabled = true, range?: { from?: string; to?: string }) {
  const queryClient = useQueryClient();
  const latestRevisionRef = useRef<number>(-1);
  const lastSuccessfulAtRef = useRef<number>(Date.now());

  const query = useQuery<Snapshot, ApiClientError>({
    queryKey: QUERY_KEYS.snapshot,
    queryFn: async () => {
      const result = await apiClient.getSnapshot(range);
      const revision = result.meta?.state_revision ?? 0;
      if (revision < latestRevisionRef.current) {
        // Return existing snapshot from cache to prevent stale overwrite
        const cached = queryClient.getQueryData<Snapshot>(QUERY_KEYS.snapshot);
        if (cached) return cached;
      }
      latestRevisionRef.current = Math.max(latestRevisionRef.current, revision);
      lastSuccessfulAtRef.current = Date.now();
      return result;
    },
    enabled,
    refetchInterval: (query) => {
      // If 401 session expired, stop polling
      if (query.state.error && query.state.error.status === 401) {
        return false;
      }
      return 2000;
    },
    refetchIntervalInBackground: false, // pauses when tab is hidden
    refetchOnWindowFocus: true, // refreshes immediately when tab becomes visible
    retry: (failureCount, error) => {
      if (error.status === 401 || error.isContractMismatch) return false;
      return failureCount < 3;
    },
  });

  useEffect(() => {
    if (query.data?.meta?.state_revision !== undefined) {
      latestRevisionRef.current = Math.max(latestRevisionRef.current, query.data.meta.state_revision);
    }
  }, [query.data]);

  return {
    ...query,
    lastSuccessfulAt: lastSuccessfulAtRef.current,
    isStaleData: Boolean(query.isError && query.data),
  };
}

export function useOperation(operationId: string | null, enabled = true) {
  return useQuery<Operation, ApiClientError>({
    queryKey: QUERY_KEYS.operation(operationId || ""),
    queryFn: () => apiClient.getOperation(operationId!),
    enabled: Boolean(operationId && enabled),
    refetchInterval: (query) => {
      const op = query.state.data;
      if (op && (op.status === "succeeded" || op.status === "failed")) {
        return false;
      }
      return 1500;
    },
  });
}
