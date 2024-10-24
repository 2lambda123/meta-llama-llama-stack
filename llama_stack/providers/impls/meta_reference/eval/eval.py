# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.
from llama_models.llama3.api.datatypes import *  # noqa: F403

from llama_stack.apis.eval import *  # noqa: F403
from llama_stack.apis.common.job_types import Job
from llama_stack.apis.datasetio import DatasetIO
from llama_stack.apis.datasets import Datasets
from llama_stack.apis.inference import Inference
from llama_stack.apis.scoring import Scoring

from .config import MetaReferenceEvalConfig


class MetaReferenceEvalImpl(Eval):
    def __init__(
        self,
        config: MetaReferenceEvalConfig,
        datasetio_api: DatasetIO,
        datasets_api: Datasets,
        scoring_api: Scoring,
        inference_api: Inference,
    ) -> None:
        self.config = config
        self.datasetio_api = datasetio_api
        self.datasets_api = datasets_api
        self.scoring_api = scoring_api
        self.inference_api = inference_api

        # TODO: assume sync job, will need jobs API for async scheduling
        self.jobs = {}

    async def initialize(self) -> None: ...

    async def shutdown(self) -> None: ...

    async def validate_eval_input_dataset_schema(self, dataset_id: str) -> None:
        dataset_def = await self.datasets_api.get_dataset(dataset_identifier=dataset_id)
        if not dataset_def.dataset_schema or len(dataset_def.dataset_schema) == 0:
            raise ValueError(
                f"Dataset {dataset_id} does not have a schema defined. Please define a schema for the dataset."
            )

        # TODO: we will require user defined message types for ToolResponseMessage or include message.context
        # for now uses basic schema where messages={type: "user", content: "input_query"}
        for required_column in ["expected_answer", "input_query"]:
            if required_column not in dataset_def.dataset_schema:
                raise ValueError(
                    f"Dataset {dataset_id} does not have a '{required_column}' column."
                )
            if dataset_def.dataset_schema[required_column].type != "string":
                raise ValueError(
                    f"Dataset {dataset_id} does not have a '{required_column}' column of type 'string'."
                )

    async def evaluate_batch(
        self,
        dataset_id: str,
        candidate: EvalCandidate,
        scoring_functions: List[str],
    ) -> Job:
        await self.validate_eval_input_dataset_schema(dataset_id=dataset_id)
        all_rows = await self.datasetio_api.get_rows_paginated(
            dataset_id=dataset_id,
            rows_in_page=-1,
        )
        res = await self.evaluate(
            input_rows=all_rows.rows,
            candidate=candidate,
            scoring_functions=scoring_functions,
        )

        job_id = str(len(self.jobs))
        self.jobs[job_id] = res
        return Job(job_id=job_id)

    async def evaluate(
        self,
        input_rows: List[Dict[str, Any]],
        candidate: EvalCandidate,
        scoring_functions: List[str],
    ) -> EvaluateResponse:
        if candidate.type == "agent":
            raise NotImplementedError(
                "Evaluation with generation has not been implemented for agents"
            )
        generations = []
        for x in input_rows:
            input_query = x["input_query"]
            messages = []
            if candidate.system_message:
                messages.append(candidate.system_message)
            messages.append(
                UserMessage(content=input_query),
            )
            response = await self.inference_api.chat_completion(
                model=candidate.model,
                messages=messages,
            )
            generations.append(
                {"generated_answer": response.completion_message.content}
            )

        # scoring with generated_answer
        score_input_rows = [
            input_r | generated_r
            for input_r, generated_r in zip(input_rows, generations)
        ]

        score_response = await self.scoring_api.score(
            input_rows=score_input_rows, scoring_functions=scoring_functions
        )

        return EvaluateResponse(generations=generations, scores=score_response.results)

    async def job_status(self, job_id: str) -> JobStatus:
        if job_id in self.jobs:
            return JobStatus.completed
        else:
            return JobStatus.not_found

    async def job_cancel(self, job_id: str) -> None:
        raise NotImplementedError("Job cancel is not implemented yet")

    async def job_result(self, job_id: str) -> None:
        status = await self.job_status(job_id)
        if status != JobStatus.completed:
            raise ValueError(f"Job is not completed, Status: {status.value}")

        return self.jobs[job_id]
