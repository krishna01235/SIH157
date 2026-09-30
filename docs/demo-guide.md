# NIGRANI-SA evaluator walkthrough

Open the local workbench at `http://localhost:8000` after following the README setup. The synthetic sample is safe to explore and can be loaded repeatedly without resetting saved reviews.

1. On the overview, read the product purpose and choose **Explore sample assessment**. The workbench creates two synthetic submissions through its normal importer and runs the same three checks used for uploaded files.
2. Open the signal example. It has 6 assets, 12 alerts, and 8 cases. The cards show rapid closure **2 of 6**, no recorded investigation **1 of 5**, and critical assets absent from a declared complete alert export **1 of 4**. These are observations for a human, not a risk grade.
3. Open **Rapid closure**. Inspect `CASE-01` and `CASE-02`, their source row references and file hashes, and the visible 300-second rule threshold. Open the coverage observation to see the inventory row and the coverage declaration; no alert is fabricated for an absent record.
4. Set one observation to **Needs context**, add a note, and save. Refresh the page: the decision and note remain. Review history appears in the evidence drawer. **Export CSV** downloads the current review, including all affected source records and lineage.
5. Return to the overview and open the second synthetic submission. It has zero observations. The absence of these three signals is not a general security finding.

To evaluate import, choose **New submission**. Download the three templates, select an entity and a 1–90 day UTC window, upload matching `assets.csv`, `alerts.csv`, and `cases.csv`, and declare alert-export coverage. The committed `demo/no-signal-example` files are a valid upload example. The `demo/invalid-example` files demonstrate row-level errors: an unknown asset reference and a case closure before opening. An invalid submission is rejected as a whole.

The three rules are deliberately narrow. `MVP-EG-01` flags closed high/critical cases under 300 seconds; `MVP-EG-02` flags a reported investigation count of zero among otherwise eligible cases with known counts; `MVP-NS-01` flags in-scope critical assets with no alerts only when the export is declared complete. A blank investigation count is unknown, and incomplete coverage makes the absence check not evaluable.
