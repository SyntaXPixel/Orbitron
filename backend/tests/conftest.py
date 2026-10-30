import tempfile
import os
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
import httpx

from app.main import app
from app.db.session import Base, get_db
from app.db.models import (
    Organization, User, ServicePrincipal, ServiceCredential,
    Satellite, SatelliteOrbit, Station, Antenna, StationPartnerPermission,
    Opportunity, ApplicationState, ScenarioRun
)
from app.services.auth_service import hash_password, hash_token

TEST_ADMIN_PASSWORD = "AdminPassword123!"
TEST_ALPHA_PASSWORD = "AlphaOperator123!"
TEST_BETA_PASSWORD = "BetaOperator123!"

TEST_CONTROLLER_TOKEN = "test_controller_bearer_token"
TEST_GATEWAY_TOKEN = "test_gateway_bearer_token"
TEST_OWNER_TOKEN = "test_owner_bearer_token"

@pytest.fixture(scope="session")
def test_db_path():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_orbitron.db")
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)

@pytest.fixture(scope="session")
def test_engine(test_db_path):
    engine = create_engine(
        f"sqlite:///{test_db_path}",
        connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="session")
def TestingSessionLocal(test_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)

@pytest.fixture(autouse=True)
def setup_test_db(TestingSessionLocal):
    db = TestingSessionLocal()
    # Clean tables
    Base.metadata.drop_all(bind=db.get_bind())
    Base.metadata.create_all(bind=db.get_bind())

    # Seed basic records
    org_alpha = Organization(id="org-alpha", name="Alpha Space Dynamics")
    org_beta = Organization(id="org-beta", name="Beta Orbital Communications")
    db.add_all([org_alpha, org_beta])
    db.commit()

    admin_user = User(
        id="user-admin",
        display_name="Network Administrator",
        email="admin@orbitron.local",
        organization_id="org-alpha",
        role="network_admin",
        password_hash=hash_password(TEST_ADMIN_PASSWORD)
    )
    op_alpha = User(
        id="user-op-alpha",
        display_name="Alpha Operator",
        email="operator@alpha.local",
        organization_id="org-alpha",
        role="operator",
        password_hash=hash_password(TEST_ALPHA_PASSWORD)
    )
    op_beta = User(
        id="user-op-beta",
        display_name="Beta Operator",
        email="operator@beta.local",
        organization_id="org-beta",
        role="operator",
        password_hash=hash_password(TEST_BETA_PASSWORD)
    )
    db.add_all([admin_user, op_alpha, op_beta])

    # Service Principals & Credentials
    sp_ctrl = ServicePrincipal(id="sim-controller", name="Simulator Controller", category="simulator_controller", permitted_resources_json={"all": True})
    sp_gw = ServicePrincipal(id="station-gw-alpha", name="Svalbard Gateway", category="station_gateway", organization_id="org-alpha", permitted_resources_json={"station_ids": ["gs-a-001"]})
    sp_owner = ServicePrincipal(id="owner-receiver-alpha", name="Owner Receiver", category="owner_receiver", organization_id="org-alpha", permitted_resources_json={"organization_ids": ["org-alpha"]})
    db.add_all([sp_ctrl, sp_gw, sp_owner])
    db.commit()

    c_ctrl = ServiceCredential(id="cred-ctrl", principal_id="sim-controller", token_hash=hash_token(TEST_CONTROLLER_TOKEN), scope="all")
    c_gw = ServiceCredential(id="cred-gw", principal_id="station-gw-alpha", token_hash=hash_token(TEST_GATEWAY_TOKEN), scope="station")
    c_owner = ServiceCredential(id="cred-owner", principal_id="owner-receiver-alpha", token_hash=hash_token(TEST_OWNER_TOKEN), scope="owner")
    db.add_all([c_ctrl, c_gw, c_owner])

    # Base Time
    base_start = datetime(2026, 10, 31, 6, 0, 0, tzinfo=timezone.utc)
    base_end = base_start + timedelta(hours=24)

    sc_run = ScenarioRun(
        id="scenario-001",
        name="Test Scenario",
        seed=42,
        start_at=base_start,
        end_at=base_end,
        ready_for_evaluation=True,
        is_active=True
    )
    db.add(sc_run)
    db.commit()

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
        current_scenario_id="scenario-001"
    )
    db.add(app_state)
    db.commit()

    sat = Satellite(
        id="sat-a-001",
        name="Alpha-Sat-1",
        owner_org_id="org-alpha",
        supported_bands_json=["X", "S"],
        max_downlink_rate_bps=150_000_000,
        max_parallel_contacts=1,
        onboard_bytes=10_000_000_000,
        reserved_bytes=0,
        operational_status="available",
        telemetry_status="fresh",
        position_lat=78.2,
        position_lon=15.4,
        position_alt=520.0,
        position_observed_at=base_start,
        last_telemetry_at=base_start,
        source="simulated",
        orbit_source="synthetic",
        orbit_epoch_at=base_start
    )
    db.add(sat)

    st = Station(
        id="gs-a-001",
        name="Svalbard Station",
        owner_org_id="org-alpha",
        latitude_deg=78.23,
        longitude_deg=15.40,
        min_elevation_deg=5.0,
        operational_status="online",
        connection_status="connected",
        weather_capacity_factor=1.0,
        sharing_enabled=True,
        last_heartbeat_at=datetime.now(timezone.utc)
    )
    db.add(st)
    db.commit()

    db.add(StationPartnerPermission(id="part-1", station_id="gs-a-001", partner_org_id="org-beta"))
    db.add(Antenna(
        id="ant-a-001",
        station_id="gs-a-001",
        name="Dish-1",
        supported_bands_json=["X", "S"],
        max_rate_bps=150_000_000,
        setup_seconds=60,
        status="available"
    ))

    db.add(Opportunity(
        id="opp-001",
        scenario_id="scenario-001",
        satellite_id="sat-a-001",
        station_id="gs-a-001",
        antenna_id="ant-a-001",
        band="X",
        start_at=base_start + timedelta(minutes=15),
        end_at=base_start + timedelta(minutes=30),
        predicted_rate_bps=150_000_000
    ))
    db.commit()
    db.close()

from starlette.testclient import TestClient
from app.workers.operations_worker import worker

@pytest.fixture
def client(TestingSessionLocal):
    worker.session_factory = TestingSessionLocal
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, base_url="http://localhost:8000") as c:
        yield c
    app.dependency_overrides.clear()

def login_user(client: httpx.Client, email: str, password: str) -> dict:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "http://localhost:5173"}
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()
