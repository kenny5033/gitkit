from typing import Annotated
from git import Repo
from gitkit.utils import set_app_repo
import typer
from gitkit.commands.parts import app as parts_app
from gitkit.commands.series import app as series_app
from gitkit.commands.misc import app as misc_app


app = typer.Typer()


@app.callback()
def gitkit_common_options(
    repo_path: Annotated[
        str, typer.Option(help="The path of the repo to call this verification on")
    ] = ".",
):
    set_app_repo(Repo(repo_path))


app.add_typer(parts_app, rich_help_panel="Parts")
app.add_typer(series_app, rich_help_panel="Series")
app.add_typer(misc_app, rich_help_panel="Utilities")


def main():
    app()
