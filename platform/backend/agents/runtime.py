from agents.executor import agent_executor
from agents.runtime_instrumentation import (
    InstrumentedAgentExecutor,
    RuntimeInstrumentation,
)
from agents.truth_service import agent_truth_service

runtime_instrumentation = RuntimeInstrumentation(
    agent_truth_service
)

instrumented_agent_executor = InstrumentedAgentExecutor(
    agent_executor,
    runtime_instrumentation,
)
