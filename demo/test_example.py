import logging
import sys
import unittest

import numpy as np

from example import (
    CHARACTER_VALUES,
    FIXED_QUERY,
    PARAGRAPH,
    RotationKey,
    WORD_SENTENCE,
    WORD_SEQUENCE,
    WORD_VALUES,
    build_fixed_dataset,
    build_rotation_key_table,
    decode_values,
    encode_values,
    query_value,
)
from perf_test import build_uniform_grid, query_uniform_grid
from scipy.spatial.transform import Rotation

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
logger.addHandler(handler)


class FixedQueryRotationTests(unittest.TestCase):
    def setUp(self):
        self.dataset = build_fixed_dataset(CHARACTER_VALUES)
        self.keys = build_rotation_key_table(self.dataset)
        self.original_points = self.dataset.points.copy()
        self.original_tree_data = self.dataset.tree.data.copy()

    def test_same_invariant_query_retrieves_different_values_for_different_keys(self):
        first_key = self.keys["A"]
        second_key = self.keys["B"]

        first_value, first_distance = query_value(first_key, self.dataset)
        second_value, second_distance = query_value(second_key, self.dataset)

        self.assertEqual(first_value, "A")
        self.assertEqual(second_value, "B")
        self.assertNotEqual(first_value, second_value)
        self.assertLess(first_distance, 1e-12)
        self.assertLess(second_distance, 1e-12)
        self.assertEqual(self.dataset.invariant_query, FIXED_QUERY)
        logger.info(
            "The same invariant query retrieved %r then %r using different rotation keys.",
            first_value,
            second_value,
        )

    def test_dataset_contains_alphabet_space_and_period(self):
        self.assertEqual(self.dataset.values, CHARACTER_VALUES)
        self.assertEqual(len(self.dataset.points), 28)
        logger.info("Verified fixed A-Z, space, and period dataset has 28 points.")

    def test_distinct_rotation_keys_can_pin_the_same_value(self):
        rotation = self.keys["A"].to_rotation()
        spin_about_query = Rotation.from_rotvec(self.dataset.query_vector * 0.7)
        alternate_key = RotationKey.from_rotation(
            spin_about_query * rotation
        )
        self.assertNotEqual(self.keys["A"], alternate_key)
        retrieved, _ = query_value(alternate_key, self.dataset)
        self.assertEqual(retrieved, "A")
        logger.info("Verified another spherical orientation key pins the same letter.")

    def test_character_paragraph_round_trips_through_linked_rotation_keys(self):
        path = encode_values(PARAGRAPH, self.dataset, self.keys)
        decoded = "".join(decode_values(path, self.dataset))

        self.assertEqual(decoded, PARAGRAPH)
        self.assertEqual(len(path), len(PARAGRAPH))
        self.assertTrue(all(hasattr(node, "key") for node in path))
        logger.info(
            "Round-tripped %d characters through spherical rotation keys.",
            len(path),
        )

    def test_word_phrase_round_trips_against_its_fixed_word_dataset(self):
        dataset = build_fixed_dataset(WORD_VALUES)
        keys = build_rotation_key_table(dataset)
        path = encode_values(WORD_SEQUENCE, dataset, keys)

        decoded_words = decode_values(path, dataset)
        self.assertEqual(decoded_words, WORD_SEQUENCE)
        self.assertEqual(" ".join(decoded_words), WORD_SENTENCE)
        self.assertEqual(len(path), len(WORD_SEQUENCE))
        logger.info(
            "Round-tripped %d words over %d distinct fixed word values.",
            len(path),
            len(dataset.values),
        )

    def test_precomputed_and_on_demand_keys_encode_identically(self):
        precomputed_path = encode_values(PARAGRAPH, self.dataset, self.keys)
        on_demand_path = encode_values(PARAGRAPH, self.dataset)

        self.assertEqual(
            [node.key for node in precomputed_path],
            [node.key for node in on_demand_path],
        )
        logger.info("AOT and on-demand encoding produced the same rotation keys.")

    def test_dataset_and_query_remain_unchanged_during_rotation_lookup(self):
        query_before = self.dataset.invariant_query
        for key in self.keys.values():
            query_value(key, self.dataset)

        np.testing.assert_array_equal(self.dataset.points, self.original_points)
        np.testing.assert_array_equal(
            self.dataset.tree.data, self.original_tree_data
        )
        self.assertEqual(self.dataset.invariant_query, query_before)
        self.assertFalse(self.dataset.points.flags.writeable)
        self.assertFalse(self.dataset.tree.data.flags.writeable)
        logger.info("All rotations left the query and indexed points unchanged.")

    def test_aot_rotation_keys_are_unique_for_character_values(self):
        self.assertEqual(len(self.keys), len(CHARACTER_VALUES))
        self.assertEqual(len(set(self.keys.values())), len(self.keys))
        logger.info(
            "Precomputed %d distinct spherical keys for the character dataset.",
            len(self.keys),
        )

    def test_rotation_keys_round_trip_to_their_indexed_values(self):
        for value, key in self.keys.items():
            retrieved, distance = query_value(key, self.dataset)
            self.assertEqual(retrieved, value)
            self.assertLess(distance, 1e-12)

    def test_uniform_grid_returns_same_value_for_every_orientation(self):
        cell_width, cells = build_uniform_grid(self.dataset)
        for key, expected in zip(self.keys.values(), self.dataset.values):
            self.assertEqual(
                query_uniform_grid(key, self.dataset, cell_width, cells),
                expected,
            )
        logger.info(
            "Uniform grid matched all %d character values without a KD-Tree.",
            len(self.dataset.values),
        )

    def test_unsupported_values_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "not in the fixed dataset"):
            encode_values("?", self.dataset, self.keys)

    def test_dataset_rejects_empty_or_duplicate_values(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            build_fixed_dataset(())
        with self.assertRaisesRegex(ValueError, "unique"):
            build_fixed_dataset(("A", "A"))
        with self.assertRaisesRegex(ValueError, "nonzero"):
            build_fixed_dataset(("A",), (0.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()