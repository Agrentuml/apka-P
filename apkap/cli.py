"""
apka-P [APK API] — GraphQL schema extractor from Android APKs
"""

import sys
import click
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .extractor import Extractor

console = Console()

VERSION = "0.2.0"

BANNER = """ █████╗ ██████╗ ██╗  ██╗ █████╗       ██████╗ 
██╔══██╗██╔══██╗██║ ██╔╝██╔══██╗      ██╔══██╗
███████║██████╔╝█████╔╝ ███████║█████╗██████╔╝
██╔══██║██╔═══╝ ██╔═██╗ ██╔══██║╚════╝██╔═══╝ 
██║  ██║██║     ██║  ██╗██║  ██║      ██║     
╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝      ╚═╝     """


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("apk_path", type=click.Path(exists=True, dir_okay=False), metavar="APK")
@click.option("-o", "--output", default=None, metavar="DIR",
              help="Output directory (default: ./apkap_output/<apk_name>/)")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed extraction steps")
@click.option("--no-html", is_flag=True, help="Skip HTML report")
@click.option("--no-json", is_flag=True, help="Skip JSON output")
@click.option("--apktool", default="apktool", metavar="PATH",
              help="Path to apktool binary (default: apktool)")
@click.option("--version", "show_version", is_flag=True, is_eager=True,
              expose_value=False, callback=lambda ctx, p, v: (
                  click.echo(f"apka-P [APK API] v{VERSION}") or ctx.exit()
              ) if v else None,
              help="Show version and exit")
def main(apk_path, output, verbose, no_html, no_json, apktool):
    """
    apka-P [APK API] — Extract GraphQL schema from Android APKs.

    Works even when server introspection is disabled.
    Reads DEX string pool, assets, smali, and JS bundles.

    \b
    Examples:
      apka-p app.apk
      apka-p app.apk -o ~/bug-bounty/output/ -v
      apka-p app.apk --no-html
    """
    console.print(BANNER, style="bold magenta")
    console.print(f"  [dim]APK API[/dim] [bold white]v{VERSION}[/bold white]\n")

    apk  = Path(apk_path)
    out_dir = Path(output) if output else Path("apkap_output") / apk.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel(
        f"[bold]Target:[/bold] {apk}\n[bold]Output:[/bold] {out_dir}",
        style="cyan", padding=(0, 1)
    ))

    with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                  console=console, transient=True) as progress:
        progress.add_task("Analyzing APK...", total=None)
        extractor = Extractor(apk, apktool_bin=apktool, verbose=verbose)
        result = extractor.run()

    ops   = result.get("operations", [])
    types = result.get("types", [])
    queries       = [o for o in ops if o["type"] == "query"]
    mutations     = [o for o in ops if o["type"] == "mutation"]
    subscriptions = [o for o in ops if o["type"] == "subscription"]

    console.print()
    console.print(Panel(
        f"[bold green]Strategy:[/bold green]     {result.get('strategy', 'none')}\n"
        f"[bold cyan]Queries:[/bold cyan]       {len(queries)}\n"
        f"[bold yellow]Mutations:[/bold yellow]    {len(mutations)}\n"
        f"[bold magenta]Subscriptions:[/bold magenta] {len(subscriptions)}\n"
        f"[bold white]Types:[/bold white]         {len(types)}",
        title="[bold]Results[/bold]", style="green"
    ))

    if not ops and not types:
        console.print("\n[bold red]Nothing found.[/bold red]")
        console.print("[dim]The APK may use string encryption (DexGuard/Allatori) "
                      "or doesn't use GraphQL.[/dim]")
        sys.exit(1)

    if not no_json:
        from .reporters.json_reporter import write_json
        json_path = out_dir / "schema.json"
        write_json(result, json_path)
        console.print(f"[green]✓[/green] JSON → {json_path}")

    if not no_html:
        from .reporters.html_reporter import write_html
        html_path = out_dir / "schema.html"
        write_html(result, html_path, apk_name=apk.name)
        console.print(f"[green]✓[/green] HTML → {html_path}")

    console.print(f"\n[bold]Open [cyan]{out_dir}/schema.html[/cyan] in browser[/bold]")


if __name__ == "__main__":
    main()
