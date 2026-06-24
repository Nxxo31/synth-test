"""
Terminal reporter for synth-test results.
Renders test suite results with color-coded output.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from typing import Union

from .types import TestCase, TestResult, TestSuite


# ---------------------------------------------------------------------------
# ANSI color codes (fallback when rich is not available)
# ---------------------------------------------------------------------------

class ANSIColors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"

    @classmethod
    def red(cls, text: str) -> str:
        return f"{cls.RED}{text}{cls.RESET}"

    @classmethod
    def green(cls, text: str) -> str:
        return f"{cls.GREEN}{text}{cls.RESET}"

    @classmethod
    def yellow(cls, text: str) -> str:
        return f"{cls.YELLOW}{text}{cls.RESET}"


# ---------------------------------------------------------------------------
# Reporter class
# ---------------------------------------------------------------------------

class Reporter:
    """
    Generates terminal reports from TestSuite results.
    Uses Rich for formatted output if available, falls back to plain text.
    """

    def __init__(self, use_rich: bool = True):
        self.use_rich = use_rich and self._rich_available()
        self.console = Console() if self.use_rich else None

    @staticmethod
    def _rich_available() -> bool:
        try:
            import rich
            return True
        except ImportError:
            return False

    def report(self, suite: TestSuite) -> str:
        """Generate and return the full report as a string (plain text only)."""
        return self._report_plain(suite)

    def print(self, suite: TestSuite) -> None:
        """Print the report to stdout with full Rich formatting."""
        if self.use_rich:
            self._print_rich(suite)
        else:
            print(self._report_plain(suite))

    def _print_rich(self, suite: TestSuite) -> None:
        """Print a Rich-formatted report directly to console."""
        console = self.console

        total = suite.total_cases
        failed = len(suite.failed_cases)
        passed = len(suite.passed_cases)
        error_rate = suite.error_rate
        duration = sum(r.duration_ms for r in suite.results)

        summary_lines = [
            f"  Endpoint:     [bold cyan]{suite.method} {suite.endpoint}[/bold cyan]",
            f"  Total cases: [bold]{total}[/bold]",
            f"  [green]Passed:[/green]  {passed} ([green]{((passed / total * 100) if total else 0):.1f}%[/green])",
            f"  [red]Failed:[/red]    {failed} ([red]{((failed / total * 100) if total else 0):.1f}%[/red])",
            f"  Duration:    [dim]{duration:.1f}ms[/dim]",
        ]

        if failed > 0:
            summary_lines.insert(
                3,
                f"  [bold red]ERROR RATE: {error_rate * 100:.1f}%[/bold red]"
            )

        summary_text = Text("\n".join(summary_lines))
        summary_panel = Panel(
            summary_text,
            title="[bold]synth-test Report[/bold]",
            border_style="cyan",
            box=box.DOUBLE,
        )

        # Failed cases table
        if suite.failed_cases:
            table = Table(
                title="[bold red]Failed Cases[/bold red]",
                show_header=True,
                header_style="bold red",
                box=box.SIMPLE,
            )
            table.add_column("Name", style="cyan", no_wrap=False)
            table.add_column("Path", style="blue")
            table.add_column("Value", style="magenta", no_wrap=False)
            table.add_column("Category", style="yellow")
            table.add_column("Status", style="red")

            for result in suite.failed_cases:
                status_text = f"[red]{result.response_status}[/red] {result.error or ''}"
                value_repr = self._truncate(repr(result.case.generated_value), 40)

                table.add_row(
                    result.case.name,
                    result.case.path,
                    value_repr,
                    result.case.category,
                    status_text,
                )

            failed_panel = Panel(table, border_style="red", box=box.DOUBLE)
        else:
            failed_panel = Panel(
                Text("[green]No failures - all cases passed![/green]"),
                border_style="green",
                box=box.DOUBLE,
            )

        # Passed cases summary (first 20)
        if suite.passed_cases:
            passed_table = Table(
                title="[green]Passed Cases (first 20)[/green]",
                show_header=True,
                header_style="bold green",
                box=box.SIMPLE,
            )
            passed_table.add_column("Name", style="cyan")
            passed_table.add_column("Path", style="blue")
            passed_table.add_column("Category", style="yellow")
            passed_table.add_column("Status", style="green")

            for result in suite.passed_cases[:20]:
                passed_table.add_row(
                    result.case.name,
                    result.case.path,
                    result.case.category,
                    f"[green]{result.response_status}[/green]",
                )

            passed_panel = Panel(passed_table, border_style="green", box=box.DOUBLE)
        else:
            passed_panel = None

        # Compose output
        from rich.console import Group
        if passed_panel:
            content = Group(summary_panel, failed_panel, passed_panel)
        else:
            content = Group(summary_panel, failed_panel)

        console.print(Panel(content, border_style="cyan"))  # type: ignore[union-attr]

    def _report_plain(self, suite: TestSuite) -> str:
        """Generate a plain-text report."""
        lines = []
        total = suite.total_cases
        failed = len(suite.failed_cases)
        passed = len(suite.passed_cases)

        lines.append("=" * 60)
        lines.append("  synth-test Report")
        lines.append("=" * 60)
        lines.append(f"  Endpoint:    {suite.method} {suite.endpoint}")
        lines.append(f"  Total cases: {total}")
        lines.append(f"  Passed:      {passed} ({((passed / total * 100) if total else 0):.1f}%)")
        lines.append(f"  Failed:      {failed} ({((failed / total * 100) if total else 0):.1f}%)")
        lines.append("=" * 60)

        if failed > 0:
            lines.append("\n  *** ERROR RATE: {:.1f}% ***".format(suite.error_rate * 100))
            lines.append("\n  FAILED CASES:")
            lines.append("-" * 60)
            for result in suite.failed_cases:
                lines.append(f"  [{result.response_status}] {result.case.name}")
                lines.append(f"    Path:     {result.case.path}")
                lines.append(f"    Value:    {self._truncate(repr(result.case.generated_value), 50)}")
                lines.append(f"    Category: {result.case.category}")
                if result.error:
                    lines.append(f"    Error:    {result.error}")
                lines.append("")

        if passed:
            lines.append(f"\n  PASSED CASES ({len(suite.passed_cases)} total, first 20):")
            lines.append("-" * 60)
            for result in suite.passed_cases[:20]:
                lines.append(
                    f"  [OK] {result.case.name} ({result.case.category})"
                )
            if len(suite.passed_cases) > 20:
                lines.append(f"  ... and {len(suite.passed_cases) - 20} more")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len - 3] + "..."


def report(suite: TestSuite) -> str:
    """Convenience function to generate a plain text report."""
    reporter = Reporter()
    return reporter.report(suite)


def print_report(suite: TestSuite) -> None:
    """Convenience function to print a full report."""
    reporter = Reporter()
    reporter.print(suite)