---
hide:
  - navigation
  - toc
  - path
---

# DV-TrioTrain v0.8

DeepVariant-TrioTrain (DV-TT) is an automated pipeline for extending DeepVariant (DV), a deep-learning-based germline variant caller. See the [original DeepVariant github page](https://github.com/google/deepvariant) to learn more about DeepVariant.

While the DV-TT pipeline assumes re-training data are from trio-binned samples, models built by DV-TrioTrain **do not require trio-binned data for variant calling.** In contrast to the [DeepTrio](https://github.com/google/deepvariant/blob/r1.5/docs/deeptrio-details.md) joint-caller, DV-TT models are trained to prioritize features of inherited variants to produce fewer Mendelian Inheritance Errors (MIE) in individual samples.

---
### Contributing to TrioTrain

Please [open a pull request (fix this link)]() if you wish to contribute to TrioTrain.
