---
hide:
  - navigation
---

# DV-TrioTrain v0.8

DV-TrioTrain is a model development framework for [DeepVariant](https://github.com/google/deepvariant): a deep-learning-based germline variant caller. Here we provide an automated pipeline for extending DeepVariant v1.4.0 in new species.

### **Models built by DV-TrioTrain do not require trio-binned data for variant calling.** 

Our unique re-training approach enables the model to incorporate inheritance expectations. Using TrioTrain to build new versions of DeepVariant models requires trio-binned genomes, the final model produced by TrioTrain works on individual genomes, while prioritizing features of inherited variants. 


[Get Started with TrioTrain](./getting-started/getting-started.md){ .md-button .md-button--primary }

---

### Contributing to TrioTrain

Please [open a Github pull request](https://github.com/jkalleberg/DV-TrioTrain/pulls) if you wish to contribute to TrioTrain.

### License

[GPL-3.0 license](about/license.md)
