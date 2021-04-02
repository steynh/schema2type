"""
Copyright 2021 Mokkit Oy

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""
from pathlib import Path

import setuptools


root_directory = Path(__file__).parent.parent


with open("README.md", "r") as readme_file:
    long_description = readme_file.read()


with open("requirements.txt") as requirements_file:
    requirements = list(requirement for requirement in requirements_file.readlines() if requirement != '')


setuptools.setup(
    name="schema2type",
    version="0.0.1",
    author="Steyn Huurman",
    author_email="steyn@mokkit.eu",
    description="Interact with JSON or YAML content as if it's a Python object",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mokkit/schema2type",
    packages=setuptools.find_packages(),
    install_requires=requirements,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    license='Apache 2.0',
    python_requires='>=3.6',
    entry_points={'console_scripts': ['schema2type = schema2type.__main__:main']},
)
