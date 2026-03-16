"""
TARAPATH - Setup Script
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="tarapath",
    version="1.0.0",
    author="TARAPATH Team",
    description="Offline Celestial Navigation System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/tarapath",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": ["pytest>=6.2.0", "black>=21.0", "flake8>=3.9.0"],
        "gpu": ["cupy>=9.0.0"],  # Optional GPU acceleration
    },
    entry_points={
        "console_scripts": [
            "tarapath=main:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)

