"""The single guardrail. Any step may raise it; the runner turns it into the spec's JSON."""


class GuardrailExit(Exception):
    """Stops the pipeline with {"status": "no_amounts_found", "reason": <reason>}."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason
