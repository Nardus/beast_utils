# beast_utils

<!-- badges: start -->
[![Project Status: WIP – Initial development is in progress, but there has not yet been a stable, usable release suitable for the public.](https://www.repostatus.org/badges/latest/wip.svg)](https://www.repostatus.org/#wip)
<!-- badges: end -->


Generate and manipulate BEAST v1 XML files using templates and simple python calls.

This library provides an API allowing programmatic generation of BEAST XML files. Its main aim is to separate data (which may change) from basic run setup (which can be saved in a template XML file generated manually or using BEAUTI). This simplifies use of BEAST in a pipeline, where sequence data and metadata (e.g., dates, locations) may change over the course of the project, and alongside it, things like the best partitioning scheme and substitution models or predictors for GLMs. Note however, that this library focusses primarily on phylogeographic analyses, and cannot support all possible analyses that BEAST is capable of. 

Key features currently implemented are:
- Merge arbitrary XML templates, allowing complex analyses to be specified in a more modular fashion
- Insert or update sequence data, dates, and traits, including complex partitioning schemes
- Parse IQ-Tree result files to find the appropriate partitioning scheme and substitution models
- Insert or update substitution models
- Insert or modify the starting tree specification
- Update parameters which depend on data (e.g. matrix dimensions), in most cases automatically
- Add various phylogeography-related blocks to an XML:
    - GLMs
    - Markov jumps/rewards
- Change run length / output file names

## Installation
```
pip install git+https://github.com/nardus/beast_utils.git
```


## History
This library was originally developed as part of a [rabies spatial expansion project](https://github.com/Nardus/rabies_invasion/). To view earlier versions, see [here](https://github.com/Nardus/rabies_invasion/tree/37b448bf5630de574df349f2e1270810b177fd6a/src/beast).
