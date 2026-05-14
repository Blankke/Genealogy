"""
生成族谱管理系统演示 CSV 数据。

使用示例：
  python scripts/generate_demo_data.py --output data/generated
  python scripts/generate_demo_data.py --output data/generated --seed 20260507
  python scripts/generate_demo_data.py --output data/generated_small_200 --family-sizes 200

说明：
  - 默认生成 10 个族谱、105000 名成员，其中第 1 个族谱 52000 人。
  - 默认生成 30 代，每一代至少保留一对男女成员，避免断代。
  - 输出目录会生成 users、genealogies、members、parent_child_relations、marriages 等导入所需 CSV。
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
    "安",
    "承",
    "德",
    "明",
    "文",
    "修",
    "远",
    "嘉",
    "宁",
    "雅",
    "清",
    "思",
    "立",
    "恒",
]
DEFAULT_FAMILY_SIZES = [52000, 6000, 6000, 6000, 6000, 6000, 6000, 6000, 6000, 5000]
DEFAULT_GENERATION_COUNT = 30


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
    parser.add_argument(
        "--family-sizes",
        default=",".join(str(size) for size in DEFAULT_FAMILY_SIZES),
        help="族谱人数列表，使用逗号分隔，例如 200 或 52000,6000,6000",
    )
    parser.add_argument(
        "--generation-count",
        type=int,
        default=DEFAULT_GENERATION_COUNT,
        help="每个族谱的代数，默认 30",
    )
    return parser.parse_args()


def write_csv(path: Path, headers: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def iso_now() -> str:
    return datetime.now(UTC).isoformat()


def parse_family_sizes(raw_value: str) -> list[int]:
    """解析命令行中的族谱人数列表。"""

    family_sizes: list[int] = []
    for item in raw_value.split(","):
        stripped_item = item.strip()
        if not stripped_item:
            continue

        family_size = int(stripped_item)
        if family_size < 2:
            raise ValueError("每个族谱的人数至少为 2，才能生成首代配偶关系")
        family_sizes.append(family_size)

    if not family_sizes:
        raise ValueError("至少需要提供一个有效的族谱人数")
    return family_sizes


def generation_sizes(total_members: int, generation_count: int) -> list[int]:
    """按代际平均分配成员，并保证每代至少 2 人。"""

    minimum_members = generation_count * 2
    if total_members < minimum_members:
        raise ValueError(
            f"总人数 {total_members} 不足以支撑 {generation_count} 代。"
            f"当前规则要求至少 {minimum_members} 人。"
        )

    sizes = [2] * generation_count
    remaining = total_members - minimum_members
    for index in range(remaining):
        # 首代固定保留 2 人，剩余人数从第二代开始均匀分摊。
        sizes[1 + (index % (generation_count - 1))] += 1
    return sizes


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


def generate_users() -> list[dict[str, object]]:
    password_hash = password_context.hash("Genealogy@123")
    admin_password_hash = password_context.hash("Admin@123")
    created_at = iso_now()
    users = [
        {
            "id": user_id,
            "username": f"user{user_id:02d}",
            "email": f"user{user_id:02d}@example.com",
            "password_hash": password_hash,
            "is_admin": "false",
            "created_at": created_at,
        }
        for user_id in range(1, 21)
    ]
    users.append(
        {
            "id": 21,
            "username": "admin",
            "email": "admin@example.com",
            "password_hash": admin_password_hash,
            "is_admin": "true",
            "created_at": created_at,
        }
    )
    return users


def generate_all_data(
    rng: random.Random,
    family_sizes: list[int],
    generation_count: int,
) -> dict[str, list[dict[str, object]]]:
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

    for genealogy_id, family_size in enumerate(tqdm(family_sizes, desc="生成族谱"), start=1):
        surname = SURNAMES[(genealogy_id - 1) % len(SURNAMES)]
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
        generation_member_sizes = generation_sizes(family_size, generation_count)

        for generation_index, generation_size in enumerate(
            tqdm(
                generation_member_sizes,
                desc=f"{surname}氏生成 {generation_count} 代",
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
                        "biography": (
                            f"{surname}氏第 {generation_index} 代成员，"
                            f"演示数据编号 {member_id}。"
                        ),
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
                fathers = [member for member in previous_generation if member.gender == "male"]
                mothers = [member for member in previous_generation if member.gender == "female"]

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

                males = [member for member in current_generation if member.gender == "male"]
                females = [member for member in current_generation if member.gender == "female"]
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
    family_sizes = parse_family_sizes(args.family_sizes)
    data = generate_all_data(rng, family_sizes, args.generation_count)

    headers = {
        "users": ["id", "username", "email", "password_hash", "is_admin", "created_at"],
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
    print("管理员账号：admin@example.com / Admin@123")


if __name__ == "__main__":
    main()
