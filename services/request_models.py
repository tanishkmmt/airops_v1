"""Shared size limits for tabular API payloads sent to the AIS services."""
from typing import Annotated

from pydantic import Field

HeaderCell = Annotated[str, Field(min_length=1, max_length=500)]
DataCell = Annotated[str, Field(max_length=10_000)]
TableHeaders = Annotated[list[HeaderCell], Field(max_length=300)]
TableRow = Annotated[list[DataCell], Field(max_length=300)]
TableRows = Annotated[list[TableRow], Field(max_length=500)]
ProfileValues = Annotated[dict[str, Annotated[str, Field(max_length=4_000)]], Field(max_length=32)]
