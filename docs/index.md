---
hide:
  - navigation
---

# DV-TrioTrain v0.8

TrioTrain (DV-TT) is an automated pipeline for extending DeepVariant, a deep-learning-based germline variant caller. To learn more about DeepVariant, [see the original GitHub page.](https://github.com/google/deepvariant)

---

## Why use TrioTrain?

The unique re-training approach enables the model to incorporate inheritance expectations; **however, models built by DV-TrioTrain do not require trio-binned data for variant calling.** While the DV-TT pipeline assumes re-training data are from trio-binned samples, models are trained to prioritize features of inherited variants to produce fewer Mendelian Inheritance Errors (MIE) in individual samples.

---

[Get Started with TrioTrain](./getting-started/getting-started.md){ .md-button .md-button--primary }

---

## Contributing to TrioTrain

Please [open a Github pull request](https://github.com/jkalleberg/DV-TrioTrain/pulls) if you wish to contribute to TrioTrain.

---

## License

[GPL-3.0 license](about/license.md)
