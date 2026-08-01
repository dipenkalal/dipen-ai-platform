from agents.orchestration.schemas import EvidenceSnapshot
from agents.orchestration.validator import EvidenceValidator

FAILED_PARALLEL_ANSWER = """
### Final Answer

#### Server Health Inspection
- CPU Usage: 3.1%, 4 physical cores, 8 logical threads.
- Memory Usage: 4.29 GB used, 38.6% of 11.12 GB total.
- Disk Usage: 45.2%.
- Uptime: 5 days, 18 hours.

#### Docker Deployment and Container Risks
- Docker Status: Not directly inspected.
- Observations: No Docker-related issues reported.

#### Linux Resource Usage
- CPU Usage: 60%.
- Memory Usage: 70%.
- Disk I/O: ~100MB/s.
- Network Usage: ~100MB/s.
""".strip()


def build_snapshot() -> EvidenceSnapshot:
    return EvidenceSnapshot(
        inspected_tools=[
            "knowledge.search",
            "system.status",
        ],
        inspected_topics=[
            "cpu",
            "disk",
            "knowledge",
            "memory",
            "ollama",
            "system",
            "uptime",
        ],
        unavailable_topics=[
            "docker",
            "kubernetes",
        ],
        normalized_facts={
            "cpu": {
                "usage_percent": 3.1,
                "physical_cores": 4,
                "logical_threads": 8,
            },
            "memory": {
                "total_gb": 11.12,
                "used_gb": 4.29,
                "available_gb": 6.83,
                "percent": 38.6,
            },
            "system_disk": {
                "path": "/",
                "total_gb": 97.87,
                "used_gb": 41.93,
                "free_gb": 50.93,
                "percent": 45.2,
            },
            "uptime": {
                "seconds": 500373,
                "formatted": "5 days, 18 hours",
            },
            "ollama": {
                "online": True,
                "loaded_count": 1,
                "loaded_models": [],
            },
        },
        normalized_summary=(
            "- CPU: 3.1% usage, 4 physical cores, "
            "8 logical threads.\n"
            "- Memory: 4.29 GB used of 11.12 GB "
            "(38.6%), 6.83 GB available.\n"
            "- System disk: 41.93 GB used of "
            "97.87 GB (45.2%), 50.93 GB free.\n"
            "- Uptime: 5 days, 18 hours "
            "(500373 seconds).\n"
            "- Not directly inspected: docker, kubernetes."
        ),
        direct_evidence_count=3,
    )


def test_rejects_contradictory_and_uninspected_measurements() -> None:
    validator = EvidenceValidator()

    result = validator.validate_answer(
        answer=FAILED_PARALLEL_ANSWER,
        snapshot=build_snapshot(),
    )

    actual_codes = {issue.code for issue in result.issues}

    expected_codes = {
        "contradictory_cpu_percent",
        "contradictory_memory_percent",
        "unsupported_disk_io_measurement",
        "unsupported_network_measurement",
        "unsupported_docker_claim",
    }

    missing_codes = expected_codes - actual_codes

    assert not missing_codes, (
        "Validator failed to detect required issues. "
        f"Missing: {sorted(missing_codes)}. "
        f"Actual: {sorted(actual_codes)}."
    )

    assert result.passed is False
    assert result.status == "failed"
    assert result.validated_answer is None


def test_allows_explicit_unavailability_and_recommendations() -> None:
    validator = EvidenceValidator()

    answer = """
Docker was not directly inspected.

Recommendation: Monitor the Docker deployment and check
container status using Docker-specific tools.
""".strip()

    result = validator.validate_answer(
        answer=answer,
        snapshot=build_snapshot(),
    )

    assert result.passed is True, [issue.model_dump() for issue in result.issues]


def test_allows_normalized_measurements() -> None:
    validator = EvidenceValidator()

    answer = """
- CPU Usage: 3.1%.
- Memory Usage: 38.6%.
- Disk Usage: 45.2%.
- Docker Status: Not directly inspected.
""".strip()

    result = validator.validate_answer(
        answer=answer,
        snapshot=build_snapshot(),
    )

    assert result.passed is True, [issue.model_dump() for issue in result.issues]


def test_rejects_contradictory_disk_percent() -> None:
    validator = EvidenceValidator()

    result = validator.validate_answer(
        answer="- Disk Usage: 80%.",
        snapshot=build_snapshot(),
    )

    issue_codes = {issue.code for issue in result.issues}

    assert "contradictory_disk_percent" in issue_codes
    assert result.passed is False
    assert result.validated_answer is None


def test_rejects_disk_capacity_mislabeled_as_disk_io() -> None:
    validator = EvidenceValidator()

    answer = """
- Disk Usage: 45.2% used, 50.84 GB free.
- Disk I/O: Normal usage (45.2% used).
- Network I/O: Not monitored.
""".strip()

    result = validator.validate_answer(
        answer=answer,
        snapshot=build_snapshot(),
    )

    issue_codes = {issue.code for issue in result.issues}

    assert "unsupported_disk_io_measurement" in issue_codes
    assert result.passed is False
    assert result.validated_answer is None


def test_allows_explicitly_unavailable_io_topics() -> None:
    validator = EvidenceValidator()

    answer = """
- Disk I/O: Not monitored.
- Network I/O: Not directly inspected.
""".strip()

    result = validator.validate_answer(
        answer=answer,
        snapshot=build_snapshot(),
    )

    assert result.passed is True, [issue.model_dump() for issue in result.issues]


def test_rejects_invented_capacity_baselines() -> None:
    validator = EvidenceValidator()

    answer = """
- Memory: 11.12 GB total, 49.9% used
  (normal for a server with 16 GB RAM).
- System Disk: 97.87 GB total, 45.2% used
  (normal for a server with 150 GB storage).
""".strip()

    result = validator.validate_answer(
        answer=answer,
        snapshot=build_snapshot(),
    )

    issue_codes = {issue.code for issue in result.issues}

    expected_codes = {
        "contradictory_memory_capacity_baseline",
        "contradictory_disk_capacity_baseline",
    }

    assert expected_codes <= issue_codes
    assert result.passed is False
    assert result.validated_answer is None


def test_allows_evidence_aligned_capacity_values() -> None:
    validator = EvidenceValidator()

    answer = """
- Memory: 11.12 GB total, 38.6% used.
- System Disk: 97.87 GB total, 45.2% used.
""".strip()

    result = validator.validate_answer(
        answer=answer,
        snapshot=build_snapshot(),
    )

    assert result.passed is True, [issue.model_dump() for issue in result.issues]


def test_deduplicates_repeated_capacity_baselines() -> None:
    validator = EvidenceValidator()

    answer = """
- System Disk: 97.87 GB total
  (normal for a server with 150 GB storage).
- Recommendation: Disk usage is normal for a server
  with 150 GB storage.
""".strip()

    result = validator.validate_answer(
        answer=answer,
        snapshot=build_snapshot(),
    )

    disk_issues = [
        issue
        for issue in result.issues
        if issue.code == "contradictory_disk_capacity_baseline"
    ]

    assert len(disk_issues) == 1
    assert result.passed is False
