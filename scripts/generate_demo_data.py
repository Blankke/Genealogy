"""
生成族谱管理系统演示 CSV 数据。

使用示例：
  python scripts/generate_demo_data.py --output data/generated
  python scripts/generate_demo_data.py --output data/generated --seed 20260507

说明：
  - 默认生成 10 个族谱、105000 名成员，其中第 1 个族谱 52000 人。
  - 每个族谱默认生成 30 代，成员至少通过亲子或婚姻关系连接到另一名成员。
  - 输出 CSV 不建议提交 Git，仓库已通过 .gitignore 忽略 data/generated/。
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
import random

from passlib.context import CryptContext
from tqdm import tqdm

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SURNAMES = ["陈", "林", "王", "李", "张", "刘", "赵", "黄", "周", "吴"]
NAME_PARTS = [
    "承",
    "文",
    "思",
    "明",
    "德",
    "修",
    "远",
    "安",
    "宁",
    "雅",
    "清",
    "恒",
    "嘉",
    "立",
]
DEFAULT_FAMILY_SIZES = [52000, 6000, 6000, 6000, 6000, 6000, 6000, 6000, 6000, 5000]


@dataclass(frozen=True)
class MemberSeed:
    id: int
    genealogy_id: int
    gender: str
    generation_index: int
    birth_date: date


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成族谱管理系统演示 CSV 数据")
    parser.add_argument("--output", default="data/generated", help="CSV 输出目录")
    parser.add_argument("--seed", type=int, default=20260507, help="随机种子")
    return parser.parse_args()


def write_csv(path: Path, headers: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def iso_now() -> str:
    return datetime.now(UTC).isoformat()


def make_name(surname: str, generation_index: int, member_id: int) -> str:
    first = NAME_PARTS[generation_index % len(NAME_PARTS)]
    second = NAME_PARTS[member_id % len(NAME_PARTS)]
    return f"{surname}{first}{second}"


def make_birth_date(start_year: int, generation_index: int, rng: random.Random) -> date:
    year = start_year + (generation_index - 1) * 27 + rng.randint(-3, 3)
    return date(year, rng.randint(1, 12), rng.randint(1, 28))


def make_death_date(birth: date, rng: random.Random) -> str:
    lifespan = rng.randint(50, 92)
    death_year = birth.year + lifespan
    if death_year >= 2026:
        return ""
    return date(death_year, birth.month, birth.day).isoformat()


def generation_sizes(total_members: int, generation_count: int) -> list[int]:
    sizes = [2]
    remaining = total_members - 2
    base = remaining // (generation_count - 1)
    extra = remaining % (generation_count - 1)
    for generation_offset in range(generation_count - 1):
        sizes.append(base + (1 if generation_offset < extra else 0))
    return sizes


def generate_users() -> list[dict[str, object]]:
    password_hash = password_context.hash("Genealogy@123")
    created_at = iso_now()
    return [
        {
            "id": user_id,
            "username": f"user{user_id:02d}",
            "email": f"user{user_id:02d}@example.com",
            "password_hash": password_hash,
            "created_at": created_at,
        }
        for user_id in range(1, 21)
    ]


def generate_all_data(rng: random.Random) -> dict[str, list[dict[str, object]]]:
    users = generate_users()
    genealogies: list[dict[str, object]] = []
    collaborators: list[dict[str, object]] = []
    members: list[dict[str, object]] = []
    parent_child_relations: list[dict[str, object]] = []
    marriages: list[dict[str, object]] = []

    member_id = 1
    relation_id = 1
    marriage_id = 1
    collaborator_id = 1
    now = iso_now()

    for genealogy_id, family_size in enumerate(
        tqdm(DEFAULT_FAMILY_SIZES, desc="生成族谱"), start=1
    ):
        surname = SURNAMES[genealogy_id - 1]
        owner_user_id = ((genealogy_id - 1) % len(users)) + 1
        genealogies.append(
            {
                "id": genealogy_id,
                "name": f"{surname}氏族谱",
                "surname": surname,
                "revision_time": date(2026, 5, 7).isoformat(),
                "owner_user_id": owner_user_id,
                "created_at": now,
            }
        )

        invited_user_id = (owner_user_id % len(users)) + 1
        collaborators.append(
            {
                "id": collaborator_id,
                "genealogy_id": genealogy_id,
                "user_id": invited_user_id,
                "role": "editor",
                "invited_at": now,
            }
        )
        collaborator_id += 1

        previous_generation: list[MemberSeed] = []
        start_year = 1210 + genealogy_id * 6
        for generation_index, generation_size in enumerate(
            tqdm(
                generation_sizes(family_size, 30),
                desc=f"{surname}氏生成 30 代",
                leave=False,
            ),
            start=1,
        ):
            current_generation: list[MemberSeed] = []
            for offset in range(generation_size):
                gender = "male" if offset % 2 == 0 else "female"
                birth = make_birth_date(start_year, generation_index, rng)
                current_generation.append(
                    MemberSeed(
                        id=member_id,
                        genealogy_id=genealogy_id,
                        gender=gender,
                        generation_index=generation_index,
                        birth_date=birth,
                    )
                )
                members.append(
                    {
                        "id": member_id,
                        "genealogy_id": genealogy_id,
                        "name": make_name(surname, generation_index, member_id),
                        "gender": gender,
                        "birth_date": birth.isoformat(),
                        "death_date": make_death_date(birth, rng),
                        "generation_index": generation_index,
                        "biography": f"{surname}氏第 {generation_index} 代成员，演示数据编号 {member_id}。",
                        "created_at": now,
                    }
                )
                member_id += 1

            if generation_index == 1:
                marriages.append(
                    {
                        "id": marriage_id,
                        "genealogy_id": genealogy_id,
                        "spouse_a_id": current_generation[0].id,
                        "spouse_b_id": current_generation[1].id,
                        "start_date": "",
                        "end_date": "",
                        "status": "active",
                        "created_at": now,
                    }
                )
                marriage_id += 1
            else:
                fathers = [
                    member for member in previous_generation if member.gender == "male"
                ]
                mothers = [
                    member
                    for member in previous_generation
                    if member.gender == "female"
                ]
                for child in current_generation:
                    father = rng.choice(fathers)
                    mother = rng.choice(mothers)
                    for parent, role in [(father, "father"), (mother, "mother")]:
                        parent_child_relations.append(
                            {
                                "id": relation_id,
                                "genealogy_id": genealogy_id,
                                "parent_id": parent.id,
                                "child_id": child.id,
                                "parent_role": role,
                                "created_at": now,
                            }
                        )
                        relation_id += 1

                males = [
                    member for member in current_generation if member.gender == "male"
                ]
                females = [
                    member for member in current_generation if member.gender == "female"
                ]
                pair_count = min(len(males), len(females)) // 3
                for pair_index in range(pair_count):
                    marriages.append(
                        {
                            "id": marriage_id,
                            "genealogy_id": genealogy_id,
                            "spouse_a_id": males[pair_index].id,
                            "spouse_b_id": females[pair_index].id,
                            "start_date": "",
                            "end_date": "",
                            "status": "active",
                            "created_at": now,
                        }
                    )
                    marriage_id += 1

            previous_generation = current_generation

    return {
        "users": users,
        "genealogies": genealogies,
        "genealogy_collaborators": collaborators,
        "members": members,
        "parent_child_relations": parent_child_relations,
        "marriages": marriages,
    }


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    output = Path(args.output)
    data = generate_all_data(rng)

    headers = {
        "users": ["id", "username", "email", "password_hash", "created_at"],
        "genealogies": [
            "id",
            "name",
            "surname",
            "revision_time",
            "owner_user_id",
            "created_at",
        ],
        "genealogy_collaborators": [
            "id",
            "genealogy_id",
            "user_id",
            "role",
            "invited_at",
        ],
        "members": [
            "id",
            "genealogy_id",
            "name",
            "gender",
            "birth_date",
            "death_date",
            "generation_index",
            "biography",
            "created_at",
        ],
        "parent_child_relations": [
            "id",
            "genealogy_id",
            "parent_id",
            "child_id",
            "parent_role",
            "created_at",
        ],
        "marriages": [
            "id",
            "genealogy_id",
            "spouse_a_id",
            "spouse_b_id",
            "start_date",
            "end_date",
            "status",
            "created_at",
        ],
    }

    for table_name, rows in tqdm(data.items(), desc="写入 CSV"):
        write_csv(output / f"{table_name}.csv", headers[table_name], rows)

    print(f"已生成数据目录：{output.resolve()}")
    print(f"成员总数：{len(data['members'])}")
    print("演示账号：user01@example.com / Genealogy@123")


if __name__ == "__main__":
    main()
