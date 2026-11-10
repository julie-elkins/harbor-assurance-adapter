# Raman unit-contract diagnostic

This instruction is for a controlled diagnostic ablation. It does not change
the Terminal-Bench task, verifier, or leaderboard condition.

For this run, make the coordinate system explicit before fitting:

1. Treat the first column as wavelength in nanometres.
2. Convert it to calibrated Raman-shift coordinates in inverse centimetres
   using `x_calibrated = 1e7 / wavelength_nm`.
3. Select and fit the G and 2D peaks in the calibrated coordinate.
4. Report `x0` and `gamma` in inverse centimetres. Report amplitude and offset
   in the intensity units of the input.

Write the required `/app/results.json` file and preserve the task's requested
schema. Do not modify the verifier or add explanatory files instead of the
required result.
