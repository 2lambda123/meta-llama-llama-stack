import pytest
import yaml
from datetime import datetime
from llama_stack.distribution.configure import (
    parse_and_maybe_upgrade_config,
    LLAMA_STACK_RUN_CONFIG_VERSION,
)


@pytest.fixture
def up_to_date_config():
    return yaml.safe_load(
        """
        version: {version}
        image_name: foo
        apis_to_serve: []
        built_at: {built_at}
        models:
          - identifier: model1
            provider_id: provider1
            llama_model: Llama3.1-8B-Instruct
        shields:
          - identifier: shield1
            type: llama_guard
            provider_id: provider1
        memory_banks:
          - identifier: memory1
            type: vector
            provider_id: provider1
            embedding_model: all-MiniLM-L6-v2
            chunk_size_in_tokens: 512
        providers:
          inference:
            - provider_id: provider1
              provider_type: meta-reference
              config: {{}}
          safety:
            - provider_id: provider1
              provider_type: meta-reference
              config:
                llama_guard_shield:
                  model: Llama-Guard-3-1B
                  excluded_categories: []
                  disable_input_check: false
                  disable_output_check: false
                enable_prompt_guard: false
          memory:
            - provider_id: provider1
              provider_type: meta-reference
              config: {{}}
    """.format(
            version=LLAMA_STACK_RUN_CONFIG_VERSION, built_at=datetime.now().isoformat()
        )
    )


@pytest.fixture
def old_config():
    return yaml.safe_load(
        """
        image_name: foo
        built_at: {built_at}
        apis_to_serve: []
        routing_table:
          inference:
            - provider_type: remote::ollama
              config:
                host: localhost
                port: 11434
              routing_key: Llama3.2-1B-Instruct
            - provider_type: meta-reference
              config:
                model: Llama3.1-8B-Instruct
              routing_key: Llama3.1-8B-Instruct
          safety:
            - routing_key: ["shield1", "shield2"]
              provider_type: meta-reference
              config:
                llama_guard_shield:
                  model: Llama-Guard-3-1B
                  excluded_categories: []
                  disable_input_check: false
                  disable_output_check: false
                enable_prompt_guard: false
          memory:
            - routing_key: vector
              provider_type: meta-reference
              config: {{}}
        api_providers:
          telemetry:
            provider_type: noop
            config: {{}}
    """.format(built_at=datetime.now().isoformat())
    )


@pytest.fixture
def invalid_config():
    return yaml.safe_load("""
        routing_table: {}
        api_providers: {}
    """)


def test_parse_and_maybe_upgrade_config_up_to_date(up_to_date_config):
    result = parse_and_maybe_upgrade_config(up_to_date_config)
    assert result.version == LLAMA_STACK_RUN_CONFIG_VERSION
    assert len(result.models) == 1
    assert len(result.shields) == 1
    assert len(result.memory_banks) == 1
    assert "inference" in result.providers


def test_parse_and_maybe_upgrade_config_old_format(old_config):
    result = parse_and_maybe_upgrade_config(old_config)
    assert result.version == LLAMA_STACK_RUN_CONFIG_VERSION
    assert len(result.models) == 2
    assert len(result.shields) == 2
    assert len(result.memory_banks) == 1
    assert all(
        api in result.providers
        for api in ["inference", "safety", "memory", "telemetry"]
    )
    safety_provider = result.providers["safety"][0]
    assert safety_provider.provider_type == "meta-reference"
    assert "llama_guard_shield" in safety_provider.config

    inference_providers = result.providers["inference"]
    assert len(inference_providers) == 2
    assert set(x.provider_id for x in inference_providers) == {
        "remote::ollama-00",
        "meta-reference-01",
    }

    ollama = inference_providers[0]
    assert ollama.provider_type == "remote::ollama"
    assert ollama.config["port"] == 11434


def test_parse_and_maybe_upgrade_config_invalid(invalid_config):
    with pytest.raises(ValueError):
        parse_and_maybe_upgrade_config(invalid_config)
