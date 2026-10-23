"""Per-request extraction of Tuskr credentials from HTTP headers."""

import logging
import warnings

from fastmcp.server.middleware import Middleware, MiddlewareContext

logger = logging.getLogger(__name__)


class UserTokenHandler(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """
        Executed on every tool call.
        We intercept it with goal to get secure token
        if it is in the header
        """
        logger.info(f"Raw middleware processing: {context.method}")

        await self.retrieve_and_apply_token(context)

        result = await call_next(context)
        logger.info(f"Raw middleware completed: {context.method}")
        return result

    async def retrieve_and_apply_token(self, context: MiddlewareContext):
        """
        In stdio mode there is no HTTP request/headers, so fall back to None
        and let the tool functions fall back to env vars instead.

        Context state access is async from fastmcp 3.0 on. A set_state call
        that is not awaited never runs, which silently drops the caller's
        headers and falls back to the server's env credentials.
        """
        try:
            request = context.fastmcp_context.request_context.request
            headers = request.headers
        # Broad by design: fastmcp raises different errors depending on which
        # part of the request context is missing in stdio mode.
        except Exception:  # noqa: BLE001
            logger.info(
                "No HTTP request context (stdio mode), skipping header extraction"
            )
            await context.fastmcp_context.set_state("ext_access_token", None)
            await context.fastmcp_context.set_state("ext_tenant_id", None)
            return

        # Read access token
        auth_header = headers.get("Authorization")
        token = None

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            if not token:
                raise ValueError(
                    "Unauthorized: Empty Bearer token",
                )
            # Never log the token itself: INFO logs end up in shared log stores.
            logger.info("Got Bearer token from the Authorization header")

        await context.fastmcp_context.set_state("ext_access_token", token)

        # Try to retrieve tenant id from headers; prefer the new Tenant-ID header
        # and fall back to the legacy Account-ID header with a deprecation warning.
        # Tenant id is optional — it can be set via TUSKR_TENANT_ID env var instead.
        tenant_id = None
        tenant_header = headers.get("Tenant-ID")
        if tenant_header:
            tenant_id = tenant_header.strip()
            logger.info(f"Got tenant id: {tenant_id}")
        else:
            legacy_header = headers.get("Account-ID")
            if legacy_header:
                warnings.warn(
                    "The 'Account-ID' HTTP header is deprecated; "
                    "use 'Tenant-ID' instead.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                tenant_id = legacy_header.strip()
                logger.info(
                    f"Got tenant id (via deprecated Account-ID header): {tenant_id}"
                )
            else:
                logger.info("Tenant id is not defined")

        await context.fastmcp_context.set_state("ext_tenant_id", tenant_id)
