"""Permitato app lifecycle hooks — called by platform during startup/shutdown."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from apps.permitato.state import initialize_permitato, shutdown_permitato

logger = logging.getLogger(__name__)


async def on_startup(app, app_dir: Path, data_dir: Path) -> None:
    """Initialize Permitato: connect to Pi-hole, start expiry loop."""
    app.state.permit_state = None
    app.state.permit_expiry_task = None

    pw_path = app.state.runtime.base_dir / "config" / "permitato_pihole_password"
    if not pw_path.exists():
        logger.info("Pi-hole password not found at %s — skipping Permitato init", pw_path)
        return

    pihole_pw = pw_path.read_text(encoding="utf-8").strip()
    permit_data_dir = data_dir / "permitato"
    app.state.permit_state = await initialize_permitato(
        data_dir=permit_data_dir,
        pihole_password=pihole_pw,
    )

    app.state.permit_expiry_task = asyncio.create_task(
        _exception_expiry_loop(app),
        name="permitato-expiry",
    )


async def on_shutdown(app) -> None:
    """Shutdown Permitato: cancel expiry, disconnect adapter."""
    expiry_task = getattr(app.state, "permit_expiry_task", None)
    if expiry_task is not None:
        expiry_task.cancel()
        try:
            await expiry_task
        except asyncio.CancelledError:
            pass

    permit_state = getattr(app.state, "permit_state", None)
    if permit_state is not None:
        await shutdown_permitato(permit_state)


async def _exception_expiry_loop(app) -> None:
    """Background task: revoke expired exceptions every 30s."""
    from apps.permitato.audit import write_audit_entry

    while True:
        await asyncio.sleep(30)
        state = getattr(app.state, "permit_state", None)
        if state and state.exception_store:
            for exc in state.exception_store.get_expired():
                if state.adapter and state.pihole_available:
                    try:
                        await state.adapter.delete_domain_rule(
                            exc.regex_pattern, "allow", "regex",
                        )
                    except Exception:
                        pass
                write_audit_entry(state.data_dir, {
                    "event": "exception_expired",
                    "domain": exc.domain,
                    "exception_id": exc.id,
                })
            revoked = state.exception_store.cleanup_expired()
            if revoked:
                state.exception_store.persist()
