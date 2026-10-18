"""Application-owned editing capabilities shared by planning and evidence review."""

EDITABLE_SUFFIXES = frozenset(
    {
        ".py",
        ".sql",
        ".md",
        ".rst",
        ".txt",
        ".toml",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".html",
        ".css",
        ".json",
        ".yaml",
        ".yml",
    }
)


def execution_capabilities():
    return {
        "origin": "application_configuration_not_user_requirements",
        "editable_extensions": sorted(EDITABLE_SUFFIXES),
        "test_runners": ["pytest", "unittest"],
        "frontend_test_execution": False,
        "dependency_installation": False,
        "database_migration_execution": False,
    }
