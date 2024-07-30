# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.

import asyncio
import json
from typing import AsyncGenerator

import fire
import httpx
from termcolor import cprint

from .api import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionResponseStreamChunk,
    CompletionRequest,
    Inference,
    InstructModel,
    UserMessage,
)
from .event_logger import EventLogger


class InferenceClient(Inference):
    def __init__(self, base_url: str):
        print(f"Initializing client for {base_url}")
        self.base_url = base_url

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def completion(self, request: CompletionRequest) -> AsyncGenerator:
        raise NotImplementedError()

    async def chat_completion(self, request: ChatCompletionRequest) -> AsyncGenerator:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/inference/chat_completion",
                data=request.json(),
                headers={"Content-Type": "application/json"},
                timeout=20,
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data = line[len("data: ") :]
                        try:
                            if request.stream:
                                yield ChatCompletionResponseStreamChunk(**json.loads(data))
                            else:
                                yield ChatCompletionResponse(**json.loads(data))
                        except Exception as e:
                            print(data)
                            print(f"Error with parsing or validation: {e}")


async def run_main(host: str, port: int, stream: bool):
    client = InferenceClient(f"http://{host}:{port}")

    message = UserMessage(content="hello world, help me out here")
    cprint(f"User>{message.content}", "green")
    iterator = client.chat_completion(
        ChatCompletionRequest(
            model=InstructModel.llama3_8b_chat,
            messages=[message],
            stream=stream,
        )
    )
    async for log in EventLogger().log(iterator):
        log.print()


def main(host: str, port: int, stream: bool = True):
    asyncio.run(run_main(host, port, stream))


if __name__ == "__main__":
    fire.Fire(main)
