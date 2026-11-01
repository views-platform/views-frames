"""S4/S5 (#36/#37): the public `ReconciliationModule`, end-to-end parity gate.

The gate that turns "leaf ported" into "pipeline migrated": the whole
frames-native module reproduces the frozen views-reporting pipeline on the S0
fixture. Offline — numpy + views-frames + the committed fixture only.

Since 3.0.0 (ADR-030) the module deliberately differs from the oracle in one place: a
draw whose grid is all zeros while the country is positive is filled from a donor draw
instead of staying zero (the oracle loses that mass, #283). The fixture has 91 such draws
for ``pred_ged_sb`` and 87 for ``pred_ged_ns``, all with donors. Parity is therefore
asserted on every other draw, and the filled draws are held to the new law instead.
"""

from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import pytest

from views_frames import SpatialLevel
from views_frames_reconcile import (
    ALIGNED_DRAWS,
    METHOD_DONOR_FILL,
    POINT_BROADCAST,
    ReconciliationModule,
    ReconciliationResult,
)
from views_frames_reconcile.frames import prediction_frame_from_arrays

_FIX = Path(__file__).resolve().parent / "fixtures" / "reconciliation_e2e_parity.npz"
_TARGETS = ["pred_ged_sb", "pred_ged_ns"]
_GRIDS = {
    1: [100, 101],
    2: [102, 103, 104],
    3: [105, 106],
    4: [107, 108, 109, 110],
    5: [111, 112],
}
_MONTHS = [528, 529, 530]


@pytest.fixture(scope="module")
def fix():
    return np.load(_FIX)


@pytest.fixture(scope="module")
def module(fix):
    return ReconciliationModule(
        np.stack([fix["pg_time"], fix["pg_unit"]], axis=1), fix["pg_country"]
    )


def _frames(fix, target):
    pgm = prediction_frame_from_arrays(
        fix["pg_time"], fix["pg_unit"], fix[f"pg__{target}"], level=SpatialLevel.PGM
    )
    cm = prediction_frame_from_arrays(
        fix["cm_time"], fix["cm_unit"], fix[f"cm__{target}"], level=SpatialLevel.CM
    )
    return cm, pgm


def _filled_draws(fix, target):
    """``(N_pg, S)`` mask: the cells of draws whose group grid is empty, country > 0."""
    pg = fix[f"pg__{target}"]
    mask = np.zeros(pg.shape, dtype=bool)
    for j, (t, c) in enumerate(zip(fix["cm_time"], fix["cm_unit"], strict=True)):
        rows = (fix["pg_time"] == t) & (fix["pg_country"] == c)
        empty = ~(pg[rows] > 0).any(axis=0) & (fix[f"cm__{target}"][j] > 0)
        mask[rows] = empty
    return mask


class TestEndToEndParity:
    @pytest.mark.parametrize("target", _TARGETS)
    def test_module_reproduces_oracle_outside_filled_draws(self, fix, module, target):
        cm, pgm = _frames(fix, target)
        out = module.reconcile(cm, pgm)
        keep = ~_filled_draws(fix, target)
        assert (~keep).any(), "the fixture no longer exercises donor fill"
        np.testing.assert_allclose(
            out.values[keep],
            fix[f"recon__{target}"][keep],
            rtol=1e-5,
            atol=1e-6,
            err_msg=f"module output drifts from the frozen oracle on {target}",
        )

    @pytest.mark.parametrize("target", _TARGETS)
    def test_oracle_lost_the_mass_the_module_places(self, fix, module, target):
        # the reason for the exception above: the oracle leaves these draws at zero
        filled = _filled_draws(fix, target)
        assert (fix[f"recon__{target}"][filled] == 0).all()
        out = module.reconcile(*_frames(fix, target))
        assert out.values[filled].sum() > 0


class TestModuleProperties:
    def test_de_mutated(self, fix, module):
        cm, pgm = _frames(fix, "pred_ged_sb")
        before = pgm.values.copy()
        out = module.reconcile(cm, pgm)
        assert out is not pgm
        np.testing.assert_array_equal(pgm.values, before)

    def test_sum_constraint_on_every_draw(self, fix, module):
        cm, pgm = _frames(fix, "pred_ged_sb")
        out = module.reconcile(cm, pgm)
        recon = {
            (int(t), int(u)): out.values[i]
            for i, (t, u) in enumerate(zip(fix["pg_time"], fix["pg_unit"], strict=True))
        }
        cmv = {
            (int(t), int(u)): fix["cm__pred_ged_sb"][i]
            for i, (t, u) in enumerate(zip(fix["cm_time"], fix["cm_unit"], strict=True))
        }
        for m in _MONTHS:
            for c, gs in _GRIDS.items():
                # every draw, including those whose input grid was all zeros (ADR-030)
                grid_sum = np.stack([recon[(m, g)] for g in gs]).sum(axis=0)
                np.testing.assert_allclose(grid_sum, cmv[(m, c)], rtol=1e-4, atol=1e-3)

    def test_point_country_broadcast_equals_manual_tile(self, fix, module):
        # S1 (#143): native point-broadcast must be bit-identical to manually tiling the
        # point country to S draws and running the (oracle-proven) aligned path.
        _, pgm = _frames(fix, "pred_ged_sb")
        s = pgm.sample_count
        point_vals = fix["cm__pred_ged_sb"][
            :, :1
        ]  # a point country (sample_count == 1)
        point_cm = prediction_frame_from_arrays(
            fix["cm_time"], fix["cm_unit"], point_vals, level=SpatialLevel.CM
        )
        tiled_cm = prediction_frame_from_arrays(
            fix["cm_time"],
            fix["cm_unit"],
            np.tile(point_vals, (1, s)),
            level=SpatialLevel.CM,
        )
        out_point = module.reconcile(point_cm, pgm)
        out_tiled = module.reconcile(tiled_cm, pgm)
        np.testing.assert_array_equal(out_point.values, out_tiled.values)

    def test_bad_mapping_shape_raises(self, fix):
        with pytest.raises(ValueError, match="map_keys must be"):
            ReconciliationModule(fix["pg_time"], fix["pg_country"])  # 1-D keys

    def test_validates_before_reconciling(self, fix, module):
        # cm frame at the wrong level -> validation raises (not a mid-compute crash)
        cm_wrong, pgm = _frames(fix, "pred_ged_sb")
        with pytest.raises(ValueError, match="SpatialLevel.CM"):
            module.reconcile(pgm, pgm)  # pass pgm where cm expected


class TestReconciliationResult:
    """S2 (#144): the mode is *returned* on a result, not stamped on the leaf frame."""

    def test_aligned_draws_mode(self, fix, module):
        cm, pgm = _frames(fix, "pred_ged_sb")  # cm carries S draws
        result = module.reconcile_result(cm, pgm)
        assert isinstance(result, ReconciliationResult)
        assert result.mode == ALIGNED_DRAWS
        assert result.method == METHOD_DONOR_FILL == "proportional-donor-fill"
        assert result.filled_draws == 91  # the fixture's empty-grid draws (sb)
        # the result frame is exactly what reconcile() returns
        np.testing.assert_array_equal(
            result.frame.values, module.reconcile(cm, pgm).values
        )

    def test_point_broadcast_mode(self, fix, module):
        _, pgm = _frames(fix, "pred_ged_sb")
        point_cm = prediction_frame_from_arrays(
            fix["cm_time"],
            fix["cm_unit"],
            fix["cm__pred_ged_sb"][:, :1],
            level=SpatialLevel.CM,
        )
        result = module.reconcile_result(point_cm, pgm)
        assert result.mode == POINT_BROADCAST
        assert result.frame.sample_count == pgm.sample_count

    def test_both_points_is_aligned_draws(self, fix, module):
        # mode-corner (S3): cm and pgm both points (sample_count == 1). Nothing is
        # broadcast (counts already match), so the mode is ALIGNED_DRAWS — not
        # POINT_BROADCAST — and the result stays a single-draw frame.
        point_cm = prediction_frame_from_arrays(
            fix["cm_time"],
            fix["cm_unit"],
            fix["cm__pred_ged_sb"][:, :1],
            level=SpatialLevel.CM,
        )
        point_pgm = prediction_frame_from_arrays(
            fix["pg_time"],
            fix["pg_unit"],
            fix["pg__pred_ged_sb"][:, :1],
            level=SpatialLevel.PGM,
        )
        result = module.reconcile_result(point_cm, point_pgm)
        assert result.mode == ALIGNED_DRAWS
        assert result.frame.sample_count == 1

    def test_pre_tiled_point_cm_is_aligned_draws(self, fix, module):
        # mode-corner (S3): a caller who pre-tiles a point country to S draws BEFORE
        # calling reads as ALIGNED_DRAWS (nothing was broadcast inside this call) — the
        # mode describes what THIS call did, per result.py. Contrast test_point_broadcast_mode
        # (a genuine sample_count==1 cm), which reads POINT_BROADCAST.
        _, pgm = _frames(fix, "pred_ged_sb")
        s = pgm.sample_count
        tiled_cm = prediction_frame_from_arrays(
            fix["cm_time"],
            fix["cm_unit"],
            np.tile(fix["cm__pred_ged_sb"][:, :1], (1, s)),
            level=SpatialLevel.CM,
        )
        result = module.reconcile_result(tiled_cm, pgm)
        assert result.mode == ALIGNED_DRAWS
        assert result.frame.sample_count == s

    def test_result_is_frozen(self, fix, module):
        # ReconciliationResult is a @dataclass(frozen=True) — its mode/method/frame must
        # be immutable so a reported mode can't be retro-edited (mirrors
        # test_frames.py::test_metadata_is_frozen).
        cm, pgm = _frames(fix, "pred_ged_sb")
        result = module.reconcile_result(cm, pgm)
        with pytest.raises(FrozenInstanceError):
            result.mode = POINT_BROADCAST  # type: ignore[misc]
