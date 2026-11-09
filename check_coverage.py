"""Check that every page of every PDF actually made it into the knowledge base.

A sync can report "Complete" with 0 failed documents and still lose pages, so this
compares the chunks stored in the vector index with the page count of each PDF.
"""
import io
import json
import os
from collections import defaultdict

import boto3
from dotenv import load_dotenv
from pypdf import PdfReader

load_dotenv()

REGION = os.getenv("AWS_REGION", "us-east-2")
KNOWLEDGE_BASE_ID = os.environ["KNOWLEDGE_BASE_ID"]
# Gaps this long or longer get flagged. Short gaps are normal, because a page that's
# mostly a table or image may not start a chunk of its own.
GAP_PAGES = 3


def missing_ranges(pages: set, total: int) -> list:
    ranges, start = [], None
    for page in range(total + 1):
        if page not in pages and page < total:
            start = page if start is None else start
        elif start is not None:
            if page - start >= GAP_PAGES:
                ranges.append(f"{start + 1}-{page}")
            start = None
    return ranges


def main():
    session = boto3.Session(region_name=REGION)
    agent = session.client("bedrock-agent")
    s3 = session.client("s3")

    print("Latest sync per data source:")
    sources = agent.list_data_sources(knowledgeBaseId=KNOWLEDGE_BASE_ID)["dataSourceSummaries"]
    for source in sources:
        jobs = agent.list_ingestion_jobs(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            dataSourceId=source["dataSourceId"],
            sortBy={"attribute": "STARTED_AT", "order": "DESCENDING"},
            maxResults=1,
        )["ingestionJobSummaries"]
        if not jobs:
            print(f"  {source['name']}: never synced")
            continue
        job = agent.get_ingestion_job(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            dataSourceId=source["dataSourceId"],
            ingestionJobId=jobs[0]["ingestionJobId"],
        )["ingestionJob"]
        errors = job.get("failureReasons", [])
        print(f"  {source['name']}: {job['status']}, {len(errors)} error(s)")
        for error in errors:
            print(f"    ! {error}")

    index_arn = agent.get_knowledge_base(knowledgeBaseId=KNOWLEDGE_BASE_ID)["knowledgeBase"][
        "storageConfiguration"]["s3VectorsConfiguration"]["indexArn"]
    vector_bucket, index_name = index_arn.split(":bucket/")[1].split("/index/")

    vectors = session.client("s3vectors")
    pages_by_uri = defaultdict(set)
    chunks_by_uri = defaultdict(int)
    kwargs = {"vectorBucketName": vector_bucket, "indexName": index_name, "returnMetadata": True}
    while True:
        page = vectors.list_vectors(**kwargs)
        for vector in page["vectors"]:
            metadata = vector["metadata"]
            uri = json.loads(metadata["AMAZON_BEDROCK_METADATA"])["source"]["sourceLocation"]
            chunks_by_uri[uri] += 1
            page_number = metadata.get("x-amz-bedrock-kb-document-page-number")
            if page_number is not None:
                pages_by_uri[uri].add(int(float(page_number)))
        if not page.get("nextToken"):
            break
        kwargs["nextToken"] = page["nextToken"]

    print("\nPages stored per document:")
    for uri in sorted(chunks_by_uri):
        bucket, key = uri.removeprefix("s3://").split("/", 1)
        pdf = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        total = len(PdfReader(io.BytesIO(pdf)).pages)
        pages = pages_by_uri[uri]
        covered = len([p for p in pages if p < total])
        gaps = missing_ranges(pages, total)
        print(f"  {key}: {chunks_by_uri[uri]} chunks, {covered} of {total} pages "
              f"({covered / total:.0%})")
        if gaps:
            print(f"    ! missing pages {', '.join(gaps)}")


if __name__ == "__main__":
    main()
