\
#!/usr/bin/env python3
"""
Upload project datasets to S3 (raw layer).

Datasets:
- Fraud: IEEE-CIS Fraud Detection (Kaggle competition)
- Recs: MovieLens (100k/1m/25m) from GroupLens
- Forecast: ElectricityLoadDiagrams20112014 (UCI)

Usage:
  python3 scripts/upload_datasets_to_s3.py --bucket <bucket> --prefix datasets/raw --movielens 100k --download-uci --download-kaggle

Requirements:
  pip install boto3 requests tqdm kaggle

Kaggle auth:
  - Create ~/.kaggle/kaggle.json, OR
  - Export KAGGLE_USERNAME and KAGGLE_KEY
"""
from __future__ import annotations

import argparse
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import boto3
import requests
from tqdm import tqdm


MOVIELENS_URLS = {
    "100k": "https://files.grouplens.org/datasets/movielens/ml-100k.zip",
    "1m": "https://files.grouplens.org/datasets/movielens/ml-1m.zip",
    "25m": "https://files.grouplens.org/datasets/movielens/ml-25m.zip",
}
UCI_ELECTRICITY_ZIP = "https://archive.ics.uci.edu/static/public/321/electricityloaddiagrams20112014.zip"  # UCI download button


def download_file(url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", "0") or 0)
        with open(out_path, "wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc=f"Downloading {out_path.name}") as pbar:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))


def s3_upload(local_path: Path, bucket: str, key: str, s3=None) -> None:
    s3 = s3 or boto3.client("s3")
    print(f"Uploading s3://{bucket}/{key}")
    s3.upload_file(str(local_path), bucket, key)


def maybe_unzip_and_upload(zip_path: Path, bucket: str, prefix: str, s3) -> None:
    """Uploads the zip and also uploads extracted contents under prefix/extracted/."""
    s3_upload(zip_path, bucket, f"{prefix}/{zip_path.name}", s3=s3)

    extract_dir = zip_path.parent / f"extract_{zip_path.stem}"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)

    for p in extract_dir.rglob("*"):
        if p.is_file():
            rel = p.relative_to(extract_dir)
            s3_key = f"{prefix}/extracted/{zip_path.stem}/{rel.as_posix()}"
            s3_upload(p, bucket, s3_key, s3=s3)


def download_kaggle_ieee(tmp: Path) -> Path:
    """Download Kaggle IEEE-CIS Fraud Detection competition files to tmp and return path to zip."""
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except Exception as e:
        raise RuntimeError("Missing kaggle package. Install with: pip install kaggle") from e

    api = KaggleApi()
    api.authenticate()

    # Kaggle returns a zip containing multiple CSVs
    print("Downloading Kaggle competition: ieee-fraud-detection")
    api.competition_download_files("ieee-fraud-detection", path=str(tmp), quiet=False)
    zip_path = tmp / "ieee-fraud-detection.zip"
    if not zip_path.exists():
        # Kaggle sometimes names with competition slug
        candidates = list(tmp.glob("*.zip"))
        if candidates:
            return candidates[0]
        raise FileNotFoundError("Could not find downloaded Kaggle zip in temp directory.")
    return zip_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", required=True, help="S3 bucket for datasets (raw layer).")
    ap.add_argument("--prefix", default="datasets/raw", help="S3 prefix, e.g. datasets/raw")
    ap.add_argument("--region", default=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-west-2")
    ap.add_argument("--movielens", choices=["100k", "1m", "25m"], default="100k", help="MovieLens size to download/upload.")
    ap.add_argument("--download-kaggle", action="store_true", help="Download Kaggle IEEE-CIS Fraud Detection (requires Kaggle auth).")
    ap.add_argument("--download-uci", action="store_true", help="Download UCI ElectricityLoadDiagrams20112014.")
    ap.add_argument("--extract", action="store_true", help="Also upload extracted files under prefix/extracted/.")
    args = ap.parse_args()

    session = boto3.session.Session(region_name=args.region)
    s3 = session.client("s3")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # MovieLens
        ml_url = MOVIELENS_URLS[args.movielens]
        ml_zip = tmp / f"movielens_{args.movielens}.zip"
        download_file(ml_url, ml_zip)
        if args.extract:
            maybe_unzip_and_upload(ml_zip, args.bucket, f"{args.prefix}/recs/movielens/{args.movielens}", s3=s3)
        else:
            s3_upload(ml_zip, args.bucket, f"{args.prefix}/recs/movielens/{args.movielens}/{ml_zip.name}", s3=s3)

        # UCI electricity
        if args.download_uci:
            uci_zip = tmp / "electricityloaddiagrams20112014.zip"
            download_file(UCI_ELECTRICITY_ZIP, uci_zip)
            if args.extract:
                maybe_unzip_and_upload(uci_zip, args.bucket, f"{args.prefix}/forecast/electricity", s3=s3)
            else:
                s3_upload(uci_zip, args.bucket, f"{args.prefix}/forecast/electricity/{uci_zip.name}", s3=s3)

        # Kaggle IEEE-CIS
        if args.download_kaggle:
            try:
                kag_zip = download_kaggle_ieee(tmp)
            except Exception as e:
                print("\nERROR: Kaggle download failed.")
                print("Fix by creating ~/.kaggle/kaggle.json OR exporting KAGGLE_USERNAME and KAGGLE_KEY.")
                raise

            if args.extract:
                maybe_unzip_and_upload(kag_zip, args.bucket, f"{args.prefix}/fraud/ieee-cis", s3=s3)
            else:
                s3_upload(kag_zip, args.bucket, f"{args.prefix}/fraud/ieee-cis/{kag_zip.name}", s3=s3)

    print("\nDone.")


if __name__ == "__main__":
    main()
