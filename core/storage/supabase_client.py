from supabase import Client, create_client

from config import settings


def get_supabase() -> Client:
    """Construct a fresh Supabase client.

    We intentionally do NOT cache the result with @lru_cache: Supabase's
    edge load balancer drops idle TCP connections after ~60-90 s, and a
    cached singleton's httpx pool keeps reusing those dead sockets. The
    next query then dies with `httpx.RemoteProtocolError: Server
    disconnected` and FastAPI returns 500 — which is exactly what the
    /admin/metrics screen on the Mini App was hitting on every second
    visit. Creating a fresh client per `SupabaseStorage(...)` instance
    (i.e. per request, since services build the adapter on demand) is
    cheap (no network I/O at construction) and keeps the pool fresh.

    If you need a long-lived client somewhere, build it once at startup
    and inject it explicitly via SupabaseStorage(client=...).
    """
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
