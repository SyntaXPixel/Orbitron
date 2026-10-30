import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import { SecurityPage } from "../pages/SecurityPage";
import { mockSnapshot } from "./mocks/fixtures";
import type { SecurityCheck, Transfer } from "../api/types";

let currentSnapshot = mockSnapshot;

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useOutletContext: () => ({
      snapshot: currentSnapshot,
      session: { user: { role: "network_admin" } },
      setActiveOperation: vi.fn(),
    }),
  };
});

describe("Security Evidence & Integrity Verification (Plan Section 11.6 & 16.10)", () => {
  it("renders transfer integrity failure evidence clearly", () => {
    const failedTransfer: Transfer = {
      id: "tx-corrupt-001",
      contact_id: "contact-001",
      owner_org_id: "org-fleet-a",
      partner_station_id: "gs-b-001",
      status: "verification_failed",
      total_bytes: 1_000_000_000,
      forwarded_bytes: 1_000_000_000,
      ciphertext_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      expected_plaintext_sha256: "aaaabbbbccccddddeeeeffff0000111122223333444455556666777788889999",
      owner_plaintext_sha256: "9999888877776666555544443333222211110000ffffeeeeddddccccbbbbaaaa",
      integrity_status: "failed", // FAILED integrity
      owner_decryption_status: "failed",
      partner_key_access: "not_provisioned",
      reasons: [
        {
          code: "PAYLOAD_TAMPERED",
          message: "SHA-256 plaintext checksum mismatch between satellite telemetry and owner decrypted payload.",
          resource_ids: ["tx-corrupt-001"],
        },
      ],
    };

    currentSnapshot = {
      ...mockSnapshot,
      transfers: [failedTransfer],
    };

    renderWithProviders(<SecurityPage />);

    expect(screen.getByText("tx-corrupt-001")).toBeInTheDocument();
    expect(screen.getByText("verification failed")).toBeInTheDocument();
    expect(screen.getAllByText("failed").length).toBeGreaterThanOrEqual(1);
  });

  it("displays demonstration security check with expected rejection verification", () => {
    const passedCheck: SecurityCheck = {
      id: "chk-01",
      test_case: "tampered_payload",
      status: "completed",
      passed: true, // Check passed because expected rejection occurred!
      expected_outcome: "Decryption or hash verification fails; transfer marked verification_failed.",
      observed_outcome: "Owner plaintext checksum mismatch; status set to verification_failed.",
      reasons: [],
    };

    currentSnapshot = {
      ...mockSnapshot,
      security_checks: [passedCheck],
    };

    renderWithProviders(<SecurityPage />);
    expect(screen.getByText(/Test Case: TAMPERED PAYLOAD/i)).toBeInTheDocument();
    expect(screen.getByText(/Expected Rejection Verified/i)).toBeInTheDocument();
  });

  it("includes partner gateway key access disclaimer per plan specification", () => {
    renderWithProviders(<SecurityPage />);
    expect(
      screen.getByText(/Demo configuration: partner gateway was not provisioned a payload decryption key/i)
    ).toBeInTheDocument();
  });
});
