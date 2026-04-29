from setuptools import setup, find_packages

setup(
    name="apka-p",
    version="0.1.0",
    description="GraphQL schema extractor from Android APKs (when introspection is disabled)",
    author="You",
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "rich>=13.0",
        "graphql-core>=3.2",
    ],
    entry_points={
        "console_scripts": [
            "apka-p=apkap.cli:main",
        ],
    },
    python_requires=">=3.10",
)
