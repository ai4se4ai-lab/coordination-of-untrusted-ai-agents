import shutil
import sys
from common import ROOT, command, new_run, finish, java


def run():
    directory, manifest = new_run("doctor")
    checks = {}
    for name, args in {
        "python": [sys.executable, "--version"],
        "java": [java() or "java", "-version"],
        "pdflatex": ["pdflatex", "--version"],
        "bibtex": ["bibtex", "--version"],
        "tlaps": ["tlapm", "--version"],
        "docker": ["docker", "version", "--format", "{{.Server.Version}}"],
        "tlaps_container": ["docker", "run", "--rm", "--network", "none", "--mount", f"type=bind,source={ROOT},target=/work",
                            "vgc-tlaps:local", "/work/.tools/tlapm/bin/tlapm", "--version"],
    }.items():
        result, output = command(args, directory, name, timeout=20)
        result["version_output"] = output[:2000]
        checks[name] = result
    checks["tlc_jar"] = {"status": "installed" if (ROOT / ".tools/tla2tools.jar").is_file() else "missing"}
    checks["scope"] = "Tool availability report; not a proof or model check"
    return finish(directory, manifest, "passed", checks)


if __name__ == "__main__":
    raise SystemExit(run())
