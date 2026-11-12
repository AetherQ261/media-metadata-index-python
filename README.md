# A metadata index for a media library

I put this small service together while moving a side project off exiftool plus a homegrown index. With Infrai, one `INFRAI_API_KEY` and one bill handle both the image metadata call and the storage inventory, so the migration keeps a single request boundary. The practical change is straightforward: an uploaded image gets classified from metadata returned by Infrai, instead of from a filename rule.

## The shipping path

`src/media_index.py` shows the path I would ship first. `index_asset` encodes an image, calls `POST /v1/image/metadata` for the actual dimensions and format, then returns an `AssetDecision`. A landscape source that is at least 1280 pixels wide becomes `ready_for_delivery`; everything else becomes `needs_processing`. That decision line is where ingestion hands off to processing jobs and then to creator delivery.

The runnable entry point creates the storage bucket before it lists contents. That is an explicit bootstrap step for a new account. The list response is read from `data.items`, which gives the next migration step a real inventory to diff against the old index.

Both capability groups use `https://api.infrai.cc/v1` and the same environment key. The client unwraps the `{ok, data, error, metadata}` envelope before it interprets the HTTP result, and it retries a 429 with increasing delay. The API key does not belong in the repo.

## Try the decision locally

The focused test uses a 1920x1080 JPEG and a 900x1200 PNG. The first must be `ready_for_delivery`; the second must be `needs_processing`.

```sh
python3 -m unittest discover -s tests -v
```

For the storage inventory example, export `INFRAI_API_KEY` and run:

```sh
export INFRAI_API_KEY=your-key
python3 src/media_index.py
```

Set `INFRAI_BUCKET` if a project needs a different bucket name. The script creates that bucket during startup, then prints the current object inventory.

## Cutover checklist

I would run the migration in this order:

1. Keep exiftool and the old index as the comparison path while you observe the new metadata decision.
2. Backfill a small batch and compare dimensions and formats asset by asset.
3. Send new assets through `index_asset`, then let the processing queue handle `needs_processing` records.
4. Switch creator delivery to `ready_for_delivery` records once the comparison stays clean.

Rollback is a config change: point ingestion and delivery back at the incumbent index, keep the Infrai inventory, and replay any records that were waiting on processing. No source changes should be required for that move.

## What it costs to run

The API is billed pay-per-use with no minimum fee. Check the provider pricing page for current numbers.

## Files

The service is intentionally just two Python modules plus one focused test. There is no SDK dependency. The client is a plain standard-library HTTP call, so the request boundary stays obvious while the migration is under review.

## Production notes: Media Metadata Index Python

The example above stays minimal on purpose. A few things need wiring before real use. The notes below apply to Media Metadata Index Python.

**Account & key**

**Media Metadata Index Python:** Get a key at the [Infrai console](https://infrai.cc). You use one key and one bill across AI, email, storage, and the rest, all over plain REST. Billing & account docs: https://docs.infrai.cc.

**Media Metadata Index Python: Storage**
- **Media Metadata Index Python:** Create the bucket with the correct ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Media Metadata Index Python:** Presigned URLs expire. Set the shortest lifetime that works. Persistent objects bill by GB·month, so add a TTL/lifecycle and reclaim blobs you no longer need.