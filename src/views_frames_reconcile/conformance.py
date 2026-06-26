"""Conformance checks for the reconcile package (ADR-023).

A consumer can re-run these against its own frame factories to confirm the
reconciler behaves: grid (``pgm``) predictions sum, per draw, to their country
(``cm``) totals; zeros are preserved; values stay non-negative; the cm↔pgm mapping
is **injected, never fetched**.

The contract assertion (``assert_reconcile_contract``) lands in story #136 (S5),
mirroring ``views_frames_summarize/conformance.py:assert_summarizer_contract``.
This module is an intentional stub at scaffold stage (S2).
"""
