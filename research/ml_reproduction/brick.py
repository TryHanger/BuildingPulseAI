"""Derive target neighborhoods from the original BRICK RDF graph, Algorithm 1."""
from collections import defaultdict

import rdflib
from rdflib.namespace import RDF

SUFFIXES = ("_TEMP", "_MAT", "_DAT", "_RAT", "_EWT", "_RWT")


def tail(term):
    return str(term).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def derive(path, columns):
    graph = rdflib.Graph().parse(path, format="turtle")
    types = defaultdict(set)
    points, parts = defaultdict(set), defaultdict(set)
    inverse = {"isPointOf": "hasPoint", "isPartOf": "hasPart", "isFedBy": "feeds"}
    column_set = set(columns)
    for a, predicate, b in graph:
        if predicate == RDF.type:
            types[a].add(tail(b))
        relation = tail(predicate)
        if relation in inverse:
            a, b, relation = b, a, inverse[relation]
        if relation == "hasPoint" and tail(b) in column_set:
            points[a].add(b)
        if relation == "hasPart":
            parts[a].add(b)
    equipment = {owner: points[owner] | set().union(*(points[child] for child in parts[owner]))
                 for owner in set(points) | set(parts)}
    all_points = {tail(point) for neighborhood in equipment.values() for point in neighborhood}
    targets = {
        tail(point) for neighborhood in equipment.values() for point in neighborhood
        if any("Temperature" in kind and "Setpoint" not in kind and "Outside" not in kind for kind in types[point])
    }
    result = {target: sorted(all_points - {target}) for target in sorted(targets) if len(all_points - {target}) >= 3}
    if result:
        return result, "BRICK_GRAPH"
    fallback = {name: sorted(column_set - {name}) for name in columns
                if name.endswith(SUFFIXES) and "SPT" not in name and "_OA" not in name}
    return fallback, "ALGORITHM_1_FALLBACK"
