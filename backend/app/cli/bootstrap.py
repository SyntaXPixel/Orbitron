import json
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from sqlalchemy.orm import Session as DBSession

from app.config import settings, BACKEND_DIR
from app.db.session import engine, SessionLocal, Base
from app.db.models import (
    Organization, User, ServicePrincipal, ServiceCredential,
    Satellite, SatelliteOrbit, Station, Antenna, StationPartnerPermission,
    Opportunity, ApplicationState, ScenarioRun
)
from app.services.auth_service import hash_password, hash_token

def bootstrap_database():
    print("Ensuring database schema...")
    Base.metadata.create_all(bind=engine)

    db: DBSession = SessionLocal()
    runtime_dir = BACKEND_DIR / ".runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Organizations
        org_alpha = db.query(Organization).filter(Organization.id == "org-alpha").first()
        if not org_alpha:
            org_alpha = Organization(id="org-alpha", name="Alpha Space Dynamics")
            db.add(org_alpha)

        org_beta = db.query(Organization).filter(Organization.id == "org-beta").first()
        if not org_beta:
            org_beta = Organization(id="org-beta", name="Beta Orbital Communications")
            db.add(org_beta)
        db.commit()

        # 2. Users
        admin_pass = "AdminPassword123!"
        alpha_pass = "AlphaOperator123!"
        beta_pass = "BetaOperator123!"

        admin_user = db.query(User).filter(User.email == "admin@orbitron.local").first()
        if not admin_user:
            admin_user = User(
                id="user-admin",
                display_name="Network Administrator",
                email="admin@orbitron.local",
                organization_id="org-alpha",
                role="network_admin",
                password_hash=hash_password(admin_pass)
            )
            db.add(admin_user)

        op_alpha = db.query(User).filter(User.email == "operator@alpha.local").first()
        if not op_alpha:
            op_alpha = User(
                id="user-op-alpha",
                display_name="Alpha Mission Lead",
                email="operator@alpha.local",
                organization_id="org-alpha",
                role="operator",
                password_hash=hash_password(alpha_pass)
            )
            db.add(op_alpha)

        op_beta = db.query(User).filter(User.email == "operator@beta.local").first()
        if not op_beta:
            op_beta = User(
                id="user-op-beta",
                display_name="Beta Flight Controller",
                email="operator@beta.local",
                organization_id="org-beta",
                role="operator",
                password_hash=hash_password(beta_pass)
            )
            db.add(op_beta)
        db.commit()

        # 3. Service Principals & Credentials
        credentials_export = {}
        principals_def = [
            ("sim-controller", "Simulator Fleet Controller", "simulator_controller", None, {"all": True}),
            ("station-gw-alpha", "Svalbard Station Gateway", "station_gateway", "org-alpha", {"station_ids": ["gs-a-001"]}),
            ("station-gw-beta", "Perth Station Gateway", "station_gateway", "org-beta", {"station_ids": ["gs-b-001"]}),
            ("owner-receiver-alpha", "Alpha Owner Decryption Receiver", "owner_receiver", "org-alpha", {"organization_ids": ["org-alpha"]})
        ]

        for p_id, p_name, p_cat, p_org, p_res in principals_def:
            sp = db.query(ServicePrincipal).filter(ServicePrincipal.id == p_id).first()
            if not sp:
                sp = ServicePrincipal(
                    id=p_id,
                    name=p_name,
                    category=p_cat,
                    organization_id=p_org,
                    permitted_resources_json=p_res
                )
                db.add(sp)
                db.commit()

            cred = db.query(ServiceCredential).filter(ServiceCredential.principal_id == p_id).first()
            raw_token = f"orb_sec_{secrets.token_urlsafe(32)}"
            if not cred:
                cred = ServiceCredential(
                    id=f"cred-{p_id}",
                    principal_id=p_id,
                    token_hash=hash_token(raw_token),
                    scope="all" if p_cat == "simulator_controller" else f"category:{p_cat}",
                    expires_at=None,
                    revoked=False
                )
                db.add(cred)
                db.commit()
                credentials_export[p_id] = {
                    "principal_id": p_id,
                    "category": p_cat,
                    "bearer_token": raw_token
                }
            else:
                credentials_export[p_id] = {
                    "principal_id": p_id,
                    "category": p_cat,
                    "bearer_token": "[Existing credential retained]"
                }

        # Save credentials to ignored local runtime file
        cred_file = runtime_dir / "service_credentials.json"
        with open(cred_file, "w", encoding="utf-8") as f:
            json.dump(credentials_export, f, indent=2)

        # 4. Scenario Definition
        scenario_id = "scenario-001"
        base_start = datetime(2026, 10, 31, 6, 0, 0, tzinfo=timezone.utc)
        base_end = base_start + timedelta(hours=24)

        sc_run = db.query(ScenarioRun).filter(ScenarioRun.id == scenario_id).first()
        if not sc_run:
            sc_run = ScenarioRun(
                id=scenario_id,
                name="Orbitron Standard Scenario (Seed 42)",
                seed=42,
                start_at=base_start,
                end_at=base_end,
                ready_for_evaluation=True,
                is_active=True
            )
            db.add(sc_run)
            db.commit()

        # 5. Application State
        app_state = db.query(ApplicationState).filter(ApplicationState.id == 1).first()
        if not app_state:
            app_state = ApplicationState(
                id=1,
                contract_version="orbitron.v1",
                mode="simulation",
                state_revision=1,
                schedule_version=0,
                planning_revision=0,
                simulation_time=base_start,
                simulation_run_state="paused",
                simulation_speed_multiplier=1.0,
                current_scenario_id=scenario_id
            )
            db.add(app_state)
            db.commit()

        # 6. Satellites
        sats_def = [
            ("sat-a-001", "Alpha-Sat-1", "org-alpha", ["X", "S"], 150_000_000, 1, 8_000_000_000, 78.2, 15.4, 520.0),
            ("sat-a-002", "Alpha-Sat-2", "org-alpha", ["Ka", "X"], 300_000_000, 2, 15_000_000_000, -12.4, 45.1, 550.0),
            ("sat-b-001", "Beta-Sat-1", "org-beta", ["X", "S"], 120_000_000, 1, 6_000_000_000, 35.6, 139.7, 510.0),
        ]

        for s_id, s_name, s_org, s_bands, s_rate, s_par, s_bytes, lat, lon, alt in sats_def:
            s_obj = db.query(Satellite).filter(Satellite.id == s_id).first()
            if not s_obj:
                s_obj = Satellite(
                    id=s_id,
                    name=s_name,
                    owner_org_id=s_org,
                    supported_bands_json=s_bands,
                    max_downlink_rate_bps=s_rate,
                    max_parallel_contacts=s_par,
                    onboard_bytes=s_bytes,
                    reserved_bytes=0,
                    operational_status="available",
                    telemetry_status="fresh",
                    position_lat=lat,
                    position_lon=lon,
                    position_alt=alt,
                    position_observed_at=base_start,
                    last_telemetry_at=base_start,
                    source="simulated",
                    orbit_source="synthetic",
                    orbit_epoch_at=base_start
                )
                db.add(s_obj)

                # Orbit TLE
                db.add(SatelliteOrbit(
                    id=f"orbit-{s_id}",
                    satellite_id=s_id,
                    format="tle",
                    line1=f"1 99999U 26001A   26304.25000000  .00001000  00000-0  10000-4 0  9999",
                    line2=f"2 99999  97.5000  25.0000 0010000  60.0000 300.0000 15.20000000    10",
                    epoch_at=base_start,
                    orbit_source="synthetic"
                ))
        db.commit()

        # 7. Ground Stations & Antennas
        st_def = [
            ("gs-a-001", "Svalbard Ground Station", "org-alpha", 78.23, 15.40, 5.0, True, ["org-beta"], [
                ("ant-a-001", "Polar-Dish-1", ["X", "S"], 150_000_000, 60)
            ]),
            ("gs-b-001", "Perth Ground Station", "org-beta", -31.95, 115.86, 5.0, True, ["org-alpha"], [
                ("ant-b-001", "Perth-Dish-1", ["Ka", "X", "S"], 300_000_000, 90)
            ])
        ]

        for st_id, st_name, st_org, lat, lon, elev, sharing, partners, antennas in st_def:
            st_obj = db.query(Station).filter(Station.id == st_id).first()
            if not st_obj:
                st_obj = Station(
                    id=st_id,
                    name=st_name,
                    owner_org_id=st_org,
                    latitude_deg=lat,
                    longitude_deg=lon,
                    min_elevation_deg=elev,
                    operational_status="online",
                    connection_status="connected",
                    weather_capacity_factor=1.0,
                    sharing_enabled=sharing,
                    last_heartbeat_at=datetime.now(timezone.utc)
                )
                db.add(st_obj)
                db.commit()

                for p_org in partners:
                    db.add(StationPartnerPermission(
                        id=f"part-{st_id}-{p_org}",
                        station_id=st_id,
                        partner_org_id=p_org
                    ))

                for a_id, a_name, a_bands, a_rate, a_setup in antennas:
                    db.add(Antenna(
                        id=a_id,
                        station_id=st_id,
                        name=a_name,
                        supported_bands_json=a_bands,
                        max_rate_bps=a_rate,
                        setup_seconds=a_setup,
                        status="available"
                    ))
        db.commit()

        # 8. Communication Opportunities
        opps_def = [
            ("opp-001", "sat-a-001", "gs-a-001", "ant-a-001", "X", base_start + timedelta(minutes=15), base_start + timedelta(minutes=30), 150_000_000),
            ("opp-002", "sat-a-001", "gs-b-001", "ant-b-001", "X", base_start + timedelta(hours=1, minutes=45), base_start + timedelta(hours=2), 150_000_000),
            ("opp-003", "sat-b-001", "gs-a-001", "ant-a-001", "S", base_start + timedelta(minutes=40), base_start + timedelta(minutes=55), 100_000_000),
            ("opp-004", "sat-a-002", "gs-b-001", "ant-b-001", "Ka", base_start + timedelta(hours=2, minutes=10), base_start + timedelta(hours=2, minutes=30), 300_000_000),
        ]

        for o_id, s_id, st_id, a_id, band, st_at, end_at, rate in opps_def:
            opp_obj = db.query(Opportunity).filter(Opportunity.id == o_id).first()
            if not opp_obj:
                db.add(Opportunity(
                    id=o_id,
                    scenario_id=scenario_id,
                    satellite_id=s_id,
                    station_id=st_id,
                    antenna_id=a_id,
                    band=band,
                    start_at=st_at,
                    end_at=end_at,
                    predicted_rate_bps=rate
                ))
        db.commit()

        print("Bootstrap completed successfully!")
        print(f"Admin User: admin@orbitron.local (Password: {admin_pass})")
        print(f"Alpha Operator: operator@alpha.local (Password: {alpha_pass})")
        print(f"Beta Operator: operator@beta.local (Password: {beta_pass})")
        print(f"Service credentials exported to: {cred_file}")

    finally:
        db.close()

if __name__ == "__main__":
    bootstrap_database()
