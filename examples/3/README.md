# Data Pipeline CLI

A lightweight ETL data pipeline with CSV/JSON processing, managed by marksync agents.

## Dependencies

```text markpact:deps python
click>=8.1
rich>=13.0
pydantic>=2.0
```

## Data Models

```python markpact:file path=pipeline/models.py
from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime


class Record(BaseModel):
    """A single data record flowing through the pipeline."""
    id: Optional[int] = None
    source: str = ""
    data: dict[str, Any] = {}
    processed: bool = False
    errors: list[str] = []
    timestamp: Optional[datetime] = None


class PipelineResult(BaseModel):
    """Summary of a pipeline run."""
    input_count: int = 0
    output_count: int = 0
    error_count: int = 0
    duration_ms: float = 0.0
    stages: list[str] = []
```

## Pipeline Engine

```python markpact:file path=pipeline/engine.py
import csv
import json
import time
from io import StringIO
from pathlib import Path
from typing import Any, Callable

from pipeline.models import Record, PipelineResult


class PipelineEngine:
    """Simple ETL pipeline: read → transform → write."""

    def __init__(self):
        self.stages: list[tuple[str, Callable]] = []

    def add_stage(self, name: str, fn: Callable):
        self.stages.append((name, fn))
        return self

    def run(self, records: list[Record]) -> PipelineResult:
        t0 = time.time()
        current = list(records)
        stage_names = []

        for name, fn in self.stages:
            stage_names.append(name)
            next_batch = []
            for rec in current:
                try:
                    result = fn(rec)
                    if result is not None:
                        next_batch.append(result)
                except Exception as e:
                    rec.errors.append(f"{name}: {e}")
                    next_batch.append(rec)
            current = next_batch

        return PipelineResult(
            input_count=len(records),
            output_count=len([r for r in current if r.processed and not r.errors]),
            error_count=len([r for r in current if r.errors]),
            duration_ms=(time.time() - t0) * 1000,
            stages=stage_names,
        )


# ── Built-in stages ──────────────────────────────────────────────────────

def read_csv(path: str) -> list[Record]:
    """Read CSV file into Records."""
    text = Path(path).read_text("utf-8")
    reader = csv.DictReader(StringIO(text))
    records = []
    for i, row in enumerate(reader):
        records.append(Record(id=i, source=path, data=dict(row)))
    return records


def read_json(path: str) -> list[Record]:
    """Read JSON array file into Records."""
    items = json.loads(Path(path).read_text("utf-8"))
    if not isinstance(items, list):
        items = [items]
    return [Record(id=i, source=path, data=item) for i, item in enumerate(items)]


def write_json(records: list[Record], path: str):
    """Write Records to JSON file."""
    data = [r.data for r in records if r.processed]
    Path(path).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def stage_validate(required_fields: list[str]):
    """Create a validation stage that checks for required fields."""
    def _validate(rec: Record) -> Record:
        missing = [f for f in required_fields if f not in rec.data or not rec.data[f]]
        if missing:
            rec.errors.append(f"Missing fields: {missing}")
        return rec
    return _validate


def stage_transform(field_map: dict[str, str]):
    """Create a transform stage that renames fields."""
    def _transform(rec: Record) -> Record:
        for old_key, new_key in field_map.items():
            if old_key in rec.data:
                rec.data[new_key] = rec.data.pop(old_key)
        rec.processed = True
        return rec
    return _transform


def stage_filter(field: str, value: Any):
    """Create a filter stage — keep only records matching field==value."""
    def _filter(rec: Record) -> Record | None:
        if rec.data.get(field) == value:
            return rec
        return None
    return _filter
```

## CLI Interface

```python markpact:file path=pipeline/cli.py
import json
import click
from rich.console import Console
from rich.table import Table

from pipeline.engine import (
    PipelineEngine, read_csv, read_json, write_json,
    stage_validate, stage_transform,
)

console = Console()


@click.group()
def main():
    """Data Pipeline CLI — ETL for CSV/JSON data."""
    pass


@main.command()
@click.argument("input_file")
@click.option("--output", "-o", default="output.json", help="Output JSON file")
@click.option("--validate", "-v", multiple=True, help="Required field names")
@click.option("--rename", "-r", multiple=True, help="Rename field: old=new")
def run(input_file, output, validate, rename):
    """Run the pipeline on an input file."""
    # Read
    if input_file.endswith(".csv"):
        records = read_csv(input_file)
    elif input_file.endswith(".json"):
        records = read_json(input_file)
    else:
        console.print(f"[red]Unsupported format:[/] {input_file}")
        return

    console.print(f"[cyan]Read:[/] {len(records)} records from {input_file}")

    # Build pipeline
    engine = PipelineEngine()

    if validate:
        engine.add_stage("validate", stage_validate(list(validate)))

    if rename:
        field_map = {}
        for r in rename:
            old, _, new = r.partition("=")
            if new:
                field_map[old] = new
        if field_map:
            engine.add_stage("transform", stage_transform(field_map))

    # Mark as processed if no transform stage
    if not rename:
        engine.add_stage("passthrough", lambda rec: setattr(rec, "processed", True) or rec)

    # Run
    result = engine.run(records)

    # Write
    processed = [r for r in records if r.processed and not r.errors]
    write_json(processed, output)

    # Report
    table = Table(title="Pipeline Result")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Input records", str(result.input_count))
    table.add_row("Output records", str(result.output_count))
    table.add_row("Errors", str(result.error_count))
    table.add_row("Duration", f"{result.duration_ms:.1f} ms")
    table.add_row("Stages", " → ".join(result.stages))
    table.add_row("Output file", output)
    console.print(table)


@main.command()
@click.argument("input_file")
def inspect(input_file):
    """Show structure of an input file."""
    if input_file.endswith(".csv"):
        records = read_csv(input_file)
    elif input_file.endswith(".json"):
        records = read_json(input_file)
    else:
        console.print(f"[red]Unsupported:[/] {input_file}")
        return

    console.print(f"[cyan]Records:[/] {len(records)}")
    if records:
        console.print(f"[cyan]Fields:[/]  {list(records[0].data.keys())}")
        console.print(f"[cyan]Sample:[/]")
        console.print(json.dumps(records[0].data, indent=2, default=str))


if __name__ == "__main__":
    main()
```

## Sample Data

```text markpact:file path=data/sample.csv
name,email,role,active
Alice,alice@example.com,engineer,true
Bob,bob@example.com,designer,true
Charlie,,manager,false
Diana,diana@example.com,engineer,true
```

## Run Command

```bash markpact:run
python -m pipeline.cli run data/sample.csv -o data/output.json -v name -v email -r role=position
```
