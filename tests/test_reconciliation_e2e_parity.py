"""S4/S5 (#36/#37): the public `ReconciliationModule`, end-to-end parity gate.

The gate that turns "leaf ported" into "pipeline migrated": the whole
frames-native module reproduces the frozen views-reporting pipeline on the S0
fixture. Offline — numpy + views-frames + the committed fixture only.
"""

from pathlib import Path

import numpy as np
import pytest

from views_frames import SpatialLevel
from views_frames_reconcile import (
    ALIGNED_DRAWS,
    POINT_BROADCAST,
    ReconciliationModule,
    ReconciliationResult,
)
from views_frames_reconcile.frames import prediction_frame_from_arrays

_FIX = Path(__file__).resolve().parent / "fixtures" / "reconciliation_e2e_parity.npz"
_TARGETS = ["pred_ged_sb", "pred_ged_ns"]
_GRIDS = {1: [100, 101], 2: [102, 103, 104], 3: [105, 106],
          4: [107, 108, 109, 110], 5: [111, 112]}
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


class TestEndToEndParity:
    @pytest.mark.parametrize("target", _TARGETS)
    def test_module_reproduces_oracle(self, fix, module, target):
        cm, pgm = _frames(fix, target)
        out = module.reconcile(cm, pgm)
        np.testing.assert_allclose(
            out.values, fix[f"recon__{target}"], rtol=1e-5, atol=1e-6,
            err_msg=f"module output drifts from the frozen oracle on {target}",
        )


class TestModuleProperties:
    def test_de_mutated(self, fix, module):
        cm, pgm = _frames(fix, "pred_ged_sb")
        before = pgm.values.copy()
        out = module.reconcile(cm, pgm)
        assert out is not pgm
        np.testing.assert_array_equal(pgm.values, before)

    def test_sum_constraint_on_active_draws(self, fix, module):
        cm, pgm = _frames(fix, "pred_ged_sb")
        out = module.reconcile(cm, pgm)
        recon = {(int(t), int(u)): out.values[i]
                 for i, (t, u) in enumerate(zip(fix["pg_time"], fix["pg_unit"], strict=True))}
        pin = {(int(t), int(u)): fix["pg__pred_ged_sb"][i]
               for i, (t, u) in enumerate(zip(fix["pg_time"], fix["pg_unit"], strict=True))}
        cmv = {(int(t), int(u)): fix["cm__pred_ged_sb"][i]
               for i, (t, u) in enumerate(zip(fix["cm_time"], fix["cm_unit"], strict=True))}
        for m in _MONTHS:
            for c, gs in _GRIDS.items():
                allzero = np.stack([pin[(m, g)] for g in gs]).sum(axis=0) == 0
                grid_sum = np.stack([recon[(m, g)] for g in gs]).sum(axis=0)
                active = ~allzero
                np.testing.assert_allclose(
                    grid_sum[active], cmv[(m, c)][active], rtol=1e-4, atol=1e-3
                )
                assert (grid_sum[allzero] == 0).all()  # all-zero draws stay zero

    def test_point_country_broadcast_equals_manual_tile(self, fix, module):
        # S1 (#143): native point-broadcast must be bit-identical to manually tiling the
        # point country to S draws and running the (oracle-proven) aligned path.
        _, pgm = _frames(fix, "pred_ged_sb")
        s = pgm.sample_count
        point_vals = fix["cm__pred_ged_sb"][:, :1]  # a point country (sample_count == 1)
        point_cm = prediction_frame_from_arrays(
            fix["cm_time"], fix["cm_unit"], point_vals, level=SpatialLevel.CM
        )
        tiled_cm = prediction_frame_from_arrays(
            fix["cm_time"], fix["cm_unit"], np.tile(point_vals, (1, s)),
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
        assert result.method == "proportional"
        # the result frame is exactly what reconcile() returns
        np.testing.assert_array_equal(
            result.frame.values, module.reconcile(cm, pgm).values
        )

    def test_point_broadcast_mode(self, fix, module):
        _, pgm = _frames(fix, "pred_ged_sb")
        point_cm = prediction_frame_from_arrays(
            fix["cm_time"], fix["cm_unit"], fix["cm__pred_ged_sb"][:, :1],
            level=SpatialLevel.CM,
        )
        result = module.reconcile_result(point_cm, pgm)
        assert result.mode == POINT_BROADCAST
        assert result.frame.sample_count == pgm.sample_count
