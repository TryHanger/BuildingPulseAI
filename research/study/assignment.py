"""Generate and check coordinator-only assignments for future review."""
import argparse
from collections import Counter
from itertools import permutations
import json
import random


def allocate(seed, blocks):
    rng = random.Random(seed)
    for block in range(1, blocks + 1):
        orders = list(permutations("ABC"))
        rng.shuffle(orders)
        triplets = [rng.sample(list(group), 3) for group in (("T01", "T02", "T03"), ("T04", "T05", "T06"))]
        for slot_id, order in enumerate(orders, 1):
            visits = []
            for index, arm in enumerate(order):
                for case in rng.sample([group[index] for group in triplets], 2):
                    visits.append({"case_id": case, "condition": arm})
            yield {"participant_id": f"B{block:02d}-S{slot_id}", "visits": visits}


def verify():
    expected = Counter({(f"T{case:02d}", arm): 2 for case in range(1, 7) for arm in "ABC"})
    positions = {f"T{case:02d}": set() for case in range(1, 7)}
    for seed in range(1000):
        first, second = [list(allocate(seed, 2)) for _ in range(2)]
        assert first == second
        for begin in (0, 6):
            block = first[begin:begin + 6]
            assert len({tuple(item["condition"] for item in row["visits"][::2]) for row in block}) == 6
            visits = Counter((visit["case_id"], visit["condition"]) for row in block for visit in row["visits"])
            assert visits == expected
            for row in block:
                assert len({item["case_id"] for item in row["visits"]}) == 6
                assert Counter(item["condition"] for item in row["visits"]) == dict.fromkeys("ABC", 2)
                for index, visit in enumerate(row["visits"]):
                    positions[visit["case_id"]].add(index)
    assert all(len(indexes) == 6 for indexes in positions.values())
    print("PASS 1000 seeds, 2 blocks each, six orders, task-by-arm balance and positions")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--blocks", type=int, default=2)
    args = parser.parse_args()
    if args.blocks < 1:
        parser.error("blocks must be positive")
    if args.seed is None:
        verify()
    else:
        print(json.dumps(list(allocate(args.seed, args.blocks)), indent=2))
