Controlled diagnostic instruction: make the coordinate system explicit before
fitting. Treat the first column as wavelength in nanometres. Convert it to
calibrated Raman-shift coordinates in inverse centimetres using
`x_calibrated = 1e7 / wavelength_nm`. Select and fit the G and 2D peaks in the
calibrated coordinate. Report `x0` and `gamma` in inverse centimetres, and
report amplitude and offset in the input intensity units. Write the required
`/app/results.json` file with the task's requested schema. Do not modify the
verifier. This is a diagnostic instruction and must not be treated as a
leaderboard condition.
