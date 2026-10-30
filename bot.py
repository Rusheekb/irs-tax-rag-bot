"""Ask the IRS tax knowledge base a question through Amazon Bedrock."""
import os
from pathlib import Path

import boto3
from dotenv import load_dotenv

load_dotenv()

REGION = os.getenv("AWS_REGION", "us-east-2")
KNOWLEDGE_BASE_ID = os.environ["KNOWLEDGE_BASE_ID"]
MODEL_ID = os.getenv("MODEL_ID", "us.amazon.nova-lite-v1:0")
GUARDRAIL_ID = os.environ["GUARDRAIL_ID"]
GUARDRAIL_VERSION = os.getenv("GUARDRAIL_VERSION", "1")
PROMPT = (Path(__file__).parent / "generation_prompt.txt").read_text()


def ask(question: str) -> dict:
    session = boto3.Session(region_name=REGION)
    account = session.client("sts").get_caller_identity()["Account"]
    model_arn = f"arn:aws:bedrock:{REGION}:{account}:inference-profile/{MODEL_ID}"

    response = session.client("bedrock-agent-runtime").retrieve_and_generate(
        input={"text": question},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": KNOWLEDGE_BASE_ID,
                "modelArn": model_arn,
                "retrievalConfiguration": {"vectorSearchConfiguration": {"numberOfResults": 5}},
                "generationConfiguration": {
                    "promptTemplate": {"textPromptTemplate": PROMPT},
                    # The guardrail only runs when it's sent with the request.
                    "guardrailConfiguration": {
                        "guardrailId": GUARDRAIL_ID,
                        "guardrailVersion": GUARDRAIL_VERSION,
                    },
                    "inferenceConfig": {"textInferenceConfig": {"temperature": 0, "maxTokens": 512}},
                },
            },
        },
    )

    sources = []
    for citation in response.get("citations", []):
        for reference in citation.get("retrievedReferences", []):
            uri = reference.get("location", {}).get("s3Location", {}).get("uri", "")
            text = reference.get("content", {}).get("text", "")
            sources.append({"file": uri.rsplit("/", 1)[-1], "text": text})

    return {
        "answer": response["output"]["text"],
        "blocked": response.get("guardrailAction") == "INTERVENED",
        "sources": sources,
    }
