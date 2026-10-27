"""Render a GIF from real saved offline benchmark results; requires Pillow."""
import argparse
import json
from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, default=Path("runs/day3-offline"))
    parser.add_argument("--out", type=Path, default=Path("docs/assets/demo.gif"))
    args = parser.parse_args()
    baseline = json.loads((args.reports / "baseline.json").read_text())
    candidate = json.loads((args.reports / "candidate.json").read_text())
    comparison = json.loads((args.reports / "comparison.json").read_text())
    run = next(r for r in candidate["runs"] if r["scenario_id"] == "refund_above_limit")
    tool_lines = [f"{c['name']:<27} {c['status']:<8} {c['duration_ms']:.2f} ms" for c in run["calls"]]
    diagnostics = [s["reason"] for s in run["scores"] if not s["passed"]]
    scenes = [
        ("1 / Baseline", ["agentbench eval --agent ...:scripted_agent --trials 3", "",
            f"PASS {baseline['summary']['passed']}/{baseline['summary']['total']} runs", "",
            "20 isolated refund scenarios, repeated 3 times.", "No external models or real refunds."]),
        ("2 / Deliberate regression", ["agentbench eval --agent ...:flawed_agent --trials 3", "",
            f"PASS {candidate['summary']['passed']}/{candidate['summary']['total']} runs", "",
            "Same answers. Same final state.", "Different attempted actions."]),
        ("3 / Inspect the trace", ["agentbench trace --scenario refund_above_limit", ""] + tool_lines + ["", *diagnostics]),
        ("4 / Regression gate", ["agentbench compare --baseline ... --candidate ...", "",
            f"{len(comparison['regressions'])} case/trial regressions detected", ""] + comparison["violations"] + ["", "Gate: FAIL (exit 1)", "The mock tool blocked the refund. The evaluator caught the attempt."]),
    ]
    font_path = Path("C:/Windows/Fonts/consola.ttf")
    font = ImageFont.truetype(str(font_path), 23) if font_path.exists() else ImageFont.load_default(size=23)
    frames = []
    for title, lines in scenes:
        frame = Image.new("RGB", (1160, 650), "#101820")
        draw = ImageDraw.Draw(frame)
        draw.text((40, 30), "AGENTBENCH  /  BEHAVIORAL REGRESSION TESTING", font=font, fill="#60d5c6")
        draw.text((40, 90), title, font=font, fill="white")
        y = 150
        for line in lines:
            for wrapped in textwrap.wrap(line, 75) or [""]:
                draw.text((40, y), wrapped, font=font, fill="#d4dee8")
                y += 32
        draw.text((40, 605), "Rendered from saved deterministic reports; not a live-model recording.", font=font, fill="#899cae")
        frames.append(frame)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(args.out, save_all=True, append_images=frames[1:], duration=[3500, 3500, 6500, 5000], loop=0)
    print(args.out)


if __name__ == "__main__":
    main()
