"""MCP server exposing the PDF and plot-digitizer tools to Claude.

Register with Claude Code:
  claude mcp add lab-tools -- <project>/.venv/bin/python <project>/mcp_server.py

Runs over stdio; tools take local file paths, so this is meant for
Claude Code / Claude Desktop on the same machine.
"""
from mcp.server.fastmcp import FastMCP
from PIL import Image

import extractor
import plot_digitizer

mcp = FastMCP("lab-tools")


@mcp.tool()
def pdf_to_text(pdf_path: str, fmt: str = "md", ocr_language: str = "eng") -> str:
    """Convert a local PDF to text without vision tokens. Pages with an
    embedded text layer are extracted losslessly; scanned pages are OCR'd
    with Tesseract.

    fmt: "md" (markdown, preserves headings/tables) or "txt" (plain text).
    ocr_language: Tesseract language code, e.g. "eng" or "kor".
    """
    result = extractor.extract(pdf_path, lang=ocr_language)
    body = result["md" if fmt == "md" else "txt"]
    note = (f"[{result['pages']} pages; OCR used on: {result['ocr_pages']}]"
            if result["ocr_pages"] else f"[{result['pages']} pages; no OCR needed]")
    return f"{note}\n\n{body}"


@mcp.tool()
def digitize_plot(
    image_path: str,
    x1_pixel: int, x1_value: float,
    x2_pixel: int, x2_value: float,
    y1_pixel: int, y1_value: float,
    y2_pixel: int, y2_value: float,
    colors: list[list[int]],
    mode: str = "line",
    tolerance: float = 40,
    max_points: int = 60,
    x_log: bool = False,
    y_log: bool = False,
) -> str:
    """Extract (x, y) data series from an image of a simple plot, returning
    compact text instead of requiring vision.

    Calibration: two points per axis with known data values. x*_pixel are
    image columns, y*_pixel are image rows (origin top-left). colors is a
    list of [r, g, b] for each data series. mode: "line" or "scatter".
    Set x_log / y_log for logarithmic axes.
    """
    calibration = {
        "x1": {"pixel": x1_pixel, "value": x1_value},
        "x2": {"pixel": x2_pixel, "value": x2_value},
        "y1": {"pixel": y1_pixel, "value": y1_value},
        "y2": {"pixel": y2_pixel, "value": y2_value},
    }
    series = plot_digitizer.digitize(
        Image.open(image_path), calibration, colors, mode=mode,
        tolerance=tolerance, max_points=max_points, x_log=x_log, y_log=y_log,
    )
    out = []
    for i, s in enumerate(series, 1):
        out.append(
            f"## Series {i} (rgb{tuple(s['color'])})\n"
            f"x = [{', '.join(str(p[0]) for p in s['points'])}]\n"
            f"y = [{', '.join(str(p[1]) for p in s['points'])}]"
        )
    return "\n\n".join(out) if out else "No data points found — try a higher tolerance."


@mcp.tool()
def list_ocr_languages() -> str:
    """List the Tesseract OCR languages installed on this machine."""
    return ", ".join(extractor.available_languages())


if __name__ == "__main__":
    mcp.run()
