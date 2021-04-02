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

import unittest
from pathlib import Path
from shutil import rmtree

import prance as prance
from click.testing import CliRunner

import schema2type.commands
from schema2type.commands.gen_stubs import get_relative_path
from examples.generated_files.openapi import RootObject as OpenAPISpecification, Schema

root_dir = Path(__file__).parent.parent


class UnitTestCase(unittest.TestCase):
    def test_get_relative_path(self):
        destination = '/some/path/to/openapi_spec.yml'
        origin = '/some/path/to-origin/directory'
        self.assertEqual(str(get_relative_path(origin=origin, destination=destination)), '../../to/openapi_spec.yml')

        origin = '/some/path/to'
        self.assertEqual(str(get_relative_path(origin=origin, destination=destination)), 'openapi_spec.yml')

        origin = '/some/path/to/sub-dir'
        self.assertEqual(str(get_relative_path(origin=origin, destination=destination)), '../openapi_spec.yml')

    def test_schema_based_object(self):
        pet_store_spec_path = str(root_dir.joinpath('examples/pet_store_openapi_spec.yml'))
        pet_store_spec_dict = prance.ResolvingParser(pet_store_spec_path).specification
        pet_store_spec_object = OpenAPISpecification(**pet_store_spec_dict)
        self.assertEqual(pet_store_spec_object.info.title, 'Swagger Petstore - OpenAPI 3.0')
        pet_schema = pet_store_spec_object.components.schemas['Pet']
        self.assertEqual(type(pet_schema), Schema)
        self.assertEqual(pet_schema.type, 'object')
        self.assertEqual(pet_schema.properties['name'].type, 'string')
        self.assertDictEqual(pet_store_spec_object.as_simple_dict(), pet_store_spec_dict)


def assert_files_equal(test: unittest.TestCase, path_a, path_b):
    with open(path_a) as file_a, open(path_b) as file_b:
        test.assertListEqual(list(file_a.readlines()),
                             list(file_b.readlines()))


def test_stub_generation(test: unittest.TestCase, relative_document_path, output_name, document_format: str):
    assert document_format in ['openapi', 'json_schema']
    output_dir = root_dir.joinpath('tests/generated_outputs')
    if output_dir.exists():
        rmtree(output_dir)
    runner = CliRunner()
    result = runner.invoke(schema2type.commands.main_command, [
        'gen-stubs',
        '--out', str(output_dir.absolute()),
        '--name', output_name,
        str(root_dir.joinpath(relative_document_path).absolute()),
        document_format,
    ], )
    print(result.output)
    test.assertIsNone(result.exception, msg=f'Exception occurred while running gen-stubs: '
                                            f'type="{type(result.exception)}", args="{result.exception}"')
    test.assertTrue(output_dir.exists())
    generated_module_file_path = output_dir.joinpath(f'{output_name}.py')
    stub_file_path = output_dir.joinpath(f'{output_name}.pyi')
    test.assertTrue(generated_module_file_path.exists())
    test.assertTrue(stub_file_path.exists())
    assert_files_equal(test, generated_module_file_path,
                       root_dir.joinpath(f'examples/generated_files/{output_name}.py'))
    assert_files_equal(test, stub_file_path, root_dir.joinpath(f'examples/generated_files/{output_name}.pyi'))


class IntegrationTestCase(unittest.TestCase):
    def test_openapi_stub_generation(self):
        test_stub_generation(
            test=self,
            relative_document_path='examples/openapi_specification_3.0.x_schema.yml',
            output_name='openapi',
            document_format='json_schema',
        )

    def test_pet_store_stub_generation(self):
        test_stub_generation(
            test=self,
            relative_document_path='examples/pet_store_openapi_spec.yml',
            output_name='pet_store',
            document_format='openapi',
        )


if __name__ == '__main__':
    unittest.main()
