from common import ROOT, new_run, command, finish
import shutil


def run():
    directory, manifest = new_run("paper")
    results = []
    for n, args in enumerate((["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
                              ["bibtex", "main"],
                              ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
                              ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"])):
        result, _ = command(args, directory, "step-" + str(n), timeout=90, cwd=ROOT / "docs/paper")
        results.append(result)
        if result["status"] != "passed":
            return finish(directory, manifest, "failed", results)
    log = (ROOT / "docs/paper/main.log").read_text(errors="replace")
    problems = [line for line in log.splitlines() if "Overfull" in line or
                "undefined references" in line or "undefined citations" in line or "Rerun to get" in line]
    results.append({"layout_and_reference_warnings": problems})
    (ROOT / "dist").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "docs/paper/main.pdf", ROOT / "dist/verified-coordination.pdf")
    return finish(directory, manifest, "passed" if not problems else "failed", results)


if __name__ == "__main__":
    raise SystemExit(run())
