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
    Only a volume-name clash stopped it.

    Still relevant now that the database is an external provider rather than
    a Fly app: this guards Fly's tooling rewriting `app`, not the Postgres
    product. Any Fly app whose name looks like a database is the wrong
    deploy target, and there is no longer even a database app to point at.
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

    # getattr, because app.routes now also holds an included-router object with
    # no .path of its own. The healthchecks all point at top-level ops routes,
    # so there is no need to descend into it.
    paths = {getattr(route, "path", None) for route in service.app.routes}
    for check in fly.get("http_service", {}).get("checks", []):
        assert check["path"] in paths, check["path"]


STORE_PATH_KEYS = ("SESSION_DB_PATH", "METRICS_DB_PATH", "VECTOR_STORE_PATH")

# The three pins that make a mount-less deploy fail closed. Values, not keys --
# `SESSION_BACKEND` present but set to `sqlite` is the exact thing being guarded
# against. Read off the parsed [env] table rather than the file text, because
# `VECTOR_STORE_PATH` contains the string `VECTOR_STORE` and a text search
# cannot tell the two apart.
POSTGRES_BACKEND_PINS = {
    "SESSION_BACKEND": "postgres",
    "METRICS_BACKEND": "postgres",
    "VECTOR_STORE": "pgvector",
}


def test_the_store_paths_match_the_topology(fly):
    """Guards both topologies, because the repo passes through both.

    **With a mount.** If a path drifts outside the mounted volume the app
    still starts, still passes health checks, and silently loses every
    session on restart -- the worst kind of misconfiguration because nothing
    complains.

    **Without a mount** (the stateless topology): two separate things must
    hold, and the second is the one worth reading.

    a. No `*_DB_PATH` key may survive. Left behind after the volume goes they
       address an ephemeral container filesystem.

    b. All three backends must be *pinned* to their Postgres implementations.
       Deleting the paths does **not** on its own prevent a SQLite fallback:
       `sessions.py` defaults `SESSION_DB_PATH` to a file beside the module,
       and `default_backend()` returns `"sqlite"` whenever
       `db.postgres_configured()` is false. So with `DATABASE_URL` unset or
       empty, two mount-less machines would each boot on their own
       container-local SQLite file -- the per-machine split-brain this phase
       exists to end, now with data that also vanishes on restart, and
       invisible to every automated check: `/health` reports
       `dependencies: "ok"` because SQLite is perfectly reachable, Fly's check
       passes, and the only difference on the wire is a backend class name
       that nothing reads. With the pins the same situation fails **closed** --
       `db.database_url()` raises `RuntimeError` at store construction, the
       app does not come up, and the failure is loud.

    This test does not skip. A guard that skips when `[[mounts]]` is deleted
    is a guard that deleting `[[mounts]]` silently disarms.
    """
    env = fly.get("env", {})
    mounts = fly.get("mounts") or []

    if mounts:
        destination = mounts[0]["destination"].rstrip("/")
        for key in STORE_PATH_KEYS:
            if key in env:
                assert env[key].startswith(destination + "/"), (
                    f"{key}={env[key]} is outside the {destination} volume, so "
                    "its data would not survive a restart."
                )
        return

    stray = [key for key in STORE_PATH_KEYS if key in env]
    assert not stray, (
        f"no volume is mounted, but {', '.join(stray)} still points at a local "
        "path -- which is now an ephemeral container filesystem. Remove these "
        "keys when you remove [[mounts]]."
    )

    for key, expected in POSTGRES_BACKEND_PINS.items():
        assert env.get(key) == expected, (
            f"no volume is mounted, so {key} must be pinned to {expected!r} "
            f"(found {env.get(key)!r}). Unpinned, an unset or empty "
            "DATABASE_URL falls back to container-local SQLite/JSON, /health "
            "still reports ok, and each machine serves its own data. Pinned, "
            "store construction raises and the deploy fails loudly."
        )


def test_the_machine_count_matches_the_topology(fly):
    """The two topologies want opposite things, so guard both directions.

    **With a mount:** at most one machine. Two machines with a volume each
    hold two independent databases, and a follow-up routed to the wrong one
    404s on a session that demonstrably exists.

    **Without a mount:** at least two. A stateless single machine is the
    downtime this phase exists to remove -- host maintenance still takes the
    service offline, which is the whole reason for detaching the volume.

    Skipping either arm would let plan 11-05's mount removal pass through
    unguarded.
    """
    running = fly["http_service"].get("min_machines_running", 1)

    if fly.get("mounts") or []:
        assert running <= 1, (
            f"min_machines_running={running} with a volume mounted. Each "
            "machine would hold its own database. Move the stores to Postgres "
            "and remove [[mounts]] before raising this."
        )
    else:
        assert running >= 2, (
            f"min_machines_running={running} with no volume. The stores are "
            "on Postgres and the machine holds no state, so a single machine "
            "is downtime for nothing."
        )


def test_the_database_url_is_not_committed(fly):
    """A DSN carries the password. `fly.toml` is in a public repository, so a
    `DATABASE_URL` in `[env]` is a disclosed credential and rotation is the
    only remedy -- it belongs in `fly secrets set`.

    Asserted against the parsed `[env]` table, not the file text, so the
    comments around it stay free to name the variable.
    """
    assert "DATABASE_URL" not in fly.get("env", {}), (
        "DATABASE_URL is set in fly.toml's [env] block. That file is "
        "committed, so the password is public. Move it: "
        "`fly secrets set DATABASE_URL=... -a research-agent`."
    )


# The critic's model, pinned the same way as the backend pins above: a VALUE
# read off the parsed [env] table. `CRITIC_MODEL` present but set to the
# writer's model is exactly the arrangement ADR-0010 supersedes, so presence
# proves nothing.
CRITIC_MODEL_PIN = "claude-opus-5"


def test_the_critic_model_pin_is_intact(fly):
    """The deployed critic runs on Opus, and `fly.toml` is the only thing
    saying so.

    `graph.critic_model()` reads an absent or blank `CRITIC_MODEL` as `MODEL`
    -- a deliberately neutral default, which is what keeps CI, the suite and
    the keyless evals unaffected by phase 16. The cost of that neutrality is
    that losing this key fails **open**, not closed like the backend pins
    below: the critic quietly reverts to the writer's model, the revision loop
    keeps working, `/health` reports ok, Fly's check passes, and the only trace
    on the wire is a smaller number in the demo's cost line. Nothing else in
    the tree would notice, which is the quiet-misconfiguration class this file
    exists for.

    A key does not have to be deleted on purpose to disappear. Fly's tooling
    has regenerated this file from the web UI's defaults twice (`fly.toml`'s
    header names both incidents), and a regenerated `[env]` carries the
    variables Fly knows about.
    """
    env = fly.get("env", {})
    assert env.get("CRITIC_MODEL") == CRITIC_MODEL_PIN, (
        f"fly.toml's [env] must pin CRITIC_MODEL to {CRITIC_MODEL_PIN!r} "
        f"(found {env.get('CRITIC_MODEL')!r}). Unpinned or reverted, the "
        "deployed critic silently runs on the writer's model again -- the "
        "shared-model arrangement docs/adr/0010-... supersedes -- and every "
        "check in this repository stays green while it happens, because the "
        "code default for an absent CRITIC_MODEL is the writer's model."
    )


def test_the_runbook_names_no_unsupported_command():
    """`fly.toml`'s footer is a runbook, and a runbook is followed under time
    pressure by someone who is not reading critically.

    It documented `fly postgres create` / `fly postgres attach` for two
    phases. Fly now prints that unmanaged Fly Postgres is not supported by
    Fly.io Support and that users own operations, management and disaster
    recovery -- so following the footer meant provisioning an unsupported
    database. The replacement is an external provider reached over a
    `DATABASE_URL` secret.

    Asserted on the file text rather than the parsed table, because a
    comment is exactly what this guards and tomllib discards comments.
    """
    text = FLY_TOML.read_text()
    for command in ("fly postgres create", "fly postgres attach"):
        assert command not in text, (
            f"fly.toml's comments still tell an operator to run `{command}`, "
            "which provisions unmanaged Fly Postgres -- unsupported by Fly. "
            "The database is external; `fly secrets set DATABASE_URL=...` "
            "replaces the attach step."
        )


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
