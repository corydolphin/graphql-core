import re

from typing import Pattern

from graphql.utilities import get_introspection_query


class ExcpectIntrospectionQuery:
    def __init__(self, **options):
        self.query = get_introspection_query(**options)

    def to_match(self, name: str, times: int = 1) -> None:
        pattern = self.to_reg_exp(name)
        assert len(pattern.findall(self.query)) == times

    def to_not_match(self, name: str) -> None:
        pattern = self.to_reg_exp(name)
        assert not pattern.search(self.query)

    @staticmethod
    def to_reg_exp(name: str) -> Pattern:
        return re.compile(fr"\b{name}\b")


def describe_get_introspection_query():
    def skips_all_description_fields():
        ExcpectIntrospectionQuery().to_match("description", 5)
        ExcpectIntrospectionQuery(descriptions=True).to_match("description", 5)
        ExcpectIntrospectionQuery(descriptions=False).to_not_match("description")

    def includes_is_repeatable_field_on_directives():
        ExcpectIntrospectionQuery().to_not_match("isRepeatable")
        ExcpectIntrospectionQuery(directive_is_repeatable=True).to_match("isRepeatable")
        ExcpectIntrospectionQuery(directive_is_repeatable=False).to_not_match(
            "isRepeatable"
        )

    def includes_description_field_on_schema():
        ExcpectIntrospectionQuery().to_match("description", 5)
        ExcpectIntrospectionQuery(schema_description=False).to_match("description", 5)
        ExcpectIntrospectionQuery(schema_description=True).to_match("description", 6)
        ExcpectIntrospectionQuery(
            descriptions=False, schema_description=True
        ).to_not_match("description")

    def includes_specified_by_url_field():
        ExcpectIntrospectionQuery().to_not_match("specifiedByUrl")
        ExcpectIntrospectionQuery(specified_by_url=True).to_match("specifiedByUrl")
        ExcpectIntrospectionQuery(specified_by_url=False).to_not_match("specifiedByUrl")

    def includes_is_deprecated_field_on_input_values():
        ExcpectIntrospectionQuery().to_match("isDeprecated", 2)
        ExcpectIntrospectionQuery(input_value_deprecation=True).to_match(
            "isDeprecated", 3
        )
        ExcpectIntrospectionQuery(input_value_deprecation=False).to_match(
            "isDeprecated", 2
        )

    def includes_deprecation_reason_field_on_input_values():
        ExcpectIntrospectionQuery().to_match("deprecationReason", 2)
        ExcpectIntrospectionQuery(input_value_deprecation=True).to_match(
            "deprecationReason", 3
        )
        ExcpectIntrospectionQuery(input_value_deprecation=False).to_match(
            "deprecationReason", 2
        )

    def includes_deprecated_input_field_and_args():
        ExcpectIntrospectionQuery().to_match("includeDeprecated: true", 2)
        ExcpectIntrospectionQuery(input_value_deprecation=True).to_match(
            "includeDeprecated: true", 5
        )
        ExcpectIntrospectionQuery(input_value_deprecation=False).to_match(
            "includeDeprecated: true", 2
        )
