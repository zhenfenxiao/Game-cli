"""Agent trace collection — records the entire game generation pipeline.

Traces are persisted to SQLite (.opengame/traces/traces.db) for later
analysis, debugging, and optimization.
"""

from opengame.tracing.tracer import TraceSession, Tracer
from opengame.tracing.store import TraceStore

__all__ = ["TraceSession", "Tracer", "TraceStore"]
