# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.

import os

from llama_stack_client import LlamaStackClient

from pydantic import BaseModel

client = LlamaStackClient(base_url=f"http://localhost:{os.environ['LLAMA_STACK_PORT']}")


class CompletionMessage(BaseModel):
    content: str
    additional_info: str


response = client.inference.chat_completion(
    model_id=os.environ["INFERENCE_MODEL"],
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a haiku about coding"},
    ],
    response_format={
        "type": "json_schema",
        "json_schema": CompletionMessage.model_json_schema(),
    },
)
print(response.completion_message.content)
