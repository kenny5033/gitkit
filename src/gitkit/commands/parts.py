import gitkit.logic.parts as logic
from typing import Annotated, Optional
from gitkit.utils import gitkit_bail
import typer

app = typer.Typer()


@app.command(help="Make a new part in the current series", rich_help_panel="Parts")
def makepart(
    part: Annotated[
        float,
        typer.Argument(
            ...,
            help="This branch's *numeric* identifier in a series of stacked branches, e.g. 1 or 2.5",
        ),
    ],
    last_commit: Annotated[
        Optional[str],
        typer.Argument(
            help="The last commit to include before the base of the new part",
        ),
    ] = None,
    series: Annotated[
        Optional[str],
        typer.Option(
            "--series",
            "-s",
            help="Manually override the series for this part. Will create the series if it doesn't already exist",
        ),
    ] = None,
):
    logic.make_part(part, last_commit, on_series=series)


@app.command(help="Rebase the current part", rich_help_panel="Parts")
def rebase(
    onto: Annotated[
        str,
        typer.Argument(..., help="The onto argument for the rebase"),
    ] = "origin/master",
    context: Annotated[
        bool,
        typer.Option(
            ...,
            help="Rebase the current part's default context ('onto' will probably be your default branch)",
        ),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option(
            help="Holds you accountable",
        ),
    ] = True,
):
    def yn_question(q: str):
        if not input(f"(gk) {q} (y/N): ").strip().startswith("y"):
            gitkit_bail("Have better standards!")

    if strict:
        yn_question("Did you verify each commited hunk is good to go?")
        yn_question(
            "Did you verify each string literal in any frontend changes is wrapped with _()?"
        )

    logic.rebase_part(onto, context_only=context)


@app.command(help="Get stats on lines changed", rich_help_panel="Parts")
def partstats(
    up_to: Annotated[
        Optional[str],
        typer.Argument(
            ..., help="The commit to go no further than for calculating line stats"
        ),
    ] = None,
    fall_back_onto: Annotated[
        str,
        typer.Option(
            ...,
            help="If this part has already been rebased, use this argument as the base of the part",
        ),
    ] = "origin/master",
):
    stats = logic.part_stats(up_to=up_to, fall_back_onto=fall_back_onto)
    print()
    print("Part Stats")
    print("----------")
    print(f"Lines Added:         {stats.lines_added:>5}")
    print(f"Lines Removed:       {stats.lines_removed:>5}")
    print(f"Total Lines Changed: {stats.total_lines_changed:>5}")
    print()
