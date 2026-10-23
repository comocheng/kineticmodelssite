import re

from django import forms


# Statements that are allowed (read-only + EXPLAIN)
_ALLOWED_STARTERS = re.compile(
    r"^\s*(SELECT|WITH|EXPLAIN)\b",
    re.IGNORECASE,
)

# Strip SQL line comments (-- ...) and block comments (/* ... */) before validation
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)

# Keywords that must never appear anywhere in the query
_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|ALTER|DROP|CREATE|TRUNCATE|GRANT|REVOKE|COPY"
    r"|VACUUM|ANALYZE|BEGIN|COMMIT|ROLLBACK|SAVEPOINT|EXECUTE|CALL|DO)\b",
    re.IGNORECASE,
)


class QueryForm(forms.Form):
    sql = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control font-monospace",
                "rows": 8,
                "placeholder": "SELECT * FROM database_kineticmodel LIMIT 10;",
                "spellcheck": "false",
                "autocomplete": "off",
            }
        ),
        label="SQL Query",
        strip=True,
    )
    row_limit = forms.IntegerField(
        min_value=1,
        max_value=1000,
        initial=100,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "style": "width:120px"}),
        label="Row limit",
    )

    def clean_sql(self):
        sql = self.cleaned_data["sql"].strip()

        # Strip trailing semicolons and check for multiple statements
        stripped = sql.rstrip(";").strip()
        if ";" in stripped:
            raise forms.ValidationError(
                "Only a single SQL statement is allowed. Remove all semicolons except the optional trailing one."
            )

        # Remove comments before checking the allowed-starters rule so that
        # queries that begin with -- commentary are not incorrectly rejected.
        sql_no_comments = _BLOCK_COMMENT.sub("", stripped)
        sql_no_comments = re.sub(r"--[^\n]*", "", sql_no_comments).strip()

        if not _ALLOWED_STARTERS.match(sql_no_comments):
            raise forms.ValidationError(
                "Only SELECT, WITH … SELECT, and EXPLAIN queries are permitted."
            )

        if _FORBIDDEN_KEYWORDS.search(sql):
            raise forms.ValidationError(
                "The query contains a forbidden keyword. Only read-only statements are allowed."
            )

        return stripped

    def clean_row_limit(self):
        limit = self.cleaned_data.get("row_limit")
        return limit if limit is not None else 100
