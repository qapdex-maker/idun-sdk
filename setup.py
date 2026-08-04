from setuptools import setup, find_packages
import os
import sys

# Sdist install banner. Wheels cannot run code on install (PEP 427), so this
# only appears for source builds (`pip install --no-binary` / local `pip install .`).
_INSTALL_BANNER = (
    "\033[38;5;141m"
    "  ___ _    ___ _  _  _   _ _____ _    ___\n"
    " |_ _| |  |_ _| \\| |/ \\| | |_   _| |  | __|\n"
    "  | || |__ | || .` / _ \\ |   | | | |__| _|\n"
    " |___|____|___|_|\\/_/ \\_\\_|  |_| |____|___|\n"
    "\033[0m"
    "  \033[38;5;57mNatureLM-Idun-5-MoE  ·  Azure AI Foundry\033[0m\n"
    "  \033[38;5;141midun-sdk\033[0m installed — run `idun welcome` for the full intro.\n"
)


def _print_banner():
    try:
        sys.stdout.write(_INSTALL_BANNER + "\n")
        sys.stdout.flush()
    except Exception:
        pass


try:
    from setuptools.command.install import install as _install

    class _BannerInstall(_install):
        def run(self):
            _print_banner()
            super().run()
except Exception:
    _BannerInstall = None

_cmdclass = {"install": _BannerInstall} if _BannerInstall else {}

this_dir = os.path.dirname(os.path.abspath(__file__))
readme_path = os.path.join(this_dir, "README.md")
with open(readme_path, encoding="utf-8") as f:
    LONG_DESCRIPTION = f.read()

setup(
    name="idun-sdk",
    version="0.1.30",
    description="Thin client + CLI for Azure AI Foundry agent NatureLM-Idun-5-MoE",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author="Idun",
    author_email="alexanderkleine@qmfiresearch.onmicrosoft.com",
    url="https://github.com/qapdex-maker/idun-sdk",
    project_urls={
        "Source": "https://github.com/qapdex-maker/idun-sdk",
        "Playground": "https://github.com/qapdex-maker/idun-playground",
        "Docs (GitMCP)": "https://gitmcp.io/qapdex-maker/idun-sdk/sse",
        "Bug Tracker": "https://github.com/qapdex-maker/idun-sdk/issues",
    },
    packages=find_packages(),
    py_modules=["idun_cli", "idun_mcp"],
    package_data={"idun": ["data/*.svg", "data/prompt_packs/*.json"]},
    python_requires=">=3.8",
    # stdlib-only: no runtime dependencies. Works headless on Termux.
    install_requires=[],
    cmdclass=_cmdclass,
    entry_points={"console_scripts": ["idun=idun_cli:main", "idun-mcp=idun_mcp:main"]},
    keywords=[
        "azure", "ai-foundry", "azure-ai-foundry", "agent", "tool-agent",
        "mcp", "model-context-protocol", "naturelm", "idun", "llm",
        "cli", "stdlib", "termux", "web_search", "trace",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
