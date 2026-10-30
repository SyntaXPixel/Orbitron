import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import { QUERY_KEYS } from "./queries";
import type {
  CreateDisruptionEventRequest,
  CreateJobRequest,
  CreateTransferRequest,
  Job,
  LoginRequest,
  Operation,
  RunEvaluationRequest,
  RunScheduleRequest,
  RunSecurityCheckRequest,
  Session,
  SimulationActionRequest,
} from "./types";
import { ApiClientError } from "../utils/errors";

export function useLoginMutation() {
  const queryClient = useQueryClient();
  return useMutation<Session, ApiClientError, LoginRequest>({
    mutationFn: (credentials) => apiClient.login(credentials),
    onSuccess: (session) => {
      queryClient.setQueryData(QUERY_KEYS.session, session);
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.snapshot });
    },
  });
}

export function useLogoutMutation() {
  const queryClient = useQueryClient();
  return useMutation<void, ApiClientError, void>({
    mutationFn: () => apiClient.logout(),
    onSettled: () => {
      queryClient.setQueryData(QUERY_KEYS.session, null);
      queryClient.removeQueries({ queryKey: QUERY_KEYS.snapshot });
    },
  });
}

export function useCreateJobMutation() {
  const queryClient = useQueryClient();
  return useMutation<Job, ApiClientError, CreateJobRequest>({
    mutationFn: (payload) => apiClient.createJob(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.snapshot });
    },
  });
}

export function useRunScheduleMutation() {
  const queryClient = useQueryClient();
  return useMutation<Operation, ApiClientError, RunScheduleRequest>({
    mutationFn: (payload) => apiClient.runSchedule(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.snapshot });
    },
    onError: (err) => {
      if (err.status === 409 || err.code === "STALE_SCHEDULE") {
        queryClient.invalidateQueries({ queryKey: QUERY_KEYS.snapshot });
      }
    },
  });
}

export function useCreateDisruptionMutation() {
  const queryClient = useQueryClient();
  return useMutation<Operation, ApiClientError, CreateDisruptionEventRequest>({
    mutationFn: (payload) => apiClient.createDisruptionEvent(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.snapshot });
    },
    onError: (err) => {
      if (err.status === 409) {
        queryClient.invalidateQueries({ queryKey: QUERY_KEYS.snapshot });
      }
    },
  });
}

export function useSimulationActionMutation() {
  const queryClient = useQueryClient();
  return useMutation<Operation, ApiClientError, SimulationActionRequest>({
    mutationFn: (payload) => apiClient.simulationAction(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.snapshot });
    },
  });
}

export function useCreateTransferMutation() {
  const queryClient = useQueryClient();
  return useMutation<Operation, ApiClientError, CreateTransferRequest>({
    mutationFn: (payload) => apiClient.createTransfer(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.snapshot });
    },
  });
}

export function useRunSecurityCheckMutation() {
  const queryClient = useQueryClient();
  return useMutation<Operation, ApiClientError, RunSecurityCheckRequest>({
    mutationFn: (payload) => apiClient.runSecurityCheck(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.snapshot });
    },
  });
}

export function useRunEvaluationMutation() {
  const queryClient = useQueryClient();
  return useMutation<Operation, ApiClientError, RunEvaluationRequest>({
    mutationFn: (payload) => apiClient.runEvaluation(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.snapshot });
    },
  });
}
