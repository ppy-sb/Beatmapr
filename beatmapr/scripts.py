from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer

from beatmapr.app.updaters import (
    PACK_BATCH_SIZE,
    USERS_BATCH_SIZE,
    USERS_MAX_RETRIES,
    USERS_PAGE_LIMIT,
    MissingCredentialsError,
    PackUpdater,
    PackUpdateSummary,
    UserImportSummary,
    UserUpdater,
)

app = typer.Typer(help="Beatmapr maintenance scripts")
pack_app = typer.Typer(help="Pack maintenance")
user_app = typer.Typer(help="User maintenance")
app.add_typer(pack_app, name="packs")
app.add_typer(user_app, name="users")


@pack_app.command("update", help="Update pack data from osu! official API")
def update_packs(
    batch_size: int = typer.Option(PACK_BATCH_SIZE, min=1, help="Number of packs to commit to the database per batch"),
    include_other: bool = typer.Option(True, help="Sync packs from other categories"),
) -> None:
    updater = PackUpdater()

    try:
        standard_summary = updater.update_standard(batch_size=batch_size)
        _print_pack_summary("Standard Packs", standard_summary)

        if include_other:
            other_summary = updater.update_other(batch_size=batch_size)
            _print_pack_summary("Other Categories", other_summary)
    except MissingCredentialsError as exc:
        typer.secho(str(exc), fg="red")
        raise typer.Exit(code=1) from exc


@pack_app.command("import", help="Import pack data from local JSON files")
def import_packs(
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Path to a JSON file or directory; if not provided, auto-discover"),
    pack_type: str = typer.Option("auto", "--type", "-t", help="auto/standard/other, default auto-detect"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Override default category used during import"),
    recursive: bool = typer.Option(False, "--recursive", help="Recursively search directory for JSON files"),
) -> None:
    pack_type_normalised = pack_type.lower()
    if pack_type_normalised not in {"auto", "standard", "other"}:
        raise typer.BadParameter("type must be auto, standard, or other")

    updater = PackUpdater()
    summary = updater.import_from_path(
        path,
        pack_type=None if pack_type_normalised == "auto" else pack_type_normalised,
        category_hint=category,
        recursive=recursive,
    )

    _print_pack_summary("Import results", summary)

    if summary.errors:
        _print_errors(summary.errors)
        raise typer.Exit(code=1)


@user_app.command("sync", help="Sync Relax users from Akatsuki API")
def sync_users(
    limit: int = typer.Option(USERS_PAGE_LIMIT, min=1, help="Number of users per page request"),
    batch_size: int = typer.Option(USERS_BATCH_SIZE, min=1, help="Number of concurrent page requests"),
    max_retries: int = typer.Option(USERS_MAX_RETRIES, min=0, help="Maximum retry attempts for failed pages"),
    max_pages: Optional[int] = typer.Option(None, min=1, help="Limit max pages for this run"),
) -> None:
    updater = UserUpdater()
    result = asyncio.run(updater.sync_from_akatsuki(limit=limit, batch_size=batch_size, max_retries=max_retries, max_pages=max_pages))
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@user_app.command("import", help="Import user data from local JSON files")
def import_users(
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Path to a JSON file or directory; if not provided, auto-discover"),
    recursive: bool = typer.Option(False, "--recursive", help="Recursively search directory for JSON files"),
) -> None:
    updater = UserUpdater()
    summary = updater.import_from_path(path, recursive=recursive)
    _print_user_summary(summary)

    if summary.errors:
        _print_errors(summary.errors)
        raise typer.Exit(code=1)


@user_app.command("totals", help="Update user total plays based on *_scores.txt files")
def update_user_totals(
    data_directory: Optional[Path] = typer.Option(None, "--data-directory", "-d", help="Manually specify scores file directory"),
    batch_size: int = typer.Option(200, min=1, help="Number of users processed per batch"),
) -> None:
    updater = UserUpdater()
    result = updater.update_totals_from_files(data_directory=data_directory, batch_size=batch_size)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


def _print_pack_summary(title: str, summary: PackUpdateSummary) -> None:
    typer.secho(f"{title}:", bold=True)
    typer.echo(f"  Processed packs: {summary.processed}")
    typer.echo(f"  Inserted: {summary.inserted}")
    typer.echo(f"  Updated: {summary.updated}")
    if summary.skipped:
        typer.echo(f"  Skipped: {summary.skipped}")
    if summary.files:
        typer.echo("  Source files:")
        for file_path in summary.files:
            typer.echo(f"    - {file_path}")


def _print_user_summary(summary: UserImportSummary) -> None:
    typer.secho("User import:", bold=True)
    typer.echo(f"  Processed users: {summary.processed}")
    typer.echo(f"  Inserted: {summary.inserted}")
    typer.echo(f"  Updated: {summary.updated}")
    if summary.skipped:
        typer.echo(f"  Skipped: {summary.skipped}")
    if summary.files:
        typer.echo("  Source files:")
        for file_path in summary.files:
            typer.echo(f"    - {file_path}")


def _print_errors(errors: dict[str, str]) -> None:
    typer.secho("The following errors occurred:", fg="red")
    for source, message in errors.items():
        typer.echo(f"  {source}: {message}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
