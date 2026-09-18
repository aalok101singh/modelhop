import click

from ..display import get_console

console = get_console()


@click.command()
@click.option("--host", default="127.0.0.1", help="Bind host")
@click.option("--port", default=8000, type=int, help="Bind port")
def serve(host: str, port: int) -> None:
    """:frog: Serve OpenAI-compatible HTTP endpoint (model=auto)."""
    try:
        import uvicorn  # type: ignore
    except ImportError:
        console.print("Server extra required: pip install modelhop[server]")
        raise SystemExit(1)
    from modelhop.serve.app import create_app

    app = create_app()
    uvicorn.run(app, host=host, port=port)
