"""Replay integrity errors."""


class ReplayIntegrityError(Exception):
    """Frozen replay could not reproduce persisted runtime history."""


class ReplayVersionMismatchError(ReplayIntegrityError):
    """Bundle orchestrator version does not match the active executor version."""
