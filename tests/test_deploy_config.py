"""
Checks on the deploy config itself.

These exist because of two near-misses, not out of tidiness. Deploy config is
edited by tooling as well as by people -- `fly launch` and Fly's GitHub
integration both rewrite fly.toml -- and a wrong value here fails in
production, hours after the change, with an error that doesn't obviously point
back at the file.
"""

import re
from pathlib import Path

import pytest
import tomllib

ROOT = Path(__file__).resolve().parent.parent
FLY_TOML = ROOT / "fly.toml"
DOCKERFILE = ROOT / "Dockerfile"


@pytest.fixture(scope="module")
def fly() -> dict:
    if not FLY_TOML.exists():
        pytest.skip("no fly.toml")
    return tomllib.loads(FLY_TOML.read_text())


@pytest.fixture(scope="module")
def dockerfile() -> str:
    return DOCKERFILE.read_text()


def test_fly_config_parses(fly):
    assert fly["app"]


def test_fly_config_does_not_target_a_database_app(fly):
    """The one that actually bit.

    Fly's GitHub integration rewrote `app` to the Postgres app's name, so
    `fly deploy` tried to push the agent image onto the database cluster.
    Only a volume-name clash stopped it. `fly postgres create` makes a
    separate Fly-managed app you *attach* to; it is never a deploy target.
    """
    app = fly["app"]
    assert not app.endswith("-db"), (
        f"fly.toml targets {app!r}, which looks like the Postgres app. "
        "Deploying the agent image there would overwrite the database. "
        "Point `app` back at the agent app."
    )
    assert "postgres" not in app.lower()


def test_the_service_port_matches_the_container(fly, dockerfile):
    """A mismatch here deploys cleanly and then fails every health check,
    which reads as 'the app is broken' rather than 'the port is wrong'."""
    declared = fly["http_service"]["internal_port"]
    exposed = int(re.search(r"^EXPOSE\s+(\d+)", dockerfile, re.M).group(1))
    cmd_port = int(re.search(r'"--port",\s*"(\d+)"', dockerfile).group(1))

    assert declared == exposed == cmd_port


def test_the_healthcheck_path_is_served(fly):
    from research_agent import service

    paths = {route.path for route in service.app.routes}
    for check in fly.get("http_service", {}).get("checks", []):
        assert check["path"] in paths, check["path"]


def test_local_store_paths_live_under_the_mount(fly):
    """If a path drifts outside the mounted volume the app still starts, still
    passes health checks, and silently loses every session on restart -- the
    worst kind of misconfiguration because nothing complains."""
    mounts = fly.get("mounts") or []
    if not mounts:
        pytest.skip("no volume mounted; stores are presumably on Postgres")

    destination = mounts[0]["destination"].rstrip("/")
    env = fly.get("env", {})
    for key in ("SESSION_DB_PATH", "METRICS_DB_PATH", "VECTOR_STORE_PATH"):
        if key in env:
            assert env[key].startswith(destination + "/"), (
                f"{key}={env[key]} is outside the {destination} volume, so its "
                "data would not survive a restart."
            )


def test_a_volume_means_a_single_machine(fly):
    """Two machines with a volume each hold two independent databases, and a
    follow-up routed to the wrong one 404s on a session that exists. Raising
    this is safe only once the stores are on Postgres, at which point the
    mount should be gone."""
    if not (fly.get("mounts") or []):
        pytest.skip("no volume; the app is stateless and can scale out")

    assert fly["http_service"].get("min_machines_running", 1) <= 1


def test_the_image_runs_as_a_non_root_user(dockerfile):
    assert re.search(r"^USER\s+(?!root)", dockerfile, re.M)


def test_secrets_are_excluded_from_the_build_context():
    """A key baked into an image layer is extractable by anyone who can pull
    the image, and rotating it is the only remedy."""
    ignored = (ROOT / ".dockerignore").read_text().splitlines()
    assert ".env" in [line.strip() for line in ignored]


def test_the_demo_page_is_packaged_into_the_image():
    """The page is served from disk at runtime, and it is not a .py file, so
    nothing carries it into the wheel unless package-data says so. Without
    this the deployed root URL 500s on a missing file -- while every test
    passes, because they read it from the source tree."""
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert "[tool.setuptools.package-data]" in pyproject
    assert "static/*.html" in pyproject


def test_the_demo_page_exists_where_the_service_looks_for_it():
    from research_agent import service

    assert Path(service.DEMO_PAGE).is_file()
