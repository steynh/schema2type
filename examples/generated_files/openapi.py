from pathlib import Path

import schema2type
from schema2type import SchemaBasedObject, Reference

globals().update(schema2type.SchemaBasedTypeBuilder(
    Path(__file__).parent.joinpath('../../examples/openapi_specification_3.0.x_schema.yml'),
    'json_schema',
).get_all_types())
