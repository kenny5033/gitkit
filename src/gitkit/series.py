from dataclasses import asdict, dataclass
import json
from typing import Annotated
from git import Repo
from gitkit.utils import gitkit_bail
import typer


app = typer.Typer()


@dataclass
class SeriesInfo:
    dependent_on: str | None = None


def series_tag(name: str) -> str:
    return f"{name}-series-info"


def start_series(name: str, *, exists_ok: bool = False, force: bool = False):
    from gitkit.parts import make_part, is_part_name_valid

    repo = Repo(".")

    if (already_exists := series_exists(name)) and exists_ok:
        return

    if not force:
        gitkit_bail(already_exists, f"Series {name} already exists")

    series_info = SeriesInfo()

    old_head = repo.head.reference

    # if it is a gitkit head, mark it as a series dependency
    if is_part_name_valid(old_head.name):
        series_info.dependent_on = old_head.name

    series_head = repo.create_head(name)
    series_head.checkout()

    info = asdict(series_info)
    repo.git.commit("--allow-empty", "-m", json.dumps(info))
    repo.create_tag(series_tag(name), series_head, force=True)

    old_head.checkout()
    repo.delete_head(series_head, force=True)

    make_part(1.0, on_series=name)


def get_series_info() -> dict:
    from gitkit.parts import parse_part_name

    repo = Repo(".")

    series_name, _ = parse_part_name(repo.head.reference.name)
    return json.loads(repo.tags[series_tag(series_name)].commit.message)


def series_exists(name: str) -> bool:
    repo = Repo(".")
    return series_tag(name) in [tag.name for tag in repo.tags]


@app.command(help="Start a new series", rich_help_panel="Series")
def startseries(
    name: Annotated[str, typer.Argument(help="The name of the series to create")],
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Whether to force the creation of this series"
        ),
    ] = False,
):
    start_series(name, force=force)


@app.command(
    help="Get information stored on the series's information commit",
    rich_help_panel="Series",
)
def seriesinfo():
    print(json.dumps(get_series_info(), indent=2))
