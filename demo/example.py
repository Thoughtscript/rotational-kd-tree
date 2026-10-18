from dataclasses import dataclass
from math import acos, atan2, cos, pi, sin, sqrt
from typing import Iterable, Iterator

import numpy as np
from scipy.spatial import KDTree
from scipy.spatial.transform import Rotation

CHARACTER_VALUES = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ .")
PARAGRAPH = (
    "THE QUERY STAYS FIXED. THE A TO Z DATASET STAYS FIXED. "
    "ONLY THE SPHERICAL ROTATION KEY CHANGES."
)
WORD_SENTENCE = (
    "ROTATIONAL KEYS LET ONE FIXED QUERY RETRIEVE WORDS FROM A STATIC DATASET "
    "AND ASSEMBLE SENTENCES."
)
WORD_SEQUENCE = tuple(WORD_SENTENCE.split())
WORD_VALUES = tuple(sorted(set(WORD_SEQUENCE)))
FIXED_QUERY = (0.0, 0.0, 1.0)


@dataclass(frozen=True)
class RotationKey:
    """A rotation encoded as angle, axis azimuth, and axis inclination."""

    angle: float
    azimuth: float
    inclination: float

    @classmethod
    def from_rotation(cls, rotation: Rotation) -> "RotationKey":
        rotation_vector = rotation.as_rotvec()
        angle = float(np.linalg.norm(rotation_vector))
        if angle == 0.0:
            return cls(0.0, 0.0, 0.0)
        return cls(
            angle,
            atan2(float(rotation_vector[1]), float(rotation_vector[0])),
            acos(
                max(
                    -1.0,
                    min(1.0, float(rotation_vector[2]) / angle),
                )
            ),
        )

    def to_rotation(self) -> Rotation:
        sin_inclination = sin(self.inclination)
        rotation_vector = self.angle * np.asarray(
            (
                sin_inclination * cos(self.azimuth),
                sin_inclination * sin(self.azimuth),
                cos(self.inclination),
            )
        )
        return Rotation.from_rotvec(rotation_vector)


@dataclass
class RotationNode:
    key: RotationKey
    next: "RotationNode | None" = None


class RotationPath:
    def __init__(self) -> None:
        self.head: RotationNode | None = None
        self.tail: RotationNode | None = None
        self._length = 0

    def append(self, key: RotationKey) -> RotationNode:
        node = RotationNode(key)
        if self.tail is None:
            self.head = node
        else:
            self.tail.next = node
        self.tail = node
        self._length += 1
        return node

    def __len__(self) -> int:
        return self._length

    def __iter__(self) -> Iterator[RotationNode]:
        node = self.head
        while node is not None:
            yield node
            node = node.next


@dataclass(frozen=True)
class FixedDataset:
    values: tuple[str, ...]
    points: np.ndarray
    tree: KDTree
    invariant_query: tuple[float, float, float]
    value_indices: dict[str, int]

    @property
    def query_vector(self) -> np.ndarray:
        return np.asarray(self.invariant_query)


def fibonacci_sphere(count: int) -> np.ndarray:
    if count < 1:
        raise ValueError("A dataset must contain at least one value")

    points = []
    golden_angle = pi * (3.0 - sqrt(5.0))
    for index in range(count):
        z = 1.0 - 2.0 * (index + 0.5) / count
        radius = sqrt(1.0 - z * z)
        azimuth = golden_angle * index
        points.append((radius * cos(azimuth), radius * sin(azimuth), z))
    return np.asarray(points)


def build_fixed_dataset(
    values: Iterable[str],
    invariant_query: tuple[float, float, float] = FIXED_QUERY,
) -> FixedDataset:
    ordered_values = tuple(values)
    if not ordered_values:
        raise ValueError("A dataset must contain at least one value")
    if len(set(ordered_values)) != len(ordered_values):
        raise ValueError("Dataset values must be unique")
    if len(invariant_query) != 3 or not np.isfinite(invariant_query).all():
        raise ValueError("The invariant query must be a finite 3D coordinate")
    if np.linalg.norm(invariant_query) == 0.0:
        raise ValueError("The invariant query must be nonzero")

    points = fibonacci_sphere(len(ordered_values))
    points.setflags(write=False)
    tree = KDTree(points, copy_data=True)
    tree.data.setflags(write=False)
    return FixedDataset(
        ordered_values,
        points,
        tree,
        invariant_query,
        {value: index for index, value in enumerate(ordered_values)},
    )


def rotation_key_for_index(dataset: FixedDataset, index: int) -> RotationKey:
    rotation, _ = Rotation.align_vectors(
        [dataset.query_vector], [dataset.points[index]]
    )
    return RotationKey.from_rotation(rotation)


def build_rotation_key_table(dataset: FixedDataset) -> dict[str, RotationKey]:
    """Precompute the spherical orientation ("hash") for each dataset value."""
    return {
        value: rotation_key_for_index(dataset, index)
        for index, value in enumerate(dataset.values)
    }


def encode_values(
    values: Iterable[str],
    dataset: FixedDataset,
    key_table: dict[str, RotationKey] | None = None,
) -> RotationPath:
    path = RotationPath()
    for value in values:
        try:
            index = dataset.value_indices[value]
        except KeyError as error:
            raise ValueError(
                f"Value {value!r} is not in the fixed dataset"
            ) from error

        if key_table is None:
            key = rotation_key_for_index(dataset, index)
        else:
            try:
                key = key_table[value]
            except KeyError as error:
                raise ValueError(
                    f"No precomputed rotation key exists for {value!r}"
                ) from error
        path.append(key)
    return path


def query_value(
    key: RotationKey, dataset: FixedDataset
) -> tuple[str, float]:
    rotation = key.to_rotation()
    # This is equivalent to rotating the dataset while leaving its query fixed.
    # The indexed points and the world-space query are never mutated.
    query_in_dataset_frame = rotation.inv().apply(dataset.query_vector)
    distance, index = dataset.tree.query(query_in_dataset_frame)
    return dataset.values[int(index)], float(distance)


def decode_values(path: RotationPath, dataset: FixedDataset) -> tuple[str, ...]:
    return tuple(query_value(node.key, dataset)[0] for node in path)


def main() -> None:
    character_dataset = build_fixed_dataset(CHARACTER_VALUES)
    character_keys = build_rotation_key_table(character_dataset)
    word_dataset = build_fixed_dataset(WORD_VALUES)
    word_keys = build_rotation_key_table(word_dataset)

    character_path = encode_values(PARAGRAPH, character_dataset, character_keys)
    decoded_characters = "".join(decode_values(character_path, character_dataset))
    word_path = encode_values(WORD_SEQUENCE, word_dataset, word_keys)
    decoded_words = " ".join(decode_values(word_path, word_dataset))

    if decoded_characters != PARAGRAPH or decoded_words != WORD_SENTENCE:
        raise RuntimeError("A decoded message differs from its original")

    print("One invariant world-space query:", FIXED_QUERY)
    print(
        f"Character dataset: {len(character_dataset.values)} fixed values "
        "(A-Z, space, period)."
    )
    print(f"Word dataset: {len(word_dataset.values)} distinct fixed words.")
    print(
        "Each linked-list node stores the spherical rotation key "
        "(angle, axis azimuth, axis inclination)."
    )
    print("The underlying datasets and query remain unchanged.")
    for character, node in zip(PARAGRAPH, character_path):
        key = node.key
        print(
            f"{character!r}: angle={key.angle:.9f}, "
            f"axis_azimuth={key.azimuth:.9f}, "
            f"axis_inclination={key.inclination:.9f}"
        )
    print(f"Character sequence: {decoded_characters}")
    print(f"Word sequence: {decoded_words}")


if __name__ == "__main__":
    main()
