from setuptools import setup, find_packages

setup(
    name="idun-sdk",
    version="0.1.0",
    description="Thin client + CLI for Azure AI Foundry agent NatureLM-Idun-5-MoE",
    packages=find_packages(),
    py_modules=["idun_cli"],
    python_requires=">=3.8",
    # stdlib-only: no runtime dependencies. Works headless on Termux.
    install_requires=[],
    entry_points={"console_scripts": ["idun=idun_cli:main"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
