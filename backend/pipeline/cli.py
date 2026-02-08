"""CLI interface for the AI News Platform pipeline.

Usage:
    python -m backend.pipeline.cli ingest --all
    python -m backend.pipeline.cli ingest --source openai_news
    python -m backend.pipeline.cli status
    python -m backend.pipeline.cli search "RAG agents"
    python -m backend.pipeline.cli vacuum
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from backend.pipeline.orchestrator import IngestOrchestrator
from backend.storage.db import DatabaseManager

console = Console()

DEFAULT_DB_PATH = "data/ainews.db"
DEFAULT_CONFIG_PATH = "config.yaml"


def run_async(coro):
    """Run an async function in the event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


@click.group()
@click.option("--db", default=DEFAULT_DB_PATH, help="Database path")
@click.option("--config", default=DEFAULT_CONFIG_PATH, help="Config file path")
@click.pass_context
def cli(ctx, db: str, config: str):
    """AI News Platform pipeline CLI."""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db
    ctx.obj["config_path"] = config


@cli.command()
@click.option("--all", "all_sources", is_flag=True, help="Ingest from all sources")
@click.option("--source", "source_id", help="Ingest from a specific source")
@click.pass_context
def ingest(ctx, all_sources: bool, source_id: Optional[str]):
    """Run the ingestion pipeline."""
    if not all_sources and not source_id:
        console.print("[red]Error:[/red] Specify --all or --source <id>")
        sys.exit(1)

    source_ids = [source_id] if source_id else None

    async def _run():
        orchestrator = IngestOrchestrator(
            config_path=ctx.obj["config_path"],
            db_path=ctx.obj["db_path"],
        )
        await orchestrator.initialize()
        try:
            with console.status("[bold green]Ingesting..."):
                summary = await orchestrator.ingest_all(source_ids=source_ids)

            # Display results
            table = Table(title="Ingest Results")
            table.add_column("Source", style="cyan")
            table.add_column("Fetched", justify="right")
            table.add_column("Inserted", justify="right", style="green")
            table.add_column("Duplicates", justify="right", style="yellow")
            table.add_column("Errors", justify="right", style="red")
            table.add_column("Time", justify="right")

            for r in summary.results:
                table.add_row(
                    r.source_id,
                    str(r.fetched),
                    str(r.inserted),
                    str(r.duplicates),
                    str(r.errors),
                    f"{r.duration_seconds:.1f}s",
                )
            table.add_section()
            table.add_row(
                "[bold]Total",
                f"[bold]{summary.total_fetched}",
                f"[bold green]{summary.total_inserted}",
                f"[bold yellow]{summary.total_duplicates}",
                f"[bold red]{summary.total_errors}",
                f"[bold]{summary.duration_seconds:.1f}s",
            )

            console.print(table)
        finally:
            await orchestrator.close()

    run_async(_run())


@cli.command()
@click.pass_context
def status(ctx):
    """Show database and source status."""

    async def _run():
        db = DatabaseManager(ctx.obj["db_path"])
        await db.initialize()
        try:
            stats = await db.get_stats()

            console.print("\n[bold]Database Status[/bold]")
            console.print(f"  Path: {ctx.obj['db_path']}")
            console.print(f"  Size: {stats['db_size_bytes'] / 1024:.1f} KB")
            console.print(f"  Items: {stats['total_items']}")
            console.print(f"  Sources: {stats['total_sources']}")
            console.print(f"  Metrics: {stats['total_metrics']}")
            console.print(f"  Digests: {stats['total_digests']}")

            if stats["items_by_category"]:
                console.print("\n[bold]Items by Category[/bold]")
                for cat, cnt in stats["items_by_category"].items():
                    console.print(f"  {cat}: {cnt}")

            if stats["items_by_source"]:
                console.print("\n[bold]Items by Source[/bold]")
                for src, cnt in stats["items_by_source"].items():
                    console.print(f"  {src}: {cnt}")

            # Show source details
            sources = await db.get_enabled_sources()
            if sources:
                console.print()
                table = Table(title="Source Status")
                table.add_column("ID", style="cyan")
                table.add_column("Enabled")
                table.add_column("Last Fetch")
                table.add_column("Errors", justify="right")
                table.add_column("Last Error")

                for s in sources:
                    last_fetch = (
                        s.last_fetch_at.strftime("%Y-%m-%d %H:%M")
                        if s.last_fetch_at
                        else "never"
                    )
                    table.add_row(
                        s.id,
                        "[green]yes" if s.enabled else "[red]no",
                        last_fetch,
                        str(s.error_count),
                        (s.last_error or "")[:50],
                    )
                console.print(table)
        finally:
            await db.close()

    run_async(_run())


@cli.command()
@click.argument("query")
@click.option("--category", "-c", help="Filter by category (news/tips/paper)")
@click.option("--lang", "-l", help="Filter by language (en/ja)")
@click.option("--source", "-s", help="Filter by source ID")
@click.option("--days", "-d", type=int, help="Only items from last N days")
@click.option("--limit", "-n", default=20, help="Max results")
@click.pass_context
def search(
    ctx,
    query: str,
    category: Optional[str],
    lang: Optional[str],
    source: Optional[str],
    days: Optional[int],
    limit: int,
):
    """Full-text search across all items."""

    async def _run():
        db = DatabaseManager(ctx.obj["db_path"])
        await db.initialize()
        try:
            since = None
            if days:
                since = datetime.utcnow() - timedelta(days=days)

            items = await db.search(
                query=query,
                category=category,
                language=lang,
                source_id=source,
                since=since,
                limit=limit,
            )

            if not items:
                console.print(f"[yellow]No results for:[/yellow] {query}")
                return

            total = await db.search_count(query)
            console.print(f"\n[bold]Search results for:[/bold] {query} ({total} total)\n")

            table = Table(show_header=True)
            table.add_column("#", style="dim", width=4)
            table.add_column("Title", max_width=60)
            table.add_column("Source", style="cyan", width=15)
            table.add_column("Category", width=8)
            table.add_column("Date", width=12)
            table.add_column("Lang", width=4)

            for i, item in enumerate(items, 1):
                pub_date = (
                    item.published_at.strftime("%Y-%m-%d")
                    if item.published_at
                    else "?"
                )
                table.add_row(
                    str(i),
                    item.title[:60],
                    item.source_id,
                    item.category,
                    pub_date,
                    item.language,
                )

            console.print(table)
        finally:
            await db.close()

    run_async(_run())


@cli.command()
@click.option("--optimize-fts", is_flag=True, help="Also optimize FTS index")
@click.pass_context
def vacuum(ctx, optimize_fts: bool):
    """Vacuum database and optionally optimize FTS index."""

    async def _run():
        db = DatabaseManager(ctx.obj["db_path"])
        await db.initialize()
        try:
            if optimize_fts:
                with console.status("[bold green]Optimizing FTS index..."):
                    await db.optimize_fts()
                console.print("[green]FTS index optimized")

            with console.status("[bold green]Vacuuming database..."):
                await db.vacuum()
            console.print("[green]Database vacuumed successfully")

            # Show new size
            stats = await db.get_stats()
            console.print(f"Database size: {stats['db_size_bytes'] / 1024:.1f} KB")
        finally:
            await db.close()

    run_async(_run())


def main():
    cli()


if __name__ == "__main__":
    main()
