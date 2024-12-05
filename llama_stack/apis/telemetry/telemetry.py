# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.

from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Protocol,
    runtime_checkable,
    Union,
)

from llama_models.schema_utils import json_schema_type, webmethod
from pydantic import BaseModel, Field
from typing_extensions import Annotated

from llama_stack.apis.datasetio import DatasetIO

# Add this constant near the top of the file, after the imports
DEFAULT_TTL_DAYS = 7


@json_schema_type
class SpanStatus(Enum):
    OK = "ok"
    ERROR = "error"


@json_schema_type
class Span(BaseModel):
    span_id: str
    trace_id: str
    parent_span_id: Optional[str] = None
    name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    attributes: Optional[Dict[str, Any]] = Field(default_factory=dict)

    def set_attribute(self, key: str, value: Any):
        if self.attributes is None:
            self.attributes = {}
        self.attributes[key] = value


@json_schema_type
class Trace(BaseModel):
    trace_id: str
    root_span_id: str
    start_time: datetime
    end_time: Optional[datetime] = None


@json_schema_type
class EventType(Enum):
    UNSTRUCTURED_LOG = "unstructured_log"
    STRUCTURED_LOG = "structured_log"
    METRIC = "metric"


@json_schema_type
class LogSeverity(Enum):
    VERBOSE = "verbose"
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"


class EventCommon(BaseModel):
    trace_id: str
    span_id: str
    timestamp: datetime
    attributes: Optional[Dict[str, Any]] = Field(default_factory=dict)


@json_schema_type
class UnstructuredLogEvent(EventCommon):
    type: Literal[EventType.UNSTRUCTURED_LOG.value] = EventType.UNSTRUCTURED_LOG.value
    message: str
    severity: LogSeverity


@json_schema_type
class MetricEvent(EventCommon):
    type: Literal[EventType.METRIC.value] = EventType.METRIC.value
    metric: str  # this would be an enum
    value: Union[int, float]
    unit: str


@json_schema_type
class StructuredLogType(Enum):
    SPAN_START = "span_start"
    SPAN_END = "span_end"


@json_schema_type
class SpanStartPayload(BaseModel):
    type: Literal[StructuredLogType.SPAN_START.value] = (
        StructuredLogType.SPAN_START.value
    )
    name: str
    parent_span_id: Optional[str] = None


@json_schema_type
class SpanEndPayload(BaseModel):
    type: Literal[StructuredLogType.SPAN_END.value] = StructuredLogType.SPAN_END.value
    status: SpanStatus


StructuredLogPayload = Annotated[
    Union[
        SpanStartPayload,
        SpanEndPayload,
    ],
    Field(discriminator="type"),
]


@json_schema_type
class StructuredLogEvent(EventCommon):
    type: Literal[EventType.STRUCTURED_LOG.value] = EventType.STRUCTURED_LOG.value
    payload: StructuredLogPayload


Event = Annotated[
    Union[
        UnstructuredLogEvent,
        MetricEvent,
        StructuredLogEvent,
    ],
    Field(discriminator="type"),
]


@json_schema_type
class EvalTrace(BaseModel):
    session_id: str
    step: str
    input: str
    output: str
    expected_output: str


@json_schema_type
class SpanWithChildren(Span):
    children: List["SpanWithChildren"] = Field(default_factory=list)
    status: Optional[SpanStatus] = None


@json_schema_type
class QueryCondition(BaseModel):
    key: str
    op: Literal["eq", "ne", "gt", "lt"]
    value: Any


@runtime_checkable
class Telemetry(Protocol):

    # Each provider must initialize this dependency.
    datasetio_api: DatasetIO

    @webmethod(route="/telemetry/log-event")
    async def log_event(
        self, event: Event, ttl_seconds: int = DEFAULT_TTL_DAYS * 86400
    ) -> None: ...

    @webmethod(route="/telemetry/query-traces", method="POST")
    async def query_traces(
        self,
        attribute_filters: Optional[List[QueryCondition]] = None,
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
        order_by: Optional[List[str]] = None,
    ) -> List[Trace]: ...

    @webmethod(route="/telemetry/get-span-tree", method="POST")
    async def get_span_tree(
        self,
        span_id: str,
        attributes_to_return: Optional[List[str]] = None,
        max_depth: Optional[int] = None,
    ) -> SpanWithChildren: ...

    @webmethod(route="/telemetry/query-spans", method="POST")
    async def query_spans(
        self,
        attribute_filters: List[QueryCondition],
        attributes_to_return: List[str],
        max_depth: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        traces = await self.query_traces(attribute_filters=attribute_filters)

        rows = []

        for trace in traces:
            span_tree = await self.get_span_tree(
                span_id=trace.root_span_id,
                attributes_to_return=attributes_to_return,
                max_depth=max_depth,
            )

            def extract_spans(span: SpanWithChildren) -> List[Dict[str, Any]]:
                rows = []
                if span.attributes and all(
                    attr in span.attributes and span.attributes[attr] is not None
                    for attr in attributes_to_return
                ):
                    row = {
                        "trace_id": trace.root_span_id,
                        "span_id": span.span_id,
                        "step_name": span.name,
                    }
                    for attr in attributes_to_return:
                        row[attr] = str(span.attributes[attr])
                    rows.append(row)

                for child in span.children:
                    rows.extend(extract_spans(child))

                return rows

            rows.extend(extract_spans(span_tree))

        return rows

    @webmethod(route="/telemetry/save-spans-to-dataset", method="POST")
    async def save_spans_to_dataset(
        self,
        attribute_filters: List[QueryCondition],
        attributes_to_save: List[str],
        dataset_id: str,
        max_depth: Optional[int] = None,
    ) -> None:
        annotation_rows = await self.query_spans(
            attribute_filters=attribute_filters,
            attributes_to_return=attributes_to_save,
            max_depth=max_depth,
        )

        if annotation_rows:
            await self.datasetio_api.append_rows(
                dataset_id=dataset_id, rows=annotation_rows
            )
