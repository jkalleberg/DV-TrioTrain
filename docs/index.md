---
hide:
  - navigation
---

# DV-TrioTrain v0.8

DeepVariant-TrioTrain (DV-TT) is an automated pipeline for extending DeepVariant (DV), a deep-learning-based germline variant caller. See the [original DeepVariant github page](https://github.com/google/deepvariant) to learn more about DeepVariant.

---

## Why use TrioTrain?

While the DV-TT pipeline assumes re-training data are from trio-binned samples, models built by DV-TrioTrain **do not require trio-binned data for variant calling.** In contrast to the [DeepTrio](https://github.com/google/deepvariant/blob/r1.5/docs/deeptrio-details.md) joint-caller, DV-TT models are trained to prioritize features of inherited variants to produce fewer Mendelian Inheritance Errors (MIE) in individual samples.

---

[Get Started with TrioTrain](./getting-started/getting-started.md){ .md-button .md-button--primary }

---

## Contributing to TrioTrain

Please [open a Github pull request](https://github.com/jkalleberg/DV-TrioTrain/pulls) if you wish to contribute to TrioTrain.

---

## License

[GPL-3.0 license](about/license.md)
