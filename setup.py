from setuptools import setup, find_packages

setup(
    name="jenkins-local-init",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "click>=8.0.0",
        "pyyaml>=6.0.0",
        "rich>=10.0.0",
        "requests>=2.31.0",
    ],
    entry_points={
        "console_scripts": [
            "jenkins-local-init=jenkins_local_init.cli.main:cli",
            "jnet=jenkins_local_init.cli.main:cli",
        ],
    },
    author="Siddartha Kodaboina",
    author_email="saikumar.siddartha@gmail.com",
    description="A CLI tool to set up Jenkins infrastructure locally on macOS",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Siddartha-Kodaboina/jenkins-local-init",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
        "Programming Language :: Python :: 3.8",
    ],
    python_requires=">=3.8",
)