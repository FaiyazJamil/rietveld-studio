# Scientific method and interpretation

## Numerical model

The application delegates profile calculation and least-squares refinement to GSAS-II's `GSASIIscriptable` API. The model uses the confirmed crystal structures, GSAS-II scattering factors and symmetry, histogram/phase scale conventions, background polynomial, measurement geometry, instrumental peak profile, and enabled sample/atomic parameters.

The GUI supports constant-wavelength X-ray `PXC` patterns only. The fitted intensity includes the background. No preprocessing changes the measured intensity, except converting text input to a normalized XY-sigma representation; the unchanged original input is archived too.

## Statistics

On included observations i with intensity yᵢ, calculated intensity ŷᵢ, weights wᵢ = 1/σᵢ², N observations, and P refined independent variables:

\[
R_p = 100\frac{\sum_i |y_i-\hat y_i|}{\sum_i |y_i|}
\]

\[
R_{wp}=100\sqrt{\frac{\sum_i w_i(y_i-\hat y_i)^2}{\sum_i w_i y_i^2}}
\]

\[
R_{exp}=100\sqrt{\frac{N-P}{\sum_i w_i y_i^2}}
\]

\[
\chi^2_{red}=\frac{\sum_iw_i(y_i-\hat y_i)^2}{N-P}
=\left(\frac{R_{wp}}{R_{exp}}\right)^2,
\quad GOF=\sqrt{\chi^2_{red}}
\]

`weighted_SSE` is the numerator sum; it is not divided by degrees of freedom. Some GSAS-II logs call this sum `chi**2`. The app labels **weighted SSE** and **reduced χ²** distinctly and preserves the engine's raw values separately.

Excluded intervals and points outside the fitted 2θ range do not contribute. Rp/Rwp include background and use the exact inclusion mask. No restraints are introduced by this GUI. A future restraint model would need explicit accounting of its terms rather than blindly applying these degrees of freedom.

Durbin–Watson uses adjacent **standardized residuals** and does not bridge gaps over excluded intervals. It is a qualitative correlation diagnostic; oversampling, detector behavior, and correlated counting errors can affect its interpretation.

## Weighting and uncertainties

- Raw counts: estimated σᵢ = √max(yᵢ,1).
- XRDML CPS with a positive common counting time t: σᵢ = √max(CPSᵢ·t,1)/t.
- User-provided sigma: values are used directly. The user must supply standard deviations, not variances, relative errors, or weights.
- Constant sigma: the user explicitly selects a constant positive sigma. The resulting reduced χ²/GOF is descriptive and does not establish a statistically correct error model.

Reported refined-parameter and lattice standard uncertainties come from GSAS-II and its covariance propagation. GSAS-II scales covariance according to its GOF convention. Fixed parameters/symmetry-fixed angles have no independently estimated standard uncertainty; the app leaves these blank rather than displaying misleading exact zeros.

These uncertainties are **conditional on the selected model, declared weights, profile, fit range, and corrections**. Wavelength/calibration/height systematics, chemistry/model bias, unmodeled phases, microabsorption, and correlated errors are not automatically included.

## Broadening

Instrument coefficients use GSAS-II conventions, not arbitrary Gaussian full widths. The app can either fit an effective instrumental profile or hold a calibrated instrumental profile fixed and fit isotropic sample broadening. Size is reported in µm in tables and nm in the GUI; microstrain is reported as ΔQ/Q × 10⁶ (ppm). Their standard uncertainties are exported explicitly when refined.

Fitting a sample's line widths cannot independently establish an instrumental profile and a sample crystallite-size/strain contribution without appropriate calibration. The GUI therefore prevents free instrument broadening and free size/strain from being selected simultaneously. A calibration declaration is user-supplied, not verified from an uploaded standard.

Coherent diffraction-domain size can differ from SEM/TEM particle size. Strain/size/texture/ADP parameters can correlate, and broadening that is not resolved should not be interpreted as a precise physical result.

## Phase fractions and atomic interpretation

Mass fractions use GSAS-II's HAP scale convention and covariance derivatives. GSAS-II phase scales already incorporate its volume normalization; a second manual cell-volume factor must not be added. One phase scale is held while the global scale and additional phase scales are refined to avoid a redundant scale degree of freedom.

Reported weight fractions are normalized over the **included modeled crystalline phases**. There is no automatic internal-standard/amorphous-content determination or microabsorption correction. A single modeled phase is shown as 100% of the modeled crystalline fraction, not proof of bulk chemical purity.

Site occupancies remain fixed. X-ray refinements of Li-rich/transition-metal cathodes do not, by themselves, establish Li content, oxidation state, or unique dilute-dopant occupation. Additional chemical/physical measurements and properly constrained expert models may be necessary.

Atomic-coordinate and isotropic-ADP refinements are opt-in. Anisotropic atoms retain the supplied ADP model; the GUI does not silently convert them to Uiso. Available coordinate and Uiso uncertainties are taken from refined/dependent GSAS-II variables; complete variable/covariance data are retained for expert analysis.

## Peak associations

Observed peaks are unsmoothed local maxima exceeding the selected prominence threshold. Calculated reflections from the confirmed structural model are associated within the user's angular tolerance. All within-tolerance candidates remain in the association table, so overlap is not forced into a unique identity. Reflections may be present without a detectable isolated maximum; thresholds can miss weak/overlapped peaks.

COD URLs, publication DOIs, input hashes, and the exact used CIF blocks preserve traceability. A calculated hkl assignment is conditional on the confirmed structure. It is not independent experimental phase identification or an ICDD/JCPDS card match.

