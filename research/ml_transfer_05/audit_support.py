"""Audit frozen input support on G36 normal without loading a model or computing a residual."""
import argparse
import json
from pathlib import Path

from research.ml_transfer_05.contract import (
    ContractError, PROTOCOL_SHA, block_rows, blocks, input_support, load_protocol, masks, read_input,
)


def main(inputs, fit_receipt, output):
    protocol = load_protocol()
    fit = json.loads(fit_receipt.read_text())
    if (fit["protocol_sha256"] != PROTOCOL_SHA or fit["source_sha256"] != protocol["files"]["source"]["sha256"]
            or fit["scope"] != "SOURCE_NORMAL_ONLY"):
        raise ContractError("UNQUALIFIED_SOURCE_SUPPORT")
    reference = read_input(inputs, "target_reference")
    probe = read_input(inputs, "target_probe")
    _, probe_valid = masks(probe, protocol)
    denominator, valid = masks(reference, protocol)
    support = input_support(reference.channels, fit["train_support_degF"])
    labels = blocks(reference, protocol)
    coverage = [row for _, _, row in block_rows(labels, denominator, valid & support, protocol)]
    complete = labels.lt(protocol["mask"]["target_complete_blocks"])
    with output.open("x") as stream:
        json.dump({
            "scope": "INPUTS_ONLY", "target_prediction_executed": False, "target_healthy_gate": "NOT_EXECUTED",
            "paired_pre_support_intersection_minutes": int((complete & valid & probe_valid).sum()),
            "normal_warm_running_minutes": int((complete & denominator).sum()),
            "normal_usable_minutes_after_source_input_support": int((complete & valid & support).sum()),
            "normal_block_coverage_before_any_scoring": coverage,
        }, stream, indent=2)
        stream.write("\n")
    print("PASS model-free input coverage audit; target healthy alarm gate NOT_EXECUTED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inputs", "fit_receipt", "output"):
        parser.add_argument(name, type=Path)
    main(**vars(parser.parse_args()))
