import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error: any) => {
        // Do not retry 401s or contract mismatches
        if (error?.status === 401 || error?.isContractMismatch) return false;
        return failureCount < 2;
      },
      refetchOnWindowFocus: true,
      staleTime: 1000,
    },
    mutations: {
      retry: false,
    },
  },
});

export const Providers: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};
