# Schema2type

Schema2type: interact with JSON or YAML content as if it's a Python object.
How it works:
- You specify the desired or expected format of your content using a [JSON Schema](https://json-schema.org/) or 
  [OpenAPI Specification (version 3)](https://swagger.io/specification/).
- Schema2type then creates dynamic Python types for all the (sub-)schemas described by that schema/specification.
- You can make use of these types from anywhere in your code to interact with the JSON or YAML content.
- Schema2type also generates so-called [stub files](https://mypy.readthedocs.io/en/stable/stubs.html), 
  which allow you to make use of your IDE's auto-complete functionality for the dynamically created types 
  (this is arguably the most convenient feature of this module and works with both PyCharm and VS Code).


JSON/YAML content can be read from a file, but it can also be content obtained through any other means, such as through
an HTTP request.

## Example
If you frequently interact with OpenAPI Specifications, you might want make use of dynamic classes based on the 
[JSON schema that describes the format of an OpenAPI Specification](https://github.com/OAI/OpenAPI-Specification/blob/master/schemas/v3.0/schema.yaml)
(indeed, "a specification of a specification document" is rather meta, but very useful in this case).

```python
import prance
from my_schema_classes.openapi import RootObject as OpenAPISpecification

# resolve references in the specification with the prance module
resolved_specification = prance.ResolvingParser('/path/to/pet_store_openapi_spec.yml').specification

# create a schema-based object from the YAML content
specification_object = OpenAPISpecification(**resolved_specification)

# access information from the specification with auto-complete to guide you along the way:
print(specification_object.info.title)                       # > Swagger Petstore - OpenAPI 3.0
print(type(specification_object.components))                 # > <class 'schema2type.Components'>
pet_schema = specification_object.components.schemas['Pet']
print(type(pet_schema))                                      # > <class 'schema2type.Schema'>
print(pet_schema.required)                                   # > ['name', 'photoUrls']

```

## Compatibility
At the time of  writing, schema2type has been tested with schemas specified in the following formats/documents:
- [OpenAPI Specification Version 3.0](https://swagger.io/specification/)
- [JSON Schema Draft 4](https://tools.ietf.org/html/draft-zyp-json-schema-04)


## Disclaimer
This module is currently in development. At the moment, it can handle most, but not all situations when it comes to 
parsing your JSON schema or OpenAPI specification. Use at your own risk of running into any potential errors. Support
for `oneOf`, `allOf`, and `anyOf` schemas is still limited.

## How to install
This module is not on *pypi* yet, so ensure your virtualenv is activated (if using one at all) and then install as follows:
```bash
git clone https://github.com/mokkit/schema2type.git
pip install schema2type/
```

## Usage
First, generate the stub files based on your schema or specification:
```bash
mkdir "/path/to/my_package/my_module/schema_classes"
schema2type gen-stubs --out "/path/to/my_package/my_module/schema_classes" --name "my_schema_name" "/path/to/my_package/a_schema.yml" json_schema
```
Then, import the schema based classes from within your module wherever you need them:
```python
from my_package.schema_classes.my_schema import *
```

## License
Copyright 2021 Mokkit Oy

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

   [http://www.apache.org/licenses/LICENSE-2.0]()

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.