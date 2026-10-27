# Tool provenance

Downloads and SHA-256 hashes are in environment/toolchain.lock.json. TLC jar is
from the TLA+ v1.8.0 release URL; its banner reports build 2026.10.26.231022,
revision fad899c. A versioned URL is not assumed immutable: bootstrap verifies bytes.
TLAPS is the 1.6.0-pre Linux archive; --version reports 5f5037f, with bundled
Z3 4.8.9, Zenon 0.8.4 and Isabelle2025. Proof runs use SMT and do not request
Isabelle replay. Backend configuration and clean run output are captured.

Test host: Windows 11, Python 3.13.14, Amazon Corretto Java 11.0.16.1 discovered
read-only in an existing application runtime, MiKTeX 24.1, Docker 29.5.3. No global
Java or WSL distribution installation was performed. Native Linux uses Java on
PATH (or VGC_JAVA) and optionally TLAPS on PATH.

Official documentation consulted before writing wrappers:

* https://docs.tlapl.us/using:tlc:start
* https://proofs.tlapl.us/doc/web/content/Download/Binaries/Windows.html
* https://proofs.tlapl.us/doc/web/content/Download/Binaries/Linux.html
* https://github.com/tlaplus/tlaplus/releases
* https://www.springernature.com/gp/authors/campaigns/latex-author-support

Docker's musl service distro could not directly execute the glibc archive.
Debian bookworm was also too old (GLIBC_2.38 required). The pinned trixie base
plus procps resolves this. Both failed setup attempts are described here, not
reported as proof runs. Initial Budget/kernel proof failures are preserved in
results/raw/20261027T013215-proofs-1049b432 with source hashes.
