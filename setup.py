from setuptools import setup, find_packages


def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as f:
        return f.read().splitlines()


setup(
    name="djangoapprove",
    version="0.2.0",
    description="A Django module to manage approval workflows for CRUD operations.",
    long_description=open("README.md", "r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Byron Cabrera",
    author_email="byron.o.cabrera@gmail.com",
    url="https://github.com/ullauri/djangoapprove",
    packages=find_packages(exclude=["tests*"]),
    include_package_data=True,
    install_requires=read_requirements(),
    python_requires=">=3.7",
    license="MIT",
    keywords="django, approvals, workflow, CRUD",
    project_urls={
        "Source": "https://github.com/ullauri/djangoapprove",
    },
)

