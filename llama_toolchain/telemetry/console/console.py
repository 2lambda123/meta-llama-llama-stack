# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.

from typing import Optional

from llama_toolchain.telemetry.api import *  # noqa: F403
from .config import ConsoleConfig


class ConsoleTelemetryImpl(Telemetry):
    def __init__(self, config: ConsoleConfig) -> None:
        self.config = config
        self.spans = {}

    async def initialize(self) -> None: ...

    async def shutdown(self) -> None: ...

    async def log_event(self, event: Event):
        if isinstance(event, SpanStartEvent):
            self.spans[event.span_id] = event

        names = []
        span_id = event.span_id
        while True:
            span_event = self.spans.get(span_id)
            if not span_event:
                break

            names = [span_event.name] + names
            span_id = span_event.parent_span_id

        span_name = ".".join(names) if names else None

        formatted = format_event(event, span_name)
        if formatted:
            print(formatted)

    async def get_trace(self, trace_id: str) -> Trace:
        raise NotImplementedError()


COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
}

SEVERITY_COLORS = {
    LogSeverity.VERBOSE: COLORS["dim"] + COLORS["white"],
    LogSeverity.DEBUG: COLORS["cyan"],
    LogSeverity.INFO: COLORS["green"],
    LogSeverity.WARN: COLORS["yellow"],
    LogSeverity.ERROR: COLORS["red"],
    LogSeverity.CRITICAL: COLORS["bold"] + COLORS["red"],
}


def format_event(event: Event, span_name: str) -> Optional[str]:
    timestamp = event.timestamp.strftime("%H:%M:%S.%f")[:-3]
    span = ""
    if span_name:
        span = f"{COLORS['magenta']}[{span_name}]{COLORS['reset']} "
    if isinstance(event, LoggingEvent):
        severity_color = SEVERITY_COLORS.get(event.severity, COLORS["reset"])
        return (
            f"{COLORS['dim']}{timestamp}{COLORS['reset']} "
            f"{severity_color}[{event.severity.name}]{COLORS['reset']} "
            f"{span}"
            f"{event.message}"
        )

    elif isinstance(event, SpanStartEvent):
        return None

    #     return (f"{COLORS['dim']}{timestamp}{COLORS['reset']} "
    #             f"{COLORS['blue']}[SPAN_START]{COLORS['reset']} "
    #             f"{span}"
    #             f"{COLORS['bold']}{event.name}{COLORS['reset']}")

    elif isinstance(event, SpanEndEvent):
        return None

    #     status_color = COLORS['green'] if event.status == SpanStatus.OK else COLORS['red']
    #     return (f"{COLORS['dim']}{timestamp}{COLORS['reset']} "
    #             f"{COLORS['blue']}[SPAN_END]{COLORS['reset']} "
    #             f"{span}"
    #             f"{status_color}{event.status.value}{COLORS['reset']}")

    return f"Unknown event type: {event}"
