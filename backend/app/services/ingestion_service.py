import hashlib
import json
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session as DBSession

from app.db.models import (
    IngestionEvent, ApplicationState, ServicePrincipal, Satellite as DBSatellite,
    SatelliteObservation, Station as DBStation, Contact as DBContact, Job as DBJob,
    ContactProgress as DBContactProgress, Transfer as DBTransfer, ServiceCommand as DBServiceCommand,
    Organization as DBOrg, Antenna as DBAntenna, SatelliteOrbit as DBSatelliteOrbit,
    AuditEntry
)
from app.schemas.ingestion import (
    CatalogIngestRequest, TelemetryIngestRequest, StationHeartbeatRequest,
    ContactProgressRequest, TickIngestRequest, CommandAckRequest,
    TransferProgressRequest, DeliveryReceiptRequest
)
from app.services.snapshot_service import parse_iso_z, to_iso_z, SnapshotService
from app.services.idempotency import canonical_hash

class IngestionService:
    @classmethod
    def check_deduplication(
        cls,
        db: DBSession,
        principal_id: str,
        event_id: str,
        scenario_id: str,
        endpoint: str,
        payload_data: Any
    ) -> Tuple[bool, Optional[str]]:
        """
        Returns (is_duplicate, error_code).
        If (False, None): new event, not a duplicate.
        If (True, None): idempotent duplicate, should return success.
        If (False, error_code): conflict.
        """
        app_state = SnapshotService.get_app_state(db)
        if app_state.current_scenario_id and scenario_id != app_state.current_scenario_id:
            return False, "SCENARIO_CHANGED"

        payload_h = canonical_hash(payload_data)
        existing = (
            db.query(IngestionEvent)
            .filter(
                IngestionEvent.scenario_id == scenario_id,
                IngestionEvent.principal_id == principal_id,
                IngestionEvent.event_id == event_id
            )
            .first()
        )

        if existing:
            if existing.payload_hash == payload_h:
                return True, None
            else:
                return False, "EVENT_PAYLOAD_MISMATCH"

        # Record new ingestion event
        ev = IngestionEvent(
            id=f"ingest-{secrets.token_hex(8)}",
            scenario_id=scenario_id,
            principal_id=principal_id,
            event_id=event_id,
            endpoint=endpoint,
            payload_hash=payload_h,
            created_at=datetime.now(timezone.utc)
        )
        db.add(ev)
        return False, None

    @classmethod
    def ingest_catalog(
        cls,
        db: DBSession,
        principal: ServicePrincipal,
        req: CatalogIngestRequest
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        if principal.category != "simulator_controller":
            return False, "FORBIDDEN", "Only simulator controller can register catalogue."

        is_dup, err = cls.check_deduplication(db, principal.id, req.event_id, req.scenario_id, "catalog", req.model_dump())
        if is_dup:
            return True, None, None
        if err:
            return False, err, "Event rejected due to deduplication or scenario conflict"

        for org_data in req.organizations:
            existing_org = db.query(DBOrg).filter(DBOrg.id == org_data["id"]).first()
            if not existing_org:
                db.add(DBOrg(id=org_data["id"], name=org_data["name"]))

        for sat_data in req.satellites:
            existing_sat = db.query(DBSatellite).filter(DBSatellite.id == sat_data["id"]).first()
            if not existing_sat:
                db.add(DBSatellite(
                    id=sat_data["id"],
                    name=sat_data["name"],
                    owner_org_id=sat_data["owner_org_id"],
                    supported_bands_json=sat_data.get("supported_bands", []),
                    max_downlink_rate_bps=sat_data.get("max_downlink_rate_bps", 100_000_000),
                    max_parallel_contacts=sat_data.get("max_parallel_contacts", 1),
                    onboard_bytes=sat_data.get("onboard_bytes", 10_000_000_000),
                    operational_status=sat_data.get("operational_status", "available"),
                    orbit_source=sat_data.get("orbit_source", "synthetic"),
                    source="simulated"
                ))

        for st_data in req.stations:
            existing_st = db.query(DBStation).filter(DBStation.id == st_data["id"]).first()
            if not existing_st:
                station_obj = DBStation(
                    id=st_data["id"],
                    name=st_data["name"],
                    owner_org_id=st_data["owner_org_id"],
                    latitude_deg=st_data["latitude_deg"],
                    longitude_deg=st_data["longitude_deg"],
                    min_elevation_deg=st_data.get("min_elevation_deg", 5.0),
                    operational_status=st_data.get("operational_status", "online"),
                    weather_capacity_factor=st_data.get("weather_capacity_factor", 1.0),
                    sharing_enabled=st_data.get("sharing_enabled", False)
                )
                db.add(station_obj)
                for ant_data in st_data.get("antennas", []):
                    db.add(DBAntenna(
                        id=ant_data["id"],
                        station_id=st_data["id"],
                        name=ant_data["name"],
                        supported_bands_json=ant_data.get("supported_bands", []),
                        max_rate_bps=ant_data.get("max_rate_bps", 150_000_000),
                        setup_seconds=ant_data.get("setup_seconds", 60),
                        status=ant_data.get("status", "available")
                    ))

        for orb in req.orbit_definitions:
            existing_orb = db.query(DBSatelliteOrbit).filter(DBSatelliteOrbit.id == orb.get("id", orb.get("satellite_id"))).first()
            if not existing_orb:
                db.add(DBSatelliteOrbit(
                    id=orb.get("id", f"orbit-{secrets.token_hex(6)}"),
                    satellite_id=orb["satellite_id"],
                    format=orb.get("format", "tle"),
                    line1=orb.get("line1", ""),
                    line2=orb.get("line2", ""),
                    epoch_at=parse_iso_z(orb["epoch_at"]),
                    orbit_source=orb.get("orbit_source", "synthetic")
                ))

        app_state = SnapshotService.get_app_state(db)
        app_state.state_revision += 1
        db.commit()
        return True, None, None

    @classmethod
    def ingest_telemetry(
        cls,
        db: DBSession,
        principal: ServicePrincipal,
        req: TelemetryIngestRequest
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        # Permission check: simulator_controller or matching satellite principal
        if principal.category not in ["simulator_controller", "satellite"]:
            return False, "FORBIDDEN", "Principal not permitted to report satellite telemetry"

        is_dup, err = cls.check_deduplication(db, principal.id, req.event_id, req.scenario_id, "telemetry", req.model_dump())
        if is_dup:
            return True, None, None
        if err:
            return False, err, "Event rejected due to deduplication or scenario conflict"

        sat = db.query(DBSatellite).filter(DBSatellite.id == req.satellite_id).first()
        if not sat:
            return False, "NOT_FOUND", f"Satellite {req.satellite_id} not registered"

        # Check monotonic counter
        if req.generated_bytes_total < sat.generated_bytes_total:
            return False, "COUNTER_REGRESSION", "generated_bytes_total cannot regress"

        obs_time = parse_iso_z(req.observed_at)
        delta_generated = req.generated_bytes_total - sat.generated_bytes_total
        sat.generated_bytes_total = req.generated_bytes_total
        sat.onboard_bytes += delta_generated

        sat.operational_status = req.operational_status
        sat.last_telemetry_at = obs_time

        if req.position:
            sat.position_lat = req.position.latitude_deg
            sat.position_lon = req.position.longitude_deg
            sat.position_alt = req.position.altitude_km
            sat.position_observed_at = parse_iso_z(req.position.observed_at)

        obs = SatelliteObservation(
            id=f"obs-{secrets.token_hex(6)}",
            event_id=req.event_id,
            scenario_id=req.scenario_id,
            satellite_id=sat.id,
            observed_at=obs_time,
            operational_status=req.operational_status,
            position_lat=req.position.latitude_deg if req.position else None,
            position_lon=req.position.longitude_deg if req.position else None,
            position_alt=req.position.altitude_km if req.position else None,
            generated_bytes_total=req.generated_bytes_total
        )
        db.add(obs)

        app_state = SnapshotService.get_app_state(db)
        app_state.state_revision += 1
        db.commit()
        return True, None, None

    @classmethod
    def ingest_station_heartbeat(
        cls,
        db: DBSession,
        principal: ServicePrincipal,
        req: StationHeartbeatRequest
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        if principal.category not in ["simulator_controller", "station_gateway"]:
            return False, "FORBIDDEN", "Principal not permitted to report station heartbeats"

        is_dup, err = cls.check_deduplication(db, principal.id, req.event_id, req.scenario_id, "heartbeat", req.model_dump())
        if is_dup:
            return True, None, None
        if err:
            return False, err, "Event rejected due to deduplication or scenario conflict"

        st = db.query(DBStation).filter(DBStation.id == req.station_id).first()
        if not st:
            return False, "NOT_FOUND", f"Station {req.station_id} not registered"

        # Record receipt time in server time
        server_now = datetime.now(timezone.utc)
        st.last_heartbeat_at = server_now
        st.operational_status = req.operational_status
        st.connection_status = "connected"

        db.commit()
        return True, None, None

    @classmethod
    def ingest_contact_progress(
        cls,
        db: DBSession,
        principal: ServicePrincipal,
        req: ContactProgressRequest
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        if principal.category not in ["simulator_controller", "station_gateway"]:
            return False, "FORBIDDEN", "Principal not permitted to report contact progress"

        is_dup, err = cls.check_deduplication(db, principal.id, req.event_id, req.scenario_id, "progress", req.model_dump())
        if is_dup:
            return True, None, None
        if err:
            return False, err, "Event rejected due to deduplication or scenario conflict"

        contact = db.query(DBContact).filter(DBContact.id == req.contact_id).first()
        if not contact:
            return False, "NOT_FOUND", f"Contact {req.contact_id} not found"

        if contact.status not in ["confirmed", "active", "completed"]:
            return False, "INVALID_STATE", f"Contact {contact.id} is in status {contact.status} and cannot accept progress"

        # Check interval falls within contact
        int_start = parse_iso_z(req.interval_start_at)
        int_end = parse_iso_z(req.interval_end_at)
        c_start = contact.start_at if contact.start_at.tzinfo else contact.start_at.replace(tzinfo=timezone.utc)
        c_end = contact.end_at if contact.end_at.tzinfo else contact.end_at.replace(tzinfo=timezone.utc)

        if int_start < c_start or int_end > c_end:
            return False, "INTERVAL_OUT_OF_BOUNDS", "Progress interval falls outside contact window"

        if req.cumulative_transferred_bytes < contact.transferred_bytes:
            return False, "COUNTER_REGRESSION", "cumulative_transferred_bytes cannot regress"

        delta = req.cumulative_transferred_bytes - contact.transferred_bytes
        contact.transferred_bytes = req.cumulative_transferred_bytes
        contact.status = "active" if not req.final else "completed"

        job = contact.job
        job.delivered_bytes = min(job.requested_bytes, job.delivered_bytes + delta)
        job.remaining_bytes = max(0, job.requested_bytes - job.delivered_bytes)

        if job.remaining_bytes == 0:
            job.status = "completed"
            # Deduct from satellite onboard data
            sat = contact.job.satellite
            sat.onboard_bytes = max(0, sat.onboard_bytes - delta)
            sat.reserved_bytes = max(0, sat.reserved_bytes - delta)

        progress_record = DBContactProgress(
            id=f"prog-{secrets.token_hex(6)}",
            event_id=req.event_id,
            scenario_id=req.scenario_id,
            contact_id=contact.id,
            interval_start_at=int_start,
            interval_end_at=int_end,
            cumulative_transferred_bytes=req.cumulative_transferred_bytes,
            delta_bytes=delta,
            is_final=req.final
        )
        db.add(progress_record)

        app_state = SnapshotService.get_app_state(db)
        app_state.state_revision += 1
        db.commit()
        return True, None, None

    @classmethod
    def ingest_ticks(
        cls,
        db: DBSession,
        principal: ServicePrincipal,
        req: TickIngestRequest
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        if principal.category != "simulator_controller":
            return False, "FORBIDDEN", "Only simulator controller can submit atomic ticks"

        app_state = SnapshotService.get_app_state(db)
        if app_state.simulation_run_state == "paused":
            return False, "SIMULATION_PAUSED", "Simulation is paused. Ordinary ticks cannot advance time."

        sim_time = app_state.simulation_time
        if sim_time.tzinfo is None:
            sim_time = sim_time.replace(tzinfo=timezone.utc)

        prev_time = parse_iso_z(req.previous_simulation_time)
        new_time = parse_iso_z(req.simulation_time)

        if prev_time != sim_time:
            return False, "TIME_MISMATCH", f"previous_simulation_time ({req.previous_simulation_time}) does not match current state ({to_iso_z(sim_time)})"

        step_sec = (new_time - prev_time).total_seconds()
        if step_sec <= 0 or step_sec > 60:
            return False, "INVALID_STEP", "Simulation tick step must be positive and at most 60 simulation seconds"

        is_dup, err = cls.check_deduplication(db, principal.id, req.event_id, req.scenario_id, "ticks", req.model_dump())
        if is_dup:
            return True, None, None
        if err:
            return False, err, "Event rejected due to deduplication or scenario conflict"

        # Advance simulation time
        app_state.simulation_time = new_time
        app_state.state_revision += 1

        # Process telemetry
        for t_req in req.telemetry:
            cls.ingest_telemetry(db, principal, t_req)

        # Process heartbeats
        for h_req in req.station_heartbeats:
            cls.ingest_station_heartbeat(db, principal, h_req)

        # Process contact progress
        for p_req in req.contact_progress:
            cls.ingest_contact_progress(db, principal, p_req)

        db.commit()
        return True, None, None

    @classmethod
    def ingest_transfer_progress(
        cls,
        db: DBSession,
        principal: ServicePrincipal,
        req: TransferProgressRequest
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        is_dup, err = cls.check_deduplication(db, principal.id, req.event_id, req.scenario_id, "transfer_progress", req.model_dump())
        if is_dup:
            return True, None, None
        if err:
            return False, err, "Event rejected due to deduplication or scenario conflict"

        t = db.query(DBTransfer).filter(DBTransfer.id == req.transfer_id).first()
        if not t:
            return False, "NOT_FOUND", f"Transfer {req.transfer_id} not found"

        t.forwarded_bytes = req.forwarded_bytes
        if req.ciphertext_sha256:
            t.ciphertext_sha256 = req.ciphertext_sha256
        t.status = "forwarding"

        app_state = SnapshotService.get_app_state(db)
        app_state.state_revision += 1
        db.commit()
        return True, None, None

    @classmethod
    def ingest_delivery_receipt(
        cls,
        db: DBSession,
        principal: ServicePrincipal,
        req: DeliveryReceiptRequest
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        if principal.category != "owner_receiver":
            return False, "FORBIDDEN", "Only authorized owner receiver can submit delivery receipts"

        is_dup, err = cls.check_deduplication(db, principal.id, req.event_id, req.scenario_id, "delivery_receipt", req.model_dump())
        if is_dup:
            return True, None, None
        if err:
            return False, err, "Event rejected due to deduplication or scenario conflict"

        t = db.query(DBTransfer).filter(DBTransfer.id == req.transfer_id).first()
        if not t:
            return False, "NOT_FOUND", f"Transfer {req.transfer_id} not found"

        t.owner_plaintext_sha256 = req.owner_plaintext_sha256
        t.integrity_status = req.integrity_status
        t.owner_decryption_status = req.owner_decryption_status

        if req.integrity_status == "verified" and req.owner_decryption_status == "succeeded":
            t.status = "delivered"
        else:
            t.status = "verification_failed"

        app_state = SnapshotService.get_app_state(db)
        app_state.state_revision += 1
        db.commit()
        return True, None, None
