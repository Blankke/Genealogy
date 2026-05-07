"""
校验生成的族谱 CSV 数据是否满足需求。

使用示例：
  python scripts/validate_generated_data.py --input data/generated

说明：
  - 校验族谱数量、成员总量、最大族谱规模、最大代数。
  - 校验所有成员至少参与一个亲子或婚姻关系。
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from tqdm import tqdm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="校验族谱 CSV 数据")
    parser.add_argument("--input", default="data/generated", help="CSV 输入目录")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input)

    genealogies = read_csv(input_dir / "genealogies.csv")
    members = read_csv(input_dir / "members.csv")
    parent_child = read_csv(input_dir / "parent_child_relations.csv")
    marriages = read_csv(input_dir / "marriages.csv")

    family_counts = Counter(
        member["genealogy_id"] for member in tqdm(members, desc="统计族谱规模")
    )
    generation_counts = Counter(
        (member["genealogy_id"], member["generation_index"])
        for member in tqdm(members, desc="统计代数")
    )

    related_member_ids: set[str] = set()
    for relation in tqdm(parent_child, desc="检查亲子关系"):
        related_member_ids.add(relation["parent_id"])
        related_member_ids.add(relation["child_id"])
    for marriage in tqdm(marriages, desc="检查婚姻关系"):
        related_member_ids.add(marriage["spouse_a_id"])
        related_member_ids.add(marriage["spouse_b_id"])

    isolated_count = sum(
        1 for member in members if member["id"] not in related_member_ids
    )
    max_family_size = max(family_counts.values())
    max_generation_count = max(
        len(
            {
                generation
                for gid, generation in generation_counts
                if gid == genealogy["id"]
            }
        )
        for genealogy in genealogies
    )

    checks = {
        "族谱数量不少于 10": len(genealogies) >= 10,
        "成员总数不少于 100000": len(members) >= 100000,
        "至少一个族谱不少于 50000 人": max_family_size >= 50000,
        "至少一个族谱不少于 30 代": max_generation_count >= 30,
        "没有孤立成员": isolated_count == 0,
    }

    for label, ok in checks.items():
        print(f"{'通过' if ok else '失败'}：{label}")

    if not all(checks.values()):
        raise SystemExit("数据校验失败，请重新生成或检查脚本。")


if __name__ == "__main__":
    main()
