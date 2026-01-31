from setuptools import setup, find_packages

setup(
    name="subclipper",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "flask>=3.1.0",
        "matplotlib>=3.10.1",
        "pillow>=11.1.0",
        "pysubs2>=1.8.0",
        "python-ffmpeg>=2.0.12",
        "gunicorn>=23.0.0",
        "sub2clip @ git+https://github.com/lpalinckx/sub2clip.git@c1ead383bc9ffa5755c14633915fc559ed6a8740",
        "gevent>=25.9.1",
        "duckdb>=1.4.4",
        "pykka>=4.4.1",
        "pytest-timeout>=2.4.0"
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "subclipper=src.__main__:main",
        ],
    },
) 
