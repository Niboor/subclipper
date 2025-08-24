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
        "sub2clip @ git+https://github.com/lpalinckx/sub2clip.git@0079aa4731f6536f15b68b2333ed139e4cebd632"
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "subclipper=subclipper.__main__:main",
        ],
    },
) 
