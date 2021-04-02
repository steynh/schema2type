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

from __future__ import annotations

import keyword
import re
import logging
from abc import abstractmethod, ABC
from typing import Dict, List, Any, Callable, Iterable, Optional, Type, Union

import yaml
from openapi_schema_validator import OAS30Validator


SimpleType = Union[int, float, bool, str]


def to_simple(original_object: Union[Dict, List, SchemaBasedObject, SimpleType]):
    if isinstance(original_object, SchemaBasedObject):
        simple_object = {
            key: to_simple(value) for key, value in original_object.get_all_properties().items()
        }
    elif isinstance(original_object, dict):
        simple_object = {
            key: to_simple(value) for key, value in original_object.items()
        }
    elif isinstance(original_object, list):
        simple_object = [to_simple(value) for value in original_object]
    else:
        simple_object = original_object
    return simple_object


class SchemaBasedObject(object):
    _property_name_to_type: Dict[str, SchemaBasedTypeInfo]
    _additional_properties_type: Optional[SchemaBasedTypeInfo]
    _schema: Dict = {}
    _legal_property_name_to_original: Dict[str, str]
    _additional_properties_allowed: bool = True

    def __init__(self, **properties: Dict[str, Any]):
        OAS30Validator(self._schema).validate(properties)

        self._properties = {}
        for property_name, property_value in properties.items():
            if property_name in self._legal_property_name_to_original:
                property_name = self._legal_property_name_to_original[property_name]

            if property_name in self._property_name_to_type:
                constructor = self._property_name_to_type[property_name].constructor
                self._properties[property_name] = constructor(property_value)
            elif self._additional_properties_allowed:
                if self._additional_properties_type is not None:
                    self._properties[property_name] = self._additional_properties_type.constructor(property_value)
                else:
                    self._properties[property_name] = property_value
            else:
                raise ValueError(f'additional property {property_name} is not allowed '
                                 f'for constructing objects of class {self.__class__.__name__}')

    def get_all_properties(self) -> Dict[str, Any]:
        return self._properties

    def get_additional_properties(self) -> Dict[str, Any]:
        return {
            key: value for key, value in self._properties.items() if key not in self._property_name_to_type
        }

    def as_simple_dict(self):
        return to_simple(self)

    def __getitem__(self, item):
        if item not in self._properties:
            raise KeyError(f"{self} has no property {item}")
        return self._properties[item]

    def __repr__(self):
        required_properties = {
            name: value
            for name, value in self._properties.items()
            if name in self._property_name_to_type and self._property_name_to_type[name].required
        }
        return f'{type(self).__name__}<{str(required_properties)}>'

    def __contains__(self, item):
        return item in self._properties

    def __iter__(self):
        return self._properties.items().__iter__()


class SpecificationInterface(ABC):
    SCHEMA_REFERENCE_PATTERN: re.Pattern

    def __init__(self, specification):
        self._specification = specification

    def __init_subclass__(cls, **kwargs):
        assert re.compile(cls.SCHEMA_REFERENCE_PATTERN).groups == 1, 'expected only a single capture group for "schema name"'

    def schema_exists(self, schema_name):
        return schema_name in self.get_schema_names()

    @classmethod
    def parse_schema_name(cls, schema_ref_str):
        schema_ref_str_match = re.fullmatch(cls.SCHEMA_REFERENCE_PATTERN, schema_ref_str)
        if schema_ref_str_match is None:
            raise DocumentError(f'invalid schema reference string: {schema_ref_str}')
        return schema_ref_str_match.group(1)

    @abstractmethod
    def get_schema(self, name):
        return self._specification['components']['schemas'][name]

    def get_schema_names(self) -> Iterable[str]:
        return self._specification['definitions'].keys()


class OpenAPISpecificationInterface(SpecificationInterface):
    SCHEMA_REFERENCE_PATTERN = r'#/components/schemas/([^/]+)'

    def get_schema(self, name):
        return self._specification['components']['schemas'][name]

    def get_schema_names(self) -> Iterable[str]:
        return self._specification['components']['schemas'].keys()


class JSONSchemaInterface(SpecificationInterface):
    SCHEMA_REFERENCE_PATTERN = r'#/definitions/([^/]+)'

    def get_schema(self, name):
        if name == 'RootObject':
            return self._specification
        return self._specification['definitions'][name]

    def get_schema_names(self) -> Iterable[str]:
        return set(self._specification['definitions'].keys()) | {'RootObject'}


specification_type_to_interface_class: Dict[str, Callable[[Dict], SpecificationInterface]] = {
    'openapi': OpenAPISpecificationInterface,
    'json_schema': JSONSchemaInterface
}


class SchemaBasedTypeInfo(object):
    def __init__(self, type_str, type_obj, required: bool, constructor=None):
        self.type_str = type_str
        self.type_obj = type_obj
        self.constructor = constructor or self.type_obj
        self.required = required

    def __repr__(self):
        return f'SchemaBasedTypeInfo<type={self.type_str}; required={self.required}>'


class SchemaBasedTypeInfoFactory(ABC):
    def __init__(self, type_builder: SchemaBasedTypeBuilder, schema, schema_name: Optional[str], required: bool):
        self.type_builder = type_builder
        self.schema = schema
        self.schema_name = schema_name
        self.required = required

    @abstractmethod
    def build_type(self) -> Optional[SchemaBasedTypeInfo]:
        pass

    def on_type_defined(self, built_type: SchemaBasedTypeInfo):
        pass

    def build_sub_type(self, sub_schema, required) -> SchemaBasedTypeInfo:
        return self.type_builder.build_and_define_type(
            schema=sub_schema,
            name=None,
            required=required,
        )


class DocumentError(Exception):
    pass


class RefTypeInfoFactory(SchemaBasedTypeInfoFactory):
    def build_type(self) -> Optional[SchemaBasedTypeInfo]:
        if isinstance(self.schema, dict) and '$ref' in self.schema:
            ref_string = self.schema['$ref']
            schema_name = self.type_builder.specification_interface.parse_schema_name(ref_string)
            if not self.type_builder.specification_interface.schema_exists(schema_name):
                raise DocumentError(f'unresolved schema reference: "{ref_string}"')
            referenced_type_info = self.type_builder.get_type(schema_name)
            return SchemaBasedTypeInfo(type_str=referenced_type_info.type_str,
                                       type_obj=referenced_type_info.type_obj,
                                       constructor=referenced_type_info.constructor,
                                       required=self.required)


# noinspection PyProtectedMember
class CustomTypeInfoFactory(SchemaBasedTypeInfoFactory):
    def build_type(self) -> Optional[SchemaBasedTypeInfo]:
        if (
            self.schema_name is not None
            and isinstance(self.schema, dict)
            and 'type' in self.schema
            and self.schema['type'] == 'object'
            and 'properties' in self.schema
        ):
            # noinspection PyTypeChecker
            new_class: Type[SchemaBasedObject] = type(self.schema_name, (SchemaBasedObject,), {})
            logging.debug(f'Created new class from schema "{self.schema_name}": {new_class}')

            if self.schema.get('additionalProperties', True) is False and 'patternProperties' not in self.schema:
                new_class._additional_properties_allowed = False

            def custom_class_constructor(properties_or_object):
                if isinstance(properties_or_object, new_class):
                    return properties_or_object
                else:
                    if not isinstance(properties_or_object, dict):
                        raise ValueError(
                            f'while trying to convert to the class "{new_class.__name__}", '
                            f'expected either a raw dict of properties, or an instance of the class itself, '
                            f'got {str(type(properties_or_object))} : {str(properties_or_object)}'
                        )
                    return new_class(**properties_or_object)

            return SchemaBasedTypeInfo(
                type_str=self.schema_name,
                type_obj=new_class,
                constructor=custom_class_constructor,
                required=True,
            )

    def on_type_defined(self, built_type: SchemaBasedTypeInfo):
        """ Add properties to custom class after defining the type, in order to prevent infinite recursion. """
        custom_class: Type[SchemaBasedObject] = built_type.type_obj

        custom_class._legal_property_name_to_original = {}
        custom_class._property_name_to_type = {}
        custom_class._additional_properties_type = try_build_additional_property_type(self.schema, self.type_builder)

        required_properties = self.schema.get('required', [])
        for property_name, property_schema in self.schema['properties'].items():
            legal_property_name = make_legal(property_name)
            custom_class._legal_property_name_to_original[legal_property_name] = property_name
            custom_class._property_name_to_type[property_name] = self.build_sub_type(
                sub_schema=property_schema,
                required=property_name in required_properties,
            )

            def property_getter(self_: SchemaBasedObject, bound_property_name=property_name):
                return self_._properties.get(bound_property_name, None)

            def property_setter(self_: SchemaBasedObject, value, bound_property_name=property_name):
                property_type = self_._property_name_to_type[bound_property_name]
                if not (value is None and not property_type.required or isinstance(value, property_type.type_obj)):
                    raise ValueError(f'expected type {str(property_type.type_obj)} '
                                     f'for property "{bound_property_name}"')
                self_._properties[bound_property_name] = value

            setattr(custom_class, legal_property_name, property(fget=property_getter, fset=property_setter))


class NoValidOneOfOptionException(Exception):
    pass


class OneOfTypeInfoFactory(SchemaBasedTypeInfoFactory):
    def build_type(self) -> Optional[SchemaBasedTypeInfo]:
        if isinstance(self.schema, dict) and 'oneOf' in self.schema:
            type_options: List[SchemaBasedTypeInfo] = [self.build_sub_type(sub_schema, required=True)
                                                       for sub_schema in self.schema['oneOf']]

            type_str = f"Union[{', '.join([option.type_str for option in type_options])}]"

            def constructor(raw_value):
                for option in sorted(type_options,
                                     key=lambda option: 0 if issubclass(option.type_obj, SchemaBasedObject) else 1):
                    if (
                        issubclass(option.type_obj, SchemaBasedObject) and isinstance(raw_value, dict)
                        or isinstance(raw_value, option.type_obj)
                    ):
                        try:
                            return option.constructor(raw_value)
                        except NoValidOneOfOptionException:
                            pass  # try another option
                raise NoValidOneOfOptionException("couldn't construct OneOf object from the given value")

            return SchemaBasedTypeInfo(
                type_str=type_str,
                type_obj=object,
                constructor=constructor,
                required=self.required,
            )


class ArrayTypeInfoFactory(SchemaBasedTypeInfoFactory):
    def build_type(self) -> Optional[SchemaBasedTypeInfo]:
        if isinstance(self.schema, dict) and 'type' in self.schema and self.schema['type'] == 'array':
            sub_type: SchemaBasedTypeInfo = self.build_sub_type(self.schema['items'], required=True)

            def array_constructor(raw_list):
                if not isinstance(raw_list, list):
                    raise ValueError(f'while converting a list of raw items to a list of typed items,'
                                     f'expected a list of items, got a {str(type(raw_list))}: {str(raw_list)}')
                return [sub_type.constructor(x) for x in raw_list]

            return SchemaBasedTypeInfo(type_str=f'List[{sub_type.type_str}]',
                                       type_obj=list,
                                       constructor=array_constructor,
                                       required=self.required)


def try_build_additional_property_type(schema, type_builder: SchemaBasedTypeBuilder) -> Optional[SchemaBasedTypeInfo]:
    if isinstance(schema, dict) and schema.get('type', None) == 'object':
        pattern_properties = schema.get('patternProperties', None)
        additional_properties = schema.get('additionalProperties', None)

        if isinstance(pattern_properties, dict):
            sub_schema = {'oneOf': list(schema['patternProperties'].values())}
        elif isinstance(additional_properties, dict):
            sub_schema = schema['additionalProperties']
        else:
            return
        return type_builder.build_and_define_type(sub_schema, required=True, name=None)


class DictTypeInfoFactory(SchemaBasedTypeInfoFactory):
    def build_type(self) -> Optional[SchemaBasedTypeInfo]:
        if isinstance(self.schema, dict) and self.schema.get('type', None) == 'object':
            sub_type = try_build_additional_property_type(self.schema, self.type_builder)
            if sub_type is not None:
                def constructor(raw_dict):
                    return {str(key): sub_type.constructor(value)
                            for key, value in raw_dict.items()}
                constructed_type = f'Dict[str, {sub_type.type_str}]'

                return SchemaBasedTypeInfo(type_str=constructed_type,
                                           type_obj=dict,
                                           constructor=constructor,
                                           required=self.required)


class SimpleTypeInfoFactory(SchemaBasedTypeInfoFactory):
    def build_type(self) -> Optional[SchemaBasedTypeInfo]:
        schema_type = self.schema.get('type', None)

        basic_openapi_type_strings = {
            'string': 'str',
            'integer': 'int',
            'number': 'float',
            'boolean': 'bool',
        }

        if schema_type == 'object':
            type_str = f'Dict[str, Any]'
            type_obj = dict
        elif schema_type is None:
            type_str = 'Any'
            type_obj = object
        elif schema_type not in basic_openapi_type_strings:
            raise DocumentError(f'invalid type "{schema_type}" in schema: {self.schema}')
        else:
            type_str = basic_openapi_type_strings[schema_type]
            type_obj = eval(type_str)

        return SchemaBasedTypeInfo(type_str=type_str,
                                   type_obj=type_obj,
                                   constructor=lambda raw_value: raw_value,
                                   required=self.required)


def make_legal(property_name) -> str:
    ill_character_map = {
        '$': 'dollar'
    }

    if re.match(r'\d.+', property_name):
        property_name = 'ILL_' + property_name
    if re.match(r'\W.+', property_name):
        property_name = ill_character_map.get(property_name[0], 'ILL') + '_' + property_name[1:]
    if re.match(r'.+\W', property_name):
        property_name = property_name[0:-1] + '_' + ill_character_map.get(property_name[0], 'ILL')
    property_name = re.sub(r'\W+', f"_{ill_character_map.get(property_name[0], 'ILL')}_", property_name)

    if property_name in keyword.kwlist:
        return f'{property_name}_'
    else:
        return property_name


class SchemaBasedTypeBuilder(object):
    def __init__(self, specification_path: str,
                 specification_type: str):
        with open(specification_path) as file:
            self.specification = yaml.safe_load(file)
        self.schema_name_to_type_info = {}
        self.specification_interface = specification_type_to_interface_class[specification_type](self.specification)
        self._type_info_factories: List[Type[SchemaBasedTypeInfoFactory]] = [
            RefTypeInfoFactory,
            CustomTypeInfoFactory,
            OneOfTypeInfoFactory,
            ArrayTypeInfoFactory,
            DictTypeInfoFactory,
            SimpleTypeInfoFactory,
        ]
        self._schemas_that_are_being_parsed = set()

    def get_all_types(self) -> Dict[str, SchemaBasedTypeInfo]:
        return {schema_name: self.get_type(schema_name).type_obj
                for schema_name in sorted(self.specification_interface.get_schema_names())}

    def get_type(self, schema_name) -> SchemaBasedTypeInfo:
        if schema_name not in self.schema_name_to_type_info:
            schema = self.specification_interface.get_schema(schema_name)
            self.build_and_define_type(schema=schema, name=schema_name, required=True)
        return self.schema_name_to_type_info[schema_name]

    def build_and_define_type(self, schema, name, required: bool) -> SchemaBasedTypeInfo:
        assert name is None or name not in self.schema_name_to_type_info, f'type with name {name} already defined'

        schema_identifier = hash((name, str(schema)))
        if schema_identifier in self._schemas_that_are_being_parsed:
            type_info_factory_classes = [SimpleTypeInfoFactory]
        else:
            self._schemas_that_are_being_parsed.add(schema_identifier)
            type_info_factory_classes = self._type_info_factories

        type_info = None

        for factory_class in type_info_factory_classes:
            factory = factory_class(
                type_builder=self,
                schema=schema,
                schema_name=name,
                required=required,
            )
            type_info: Optional[SchemaBasedTypeInfo] = factory.build_type()
            if type_info is not None:
                if name is not None:
                    self.schema_name_to_type_info[name] = type_info
                factory.on_type_defined(type_info)
                break
        assert type_info is not None
        if schema_identifier in self._schemas_that_are_being_parsed:
            self._schemas_that_are_being_parsed.remove(schema_identifier)
        return type_info


# noinspection PyProtectedMember
def gen_stub_text(specification_path: str, specification_type: str):
    stub_text = 'from __future__ import annotations\n' \
                'from typing import Any, Dict, List, Optional, Union\n\n' \
                'class SchemaBasedObject(object):\n' \
                '    def __init__(self, properties: Dict[str, Any]) -> None: ...\n' \
                '    def as_simple_dict(self) -> Dict[str, Any]: ...\n' \
                '    def get_all_properties(self) -> Dict[str, Any]: ...\n' \
                '    def get_additional_properties(self) -> Dict[str, Any]: ...\n\n'
    for type_name, dynamic_type_class in sorted(SchemaBasedTypeBuilder(specification_path,
                                                                       specification_type).get_all_types().items()):
        if isinstance(dynamic_type_class, type) and issubclass(dynamic_type_class, SchemaBasedObject):
            constructor_parameters = []
            stub_text += f'class {type_name}(SchemaBasedObject):\n'

            for property_name, property_type in dynamic_type_class._property_name_to_type.items():
                property_name = make_legal(property_name)
                type_string = property_type.type_str
                if not property_type.required:
                    type_string = f'Optional[{type_string}]'
                stub_text += f'    {property_name}: {type_string} = ...\n'

                parameter_string = f'{property_name}: {type_string}'
                if not property_type.required:
                    parameter_string += ' = None'
                constructor_parameters.append(parameter_string)

            constructor_parameters = sorted(
                constructor_parameters,
                key=lambda param_str: ('= None' in param_str, constructor_parameters.index(param_str)),
            )
            stub_text += '\n'
            stub_text += '    # noinspection PyMissingConstructor\n'

            kwargs_str = ', **kwargs' if dynamic_type_class._additional_properties_allowed else ''
            stub_text += f'    def __init__(self, {", ".join(constructor_parameters)}{kwargs_str}): ...\n\n'

            additional_properties_type = dynamic_type_class._additional_properties_type
            if additional_properties_type:
                stub_text += f'    def __getitem__(self, item) -> {additional_properties_type.type_str}: ...\n\n'
    return stub_text


def gen_module_text(relative_specification_path: str, specification_type: str):
    return f"from pathlib import Path\n\n"\
           f"import schema2type\n\n"\
           f"globals().update(schema2type.SchemaBasedTypeBuilder(\n"\
           f"    Path(__file__).parent.joinpath('{relative_specification_path}'),\n"\
           f"    '{specification_type}',\n"\
           f").get_all_types())\n"
