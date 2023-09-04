# Existing DeepVariant Models

The following models are compatible with TrioTrain.

---

## DeepVariant WGS

| Species | Version | Shape | Channels | Model Source   |
| ------- | ------- | ----- | -------- | -------------- |
| Human   | v1.4    | `height=100; width=221; n_channels=7` | `1-6,19` | [Insert Size model](https://console.cloud.google.com/storage/browser/deepvariant/models/DeepVariant/1.4.0/DeepVariant-inception_v3-1.4.0+data-wgs_standard) |

---

## DeepVariant WGS.AF

| Species | Version | Shape | Channels | Model Source   |
| ------- | ------- | ----- | -------- | -------------- |
| Human   | v1.4    | `height=100; width=221; n_channels=8` | `1-6,8,19` |  [Allele Frequency model](https://console.cloud.google.com/storage/browser/brain-genomics-public/research/allele_frequency/pretrained_model_WGS/1.4.0/) |
| Bovine | v1.4    | `height=100; width=221; n_channels=8` | `1-6,8,19` |  [Custom Allel Frequency model](https://github.com/jkalleberg/DV-TrioTrain/triotrain/model_training/pretrained_models/)|
