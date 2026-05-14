from app.main import SQL_QUERY_DEFINITIONS, find_shortest_relationship_path


def test_find_shortest_relationship_path_returns_minimum_hops() -> None:
    graph = {
        1: [(2, "parent_child"), (4, "marriage")],
        2: [(1, "child_parent"), (3, "parent_child")],
        3: [(2, "child_parent"), (4, "marriage")],
        4: [(1, "marriage"), (3, "marriage")],
    }

    path = find_shortest_relationship_path(graph, 1, 3)

    assert path == ([1, 2, 3], ["parent_child", "parent_child"])


def test_find_shortest_relationship_path_returns_none_when_disconnected() -> None:
    graph = {
        1: [(2, "parent_child")],
        2: [(1, "child_parent")],
        3: [(4, "marriage")],
        4: [(3, "marriage")],
    }

    path = find_shortest_relationship_path(graph, 1, 4)

    assert path is None


def test_sql_templates_do_not_use_sqlalchemy_unsafe_cast_syntax() -> None:
    for definition in SQL_QUERY_DEFINITIONS.values():
        assert ":member_id::BIGINT" not in definition["sql"]
        assert ":genealogy_id::BIGINT" not in definition["sql"]
