import typer
from .parts import app as parts_typer
from .series import app as series_typer


app = typer.Typer()

app.add_typer(parts_typer)
app.add_typer(series_typer)


def main():
    app()
