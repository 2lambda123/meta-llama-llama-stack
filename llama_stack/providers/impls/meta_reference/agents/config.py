# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.

from llama_stack.providers.utils.kvstore import KVStoreConfig


class MetaReferenceAgentsImplConfig(BaseModel):
    kv_store: KVStoreConfig
