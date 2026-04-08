import gitkit.logic.series as logic
from dataclasses import asdict
import json
from typing import Annotated, Optional
from gitkit.utils import gitkit_bail
import typer


app = typer.Typer()


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
    logic.start_series(name, force=force)


@app.command(
    help="Get either: 1) information stored on this part's series's data node or 2) information on this context's data node",
    rich_help_panel="Series",
)
def nodeinfo():
    node = logic.load_data_node()
    if node is None:
        gitkit_bail("Couldn't find data node for the current part")
    else:  # mainly to get types feeling good
        print(json.dumps(asdict(node), indent=2))


@app.command(
    help="Create a new context head from the combination of the current part and another given part",
    rich_help_panel="Series",
)
def newcontext(
    other: Annotated[
        str, typer.Argument(..., help="The other part to combine with the current part")
    ],
    name: Annotated[
        Optional[str],
        typer.Option(
            ...,
            help="The name to give this context, if you'd like to keep better track",
        ),
    ] = None,
):
    logic.create_context(other, name=name)


@app.command(
    help="Remove tags that are for parts, series, or contexts which no longer exist",
    rich_help_panel="Utilities",
)
def prune():
    logic.prune_tags()
