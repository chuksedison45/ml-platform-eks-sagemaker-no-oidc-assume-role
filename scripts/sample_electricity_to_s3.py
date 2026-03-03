#!/usr/bin/env python3
"""
Create a smaller sample of the ElectricityLoadDiagrams dataset and upload back to S3.

- Downloads the big file from S3 to a temp file
- Reads it in chunks (does NOT load everything into RAM)
- Keeps only:
  - the time column (first column)
  - first N series columns
  - last M rows (tail)

Output is written with the same delimiter/decimal style: sep=';' decimal=','.
"""

from __future__ import annotations
import argparse, os, tempfile
from pathlib import Path

import boto3
import pandas as pd


def parse_s3_uri(uri: str):
    assert uri.startswith("s3://")
    b, k = uri[5:].split("/", 1)
    return b, k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True)
    ap.add_argument("--input-s3", required=True, help="s3://.../LD2011_2014.txt")
    ap.add_argument("--output-s3", required=True, help="s3://.../LD2011_2014_sample.txt")
    ap.add_argument("--max-series", type=int, default=10)
    ap.add_argument("--tail-rows", type=int, default=3000)
    ap.add_argument("--chunksize", type=int, default=50000)
    args = ap.parse_args()

    boto_sess = boto3.session.Session(region_name=args.region)
    s3 = boto_sess.client("s3")

    in_bucket, in_key = parse_s3_uri(args.input_s3)
    out_bucket, out_key = parse_s3_uri(args.output_s3)

    with tempfile.TemporaryDirectory() as td:
        local_in = Path(td) / "LD2011_2014.txt"
        local_out = Path(td) / "LD2011_2014_sample.txt"

        print(f"Downloading {args.input_s3} → {local_in}")
        s3.download_file(in_bucket, in_key, str(local_in))

        # Read header to decide which columns to keep
        with open(local_in, "r", encoding="utf-8", errors="ignore") as f:
            header = f.readline().strip()
        cols = header.split(";")
        # Keep first column (time) + first N series cols
        usecols = [cols[0]] + cols[1:1 + args.max_series]
        print(f"Keeping columns: {len(usecols)} (time + {args.max_series} series)")

        tail_df = None
        for chunk in pd.read_csv(
            local_in,
            sep=";",
            decimal=",",
            usecols=usecols,
            chunksize=args.chunksize,
        ):
            if tail_df is None:
                tail_df = chunk
            else:
                tail_df = pd.concat([tail_df, chunk], ignore_index=True)
            if len(tail_df) > args.tail_rows:
                tail_df = tail_df.iloc[-args.tail_rows:].reset_index(drop=True)

        print(f"Writing sample rows: {len(tail_df)} → {local_out}")
        tail_df.to_csv(local_out, sep=";", index=False)

        print(f"Uploading sample → {args.output_s3}")
        s3.upload_file(str(local_out), out_bucket, out_key)

    print("Done.")


if __name__ == "__main__":
    main()
