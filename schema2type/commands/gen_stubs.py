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
from typing import Union

import click

import schema2type
from schema2type.__main__ import main_command
from schema2type import gen_stub_text, gen_module_text


def allowed_to_write(output_file_path) -> bool:
    if output_file_path.exists():
        return input(f"Output file '{output_file_path}' exists. Overwrite? (y/N).").lower() == 'y'
    return True


def paths_are_relative(abs_origin: Path, abs_destination: Path):
    try:
        abs_destination.relative_to(abs_origin)
        return True
    except ValueError:
        return False


def get_relative_path(origin: Union[Path, str], destination: Union[Path, str]):
    origin = Path(origin).absolute()
    destination = Path(destination).absolute()

    if paths_are_relative(origin, destination):
        return destination.relative_to(origin)

    num_dirs_above_origin = 0
    shared_origin = origin
    while not paths_are_relative(shared_origin, destination):
        num_dirs_above_origin += 1
        shared_origin = shared_origin.parent
        if num_dirs_above_origin > 20:
            raise click.ClickException(f'can''t find relative path from "{origin}" to "{destination}".')
    relative_path = Path('../' * num_dirs_above_origin).joinpath(destination.relative_to(shared_origin))
    return relative_path


@main_command.command(help='Just try running this command and see what happens.')
@click.argument('document_path')
@click.argument('document_type',
                type=click.Choice(schema2type.specification_type_to_interface_class.keys()))
@click.option('-o', '--out', help='Directory for the generated files.', default='./')
@click.option('-f', '--force', help='Overwrite existing files.', default=False, is_flag=True)
@click.option('-n', '--name', help='Name of the submodule files.', default=None)
def gen_stubs(document_path, document_type, out, force, name):
    out_dir = Path(out)
    document_path = Path(document_path)

    if out_dir.is_file():
        raise click.ClickException('output directory is a file')

    if name is None:
        name = f'schema_based_classes'

    stub_file_path = out_dir.joinpath(f'{name}.pyi')
    module_file_path = out_dir.joinpath(f'{name}.py')

    if not out_dir.exists():
        out_dir.mkdir(parents=True)

    if not force:
        if not allowed_to_write(stub_file_path) or not allowed_to_write(module_file_path):
            return

    try:
        stub_text = gen_stub_text(document_path, document_type)
        module_text = gen_module_text(get_relative_path(origin=out_dir, destination=document_path),
                                      document_type)
    except (FileNotFoundError, PermissionError):
        raise click.ClickException(f"no readable document found at '{document_path}'")
    except schema2type.DocumentError as e:
        raise click.ClickException(f'can\'t parse the document at "{document_path}".\n  {e}')
    except Exception as e:
        raise click.ClickException(f'unexpect exception occurred.\n  {e}\n'
                                   f'  please report this at https://github.com/mokkit/schema2type/issues')

    path_to_write = stub_file_path
    try:
        with open(stub_file_path, 'w') as file:
            file.write(stub_text)
        path_to_write = module_file_path
        with open(module_file_path, 'w') as file:
            file.write(module_text)
    except Exception:
        raise click.ClickException(f"can't write to file at '{path_to_write}'.")
