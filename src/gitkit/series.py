from dataclasses import asdict, dataclass
import json
from git import Repo
from gitkit.parts import make_part, parse_part_name
import typer


app = typer.Typer()


@dataclass
class SeriesInfo:
    pass


def series_tag(name: str) -> str:
    return f"{name}-series-info"


def start_series(name: str):
    repo = Repo(".")

    info = asdict(SeriesInfo())

    old_head = repo.head.reference
    series_head = repo.create_head(name)
    series_head.checkout()

    repo.git.commit("--allow-empty", "-m", json.dumps(info))
    repo.create_tag(series_tag(name), series_head, force=True)

    old_head.checkout()
    repo.delete_head(series_head, force=True)

    make_part(1.0, begins_series_name=name)


def get_series_info():
    repo = Repo(".")

    series_name, _ = parse_part_name(repo.head.reference.name)
    return json.loads(repo.tags[series_tag(series_name)].commit.message)


@app.command(help="Start a new series")
def startseries(name: str):
    start_series(name)


@app.command(help="Get information stored on the series's information commit")
def seriesinfo():
    print(json.dumps(get_series_info(), indent=2))
