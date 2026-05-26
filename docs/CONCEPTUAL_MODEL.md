# Conceptual Model

This project is not trying to prove universal compression. It is trying to build
a verified compressor for visually structured data.

The central claim is deliberately narrow:

```text
Some large visual datasets have low-complexity structure.
If that structure is modeled explicitly, the visual asset can be smaller than a
direct point-by-point export while staying within a measured error budget.
```

## Representation Is Not Compression

Any finite dataset can be represented by a function. For samples

```math
D = \{(x_i, y_i)\}_{i=1}^{N}
```

there is always some interpolating function `f` such that

```math
f(x_i) = y_i
```

for every sample. This does not imply useful compression. A function with too
many coefficients, high numeric precision, or a large residual layer can be as
large as the original data.

The useful test is:

```math
|C| + |M| + |R| < |B|
```

Where:

- `C` is the compact function model.
- `M` is metadata such as domain, branch, topology, and package manifest.
- `R` is residual data needed to satisfy the error budget.
- `B` is a baseline export such as direct SVG, CSV.gz, JSON.gz, or another
  reference format.

If the inequality does not hold, the compressor should report that the candidate
model is not useful for that dataset.

## Basis Plus Residual

The practical model is:

```math
D(x) \approx F_\theta(x) + R(x)
```

Where:

- `F_\theta` is a low-complexity basis model, such as Fourier, spline, radial
  distance, or another fitted function.
- `R` stores what the basis model cannot explain cheaply.

In plain engineering terms:

```text
original data = main shape + residual details
```

The main shape is compressed with a function. The residual details are either
stored as sparse points, a secondary Fourier layer, a statistical noise summary,
or dropped only when the selected package profile allows it.

## Verified Approximation

The project should not ask users to trust a model by inspection. Every accepted
compression should be decodable and measurable.

For original data `D` and decoded reconstruction `\hat{D}`:

```math
\epsilon(D, \hat{D}) \leq \tau
```

Where:

- `\epsilon` is a selected error metric.
- `\tau` is the user or profile error budget.

For time series MVP work, the first metrics are:

```math
RMSE = \sqrt{\frac{1}{N}\sum_{i=1}^{N}(y_i - \hat{y}_i)^2}
```

```math
MAE = \frac{1}{N}\sum_{i=1}^{N}|y_i - \hat{y}_i|
```

```math
MaxError = \max_i |y_i - \hat{y}_i|
```

These metrics do not prove optimality. They prove that a produced package meets
the declared fidelity condition for the measured reconstruction.

## Branch And Domain Constraints

Implicit functions introduce a special risk: an equation can have multiple valid
solution branches.

For example:

```math
y^2 = x
```

has two branches:

```math
y = \sqrt{x}
```

and

```math
y = -\sqrt{x}
```

If a visual asset stores only the equation, the decoder may choose a mathematically
valid branch that is not the original shape. Therefore future implicit packages
must store more than a function:

```text
function + domain + branch selector + anchors + topology + residual
```

For the current time-series MVP, the same idea appears as x-domain storage:

- uniform domains can be reconstructed from `x_min`, `x_max`, and sample count.
- irregular domains must be preserved or compressed with an explicit error
  budget.

## Soundness Boundary

The project aims for soundness by verification:

```text
If the package says it is valid, the package can be decoded and checked against
its manifest, hashes, model arrays, and reconstruction constraints.
```

It does not aim for universal completeness:

```text
The compressor does not promise that every dataset can be compressed into a
smaller function asset.
```

This is the correct boundary for an engineering system. It allows successful
packages to be trusted while letting unfit datasets fall back to direct or more
conservative formats.

## Current Package Verification

`vizcompress verify` has two levels.

### Package Self-Consistency

Without a source dataset, `vizcompress verify package.vizretain` checks package
self-consistency:

- manifest schema and required fields
- required files
- file byte sizes
- SHA-256 hashes
- `model.npz` required arrays
- x-domain array consistency
- residual layer array consistency
- finite Fourier and retained-signal reconstruction

This proves that the package handoff is internally sound. It does not prove that
the decoded signal is close to the original raw source, because the package does
not embed raw input.

### Source-Backed Fidelity

When the original source is available, the verifier can decode the package and
compare it directly against that source:

```powershell
py -m vizcompress.cli verify outputs/model.vizretain --synthetic 100000 --max-rmse 0.01
```

or:

```powershell
py -m vizcompress.cli verify outputs/model.vizretain --csv data.csv --x-column time --y-column value --max-rmse 0.01
```

The mathematical check is:

```math
\epsilon(D, decode(P)) \leq \tau
```

Where:

- `D` is the source dataset.
- `P` is the package.
- `decode(P)` is the selected decoded signal, usually the retained signal.
- `\tau` is the requested error budget.

This is the first executable form of the project's soundness claim. It still
does not prove that the package is the smallest possible representation. It only
proves that this package decodes close enough to this source under the selected
metric budget.

Full production verification will later need:

- access to the original input data, or
- a review packet that records source fingerprints and accepted error metrics at
  build time.

## Review Packets

A review packet is the durable evidence for why a package was accepted. It is
not the raw data. It is a signed-style summary of what was checked:

```text
review.json
  source fingerprint
  size evidence
  verification policy
  package self-consistency result
  source-fidelity result
  accepted = true | false
```

The source fingerprint stores hashes of the numeric x/y arrays:

```math
h_x = SHA256(bytes(x))
```

```math
h_y = SHA256(bytes(y))
```

This lets a later agent detect whether the source used for review is the same
source that produced the accepted metrics.

The packet also records a basic size comparison:

```math
ratio = \frac{|source\ numeric\ arrays|}{|package|}
```

This is not the final compression proof against every possible baseline, but it
prevents fidelity-only reviews from ignoring package overhead.

When a direct SVG baseline is available, the review packet records both raw SVG
bytes and gzip-compressed SVG bytes. This matters because text-based baselines
are often transported with gzip; a fair package claim should survive comparison
against compressed baselines, not only raw text.

When `--require-review-pass` is used, the build command treats `accepted: false`
as a hard failure. This is the operational form of "do not accept a compressed
asset that exceeds its declared error budget."
