from setuptools import setup, find_packages

setup(
    name="real-world-ai-data-hub",
    version="1.0.0",
    description="A comprehensive platform for collecting, processing, analyzing, and visualizing real-world data",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="AI Data Hub Team",
    author_email="info@aidatahub.example.com",
    url="https://github.com/real-world-ai-data-hub",
    packages=find_packages(),
    install_requires=[
        "flask==3.0.3",
        "sqlalchemy==2.0.30",
        "requests==2.32.5",
        "pandas==2.2.2",
        "numpy==1.26.4",
        "scipy==1.13.1",
        "matplotlib==3.8.4",
        "seaborn==0.13.2",
        "plotly==5.22.0",
    ],
    entry_points={
        'console_scripts': [
            'data-hub = data_hub.run_hub:main',
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
)