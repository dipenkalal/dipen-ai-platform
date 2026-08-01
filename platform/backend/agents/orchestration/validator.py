import re
from typing import Any

from agents.orchestration.schemas import (
    EvidenceSnapshot,
    EvidenceValidationIssue,
    EvidenceValidationResult,
    OrchestrationTaskResult,
)

DOCKER_ASSERTION_PATTERNS: tuple[
    re.Pattern[str],
    ...,
] = (
    re.compile(
        r"\bno docker containers?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdocker (?:is|appears|looks) "
        r"(?:healthy|online|offline|running|stopped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdocker daemon "
        r"(?:is|appears|looks|activity)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bno action required "
        r"(?:for|regarding) docker\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bno docker "
        r"(?:risk|risks|issue|issues|problem|problems)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdocker deployment "
        r"(?:is|appears|looks) "
        r"(?:healthy|safe|stable)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bno docker deployment "
        r"risks? detected\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bno docker(?:-|\s+)related\s+"
        r"(?:risks?|issues?|problems?)\s+"
        r"(?:were\s+)?reported\b",
        re.IGNORECASE,
    ),
)


RAW_SIZE_WITH_MB_PATTERN = re.compile(
    r"\b(?P<value>\d{7,})"
    r"(?:\.\d+)?\s*MB\b",
    re.IGNORECASE,
)

DOCKER_TOPIC_PATTERN = re.compile(
    r"\b(?:docker|containers?|daemon|deployment)\b",
    re.IGNORECASE,
)

DOCKER_STATE_PATTERN = re.compile(
    r"\b(?:all\s+)?(?:running|healthy|unhealthy|online|offline|"
    r"stopped|safe|stable|risk[- ]?free|no\s+(?:critical\s+)?"
    r"(?:errors?|issues?|risks?|problems?))\b",
    re.IGNORECASE,
)

UNSUPPORTED_MODEL_METADATA_PATTERNS: tuple[
    re.Pattern[str],
    ...,
] = (
    re.compile(
        r"\b\d+(?:\.\d+)?\s*[bB]\s+parameters?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:model\s+(?:is\s+)?)?not\s+expired\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwithin acceptable limits\b",
        re.IGNORECASE,
    ),
)

PERCENT_VALUE_PATTERN = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)

CPU_PERCENT_LINE_PATTERN = re.compile(
    r"\bcpu(?:\s+usage)?\b",
    re.IGNORECASE,
)

MEMORY_PERCENT_LINE_PATTERN = re.compile(
    r"\b(?:memory|ram)(?:\s+usage)?\b",
    re.IGNORECASE,
)

DISK_PERCENT_LINE_PATTERN = re.compile(
    r"\b(?:system\s+)?disk(?:\s+usage)?\b",
    re.IGNORECASE,
)

DISK_IO_MEASUREMENT_PATTERN = re.compile(
    r"\bdisk\s*(?:i/o|io|throughput)\b"
    r"[^\n]*?"
    r"(?:"
    r"\b\d+(?:\.\d+)?\s*%"
    r"|"
    r"\b\d+(?:\.\d+)?\s*"
    r"(?:[kmgt]?i?b|bytes?)\s*"
    r"(?:/s|ps)\b"
    r")",
    re.IGNORECASE,
)

NETWORK_MEASUREMENT_PATTERN = re.compile(
    r"\b(?:network(?:\s+(?:usage|throughput|bandwidth))?"
    r"|bandwidth)\b"
    r"[^\n]*?"
    r"\b\d+(?:\.\d+)?\s*"
    r"(?:[kmgt]?i?b|bytes?|[kmgt]?bits?)\s*"
    r"(?:/s|ps)\b",
    re.IGNORECASE,
)

MEMORY_CAPACITY_BASELINE_PATTERN = re.compile(
    r"\bnormal\s+for\s+(?:a\s+)?server\s+with\s+"
    r"(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>GB|GiB)\s+"
    r"(?:RAM|memory)\b",
    re.IGNORECASE,
)

DISK_CAPACITY_BASELINE_PATTERN = re.compile(
    r"\bnormal\s+for\s+(?:a\s+)?server\s+with\s+"
    r"(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>GB|GiB)\s+"
    r"(?:storage|disk)\b",
    re.IGNORECASE,
)

MEASUREMENT_TOLERANCE = 0.5
CAPACITY_BASELINE_TOLERANCE_RATIO = 0.05
CAPACITY_BASELINE_MIN_TOLERANCE_GB = 0.5

NON_OBSERVATION_PREFIXES: tuple[str, ...] = (
    "recommendation",
    "recommended",
    "monitor ",
    "check ",
    "verify ",
    "confirm ",
    "use ",
    "inspect ",
    "review ",
    "consider ",
    "target ",
    "threshold ",
)


class EvidenceValidator:
    def build_snapshot(
        self,
        task_results: list[OrchestrationTaskResult],
    ) -> EvidenceSnapshot:
        inspected_tools: set[str] = set()
        inspected_topics: set[str] = set()

        normalized_facts: dict[
            str,
            Any,
        ] = {}

        evidence_count = 0

        for result in task_results:
            for step in result.steps:
                if step.type != "tool" or not step.success or not step.tool_id:
                    continue

                inspected_tools.add(
                    step.tool_id,
                )

                evidence_count += 1

                if step.tool_id == "system.status":
                    inspected_topics.update(
                        {
                            "system",
                            "cpu",
                            "memory",
                            "disk",
                            "uptime",
                            "ollama",
                        }
                    )

                    self._extract_system_status(
                        output=step.output,
                        normalized_facts=(normalized_facts),
                    )

                if step.tool_id.startswith(
                    "knowledge.",
                ):
                    inspected_topics.add(
                        "knowledge",
                    )

                if step.tool_id.startswith(
                    "docker.",
                ):
                    inspected_topics.add(
                        "docker",
                    )

                if step.tool_id.startswith(
                    "kubernetes.",
                ):
                    inspected_topics.add(
                        "kubernetes",
                    )

        unavailable_topics: list[str] = []

        if "docker" not in inspected_topics:
            unavailable_topics.append(
                "docker",
            )

        if "kubernetes" not in inspected_topics:
            unavailable_topics.append(
                "kubernetes",
            )

        summary = self._build_normalized_summary(
            normalized_facts=normalized_facts,
            inspected_topics=inspected_topics,
            unavailable_topics=(unavailable_topics),
        )

        return EvidenceSnapshot(
            inspected_tools=sorted(
                inspected_tools,
            ),
            inspected_topics=sorted(
                inspected_topics,
            ),
            unavailable_topics=(unavailable_topics),
            normalized_facts=normalized_facts,
            normalized_summary=summary,
            direct_evidence_count=(evidence_count),
        )

    def validate_answer(
        self,
        *,
        answer: str,
        snapshot: EvidenceSnapshot,
    ) -> EvidenceValidationResult:
        issues: list[EvidenceValidationIssue] = []

        if "docker" in snapshot.unavailable_topics:
            issues.extend(
                self._find_unsupported_docker_claims(
                    answer,
                )
            )

            issues.extend(
                self._find_docker_state_lines(
                    answer,
                )
            )

        issues.extend(
            self._find_contradictory_percentages(
                answer=answer,
                snapshot=snapshot,
            )
        )

        issues.extend(
            self._find_contradictory_capacity_baselines(
                answer=answer,
                snapshot=snapshot,
            )
        )

        issues.extend(
            self._find_uninspected_measurements(
                answer=answer,
                snapshot=snapshot,
            )
        )

        issues.extend(
            self._find_unit_issues(
                answer,
            )
        )

        issues.extend(
            self._find_unsupported_model_metadata(
                answer,
            )
        )

        error_count = sum(issue.severity == "error" for issue in issues)

        warning_count = sum(issue.severity == "warning" for issue in issues)

        passed = error_count == 0

        if error_count:
            status = "failed"
        elif warning_count:
            status = "warning"
        else:
            status = "passed"

        confidence = max(
            0.0,
            min(
                1.0,
                1.0 - error_count * 0.25 - warning_count * 0.10,
            ),
        )

        return EvidenceValidationResult(
            status=status,
            passed=passed,
            corrected=False,
            confidence=round(
                confidence,
                2,
            ),
            issues=issues,
            snapshot=snapshot,
            original_answer=answer,
            validated_answer=(answer if passed else None),
        )

    def mark_corrected(
        self,
        *,
        original: EvidenceValidationResult,
        corrected_answer: str,
        corrected_validation: (EvidenceValidationResult),
    ) -> EvidenceValidationResult:
        return EvidenceValidationResult(
            status=(
                "corrected"
                if corrected_validation.passed
                else corrected_validation.status
            ),
            passed=corrected_validation.passed,
            corrected=(corrected_validation.passed),
            confidence=(corrected_validation.confidence),
            issues=corrected_validation.issues,
            snapshot=original.snapshot,
            original_answer=(original.original_answer),
            validated_answer=(
                corrected_answer if corrected_validation.passed else None
            ),
        )

    def build_repair_instructions(
        self,
        validation: EvidenceValidationResult,
    ) -> str:
        issue_lines = [
            (f"- [{issue.severity.upper()}] {issue.code}: {issue.message}")
            for issue in validation.issues
        ]

        return "\n".join(
            [
                "VALIDATION FAILED.",
                "",
                "Rewrite the answer and correct every issue below:",
                *issue_lines,
                "",
                "MANDATORY EVIDENCE RULES:",
                (
                    "- Do not state Docker container, "
                    "daemon, deployment, or health "
                    "status because no Docker-specific "
                    "tool evidence was collected."
                ),
                ("- State clearly that Docker was not directly inspected."),
                (
                    "- Treat model size values from "
                    "tool output as bytes unless the "
                    "normalized evidence says otherwise."
                ),
                ("- Use the normalized evidence summary exactly for measured facts."),
                (
                    "- Remove CPU, memory, disk, disk-I/O, "
                    "and network measurements that do not "
                    "match normalized direct evidence."
                ),
                (
                    "- Do not provide numeric disk-I/O or "
                    "network measurements unless those "
                    "topics were directly inspected."
                ),
                (
                    "- Disk capacity usage is not disk-I/O. "
                    "Never relabel a disk-used percentage or "
                    "free-space value as disk-I/O."
                ),
                (
                    "- Do not invent comparison-machine "
                    "capacities such as a different RAM or "
                    "storage size. Use only capacities from "
                    "normalized direct evidence."
                ),
                "",
                "NORMALIZED EVIDENCE:",
                validation.snapshot.normalized_summary,
            ]
        )

    @staticmethod
    def _extract_system_status(
        *,
        output: Any,
        normalized_facts: dict[
            str,
            Any,
        ],
    ) -> None:
        if not isinstance(
            output,
            dict,
        ):
            return

        system = output.get(
            "system",
            {},
        )

        if isinstance(system, dict):
            cpu = system.get(
                "cpu",
                {},
            )

            memory = system.get(
                "memory",
                {},
            )

            uptime = system.get(
                "uptime",
                {},
            )

            disks = system.get(
                "disks",
                {},
            )

            if isinstance(cpu, dict):
                normalized_facts["cpu"] = {
                    "usage_percent": (cpu.get("usage_percent")),
                    "physical_cores": (cpu.get("physical_cores")),
                    "logical_threads": (cpu.get("logical_threads")),
                }

            if isinstance(
                memory,
                dict,
            ):
                normalized_facts["memory"] = {
                    "total_gb": memory.get("total_gb"),
                    "used_gb": memory.get("used_gb"),
                    "available_gb": (memory.get("available_gb")),
                    "percent": memory.get("percent"),
                }

            if isinstance(
                uptime,
                dict,
            ):
                normalized_facts["uptime"] = {
                    "seconds": uptime.get("seconds"),
                    "formatted": uptime.get("formatted"),
                }

            if isinstance(
                disks,
                dict,
            ):
                system_disk = disks.get(
                    "system",
                    {},
                )

                if isinstance(
                    system_disk,
                    dict,
                ):
                    normalized_facts["system_disk"] = {
                        "path": (system_disk.get("path")),
                        "total_gb": (system_disk.get("total_gb")),
                        "used_gb": (system_disk.get("used_gb")),
                        "free_gb": (system_disk.get("free_gb")),
                        "percent": (system_disk.get("percent")),
                    }

        ollama = output.get(
            "ollama",
            {},
        )

        if not isinstance(
            ollama,
            dict,
        ):
            return

        loaded_models = ollama.get(
            "loaded_models",
            [],
        )

        normalized_models: list[dict[str, Any]] = []

        if isinstance(
            loaded_models,
            list,
        ):
            for model in loaded_models:
                if not isinstance(
                    model,
                    dict,
                ):
                    continue

                raw_size = model.get(
                    "size",
                )

                raw_vram = model.get(
                    "size_vram",
                )

                normalized_models.append(
                    {
                        "name": model.get("name"),
                        "size_bytes": (raw_size),
                        "size_human": (EvidenceValidator._format_bytes(raw_size)),
                        "vram_bytes": (raw_vram),
                        "vram_human": (EvidenceValidator._format_bytes(raw_vram)),
                        "expires_at": (model.get("expires_at")),
                    }
                )

        normalized_facts["ollama"] = {
            "online": ollama.get("online"),
            "loaded_count": ollama.get("loaded_count"),
            "loaded_models": (normalized_models),
        }

    @staticmethod
    def _build_normalized_summary(
        *,
        normalized_facts: dict[
            str,
            Any,
        ],
        inspected_topics: set[str],
        unavailable_topics: list[str],
    ) -> str:
        lines: list[str] = []

        cpu = normalized_facts.get(
            "cpu",
        )

        if isinstance(cpu, dict):
            lines.append(
                "- CPU: "
                f"{cpu.get('usage_percent')}% usage, "
                f"{cpu.get('physical_cores')} "
                "physical cores, "
                f"{cpu.get('logical_threads')} "
                "logical threads."
            )

        memory = normalized_facts.get(
            "memory",
        )

        if isinstance(
            memory,
            dict,
        ):
            lines.append(
                "- Memory: "
                f"{memory.get('used_gb')} GB used "
                f"of {memory.get('total_gb')} GB "
                f"({memory.get('percent')}%), "
                f"{memory.get('available_gb')} GB "
                "available."
            )

        disk = normalized_facts.get(
            "system_disk",
        )

        if isinstance(
            disk,
            dict,
        ):
            lines.append(
                "- System disk: "
                f"{disk.get('used_gb')} GB used "
                f"of {disk.get('total_gb')} GB "
                f"({disk.get('percent')}%), "
                f"{disk.get('free_gb')} GB free."
            )

        uptime = normalized_facts.get(
            "uptime",
        )

        if isinstance(
            uptime,
            dict,
        ):
            lines.append(
                "- Uptime: "
                f"{uptime.get('formatted')} "
                f"({uptime.get('seconds')} seconds)."
            )

        ollama = normalized_facts.get(
            "ollama",
        )

        if isinstance(
            ollama,
            dict,
        ):
            lines.append(
                "- Ollama: "
                f"online={ollama.get('online')}, "
                "loaded models="
                f"{ollama.get('loaded_count')}."
            )

            models = ollama.get(
                "loaded_models",
                [],
            )

            if isinstance(
                models,
                list,
            ):
                for model in models:
                    if not isinstance(
                        model,
                        dict,
                    ):
                        continue

                    lines.append(
                        "- Ollama model: "
                        f"{model.get('name')}, "
                        f"size={model.get('size_human')} "
                        f"({model.get('size_bytes')} bytes), "
                        "VRAM="
                        f"{model.get('vram_human')}."
                    )

        lines.append(
            "- Inspected topics: "
            + (", ".join(sorted(inspected_topics)) or "none")
            + "."
        )

        if unavailable_topics:
            lines.append(
                "- Not directly inspected: " + ", ".join(unavailable_topics) + "."
            )

        return "\n".join(
            lines,
        )

    @staticmethod
    def _is_non_observation_line(
        line: str,
    ) -> bool:
        normalized_line = line.strip().lstrip("#*-0123456789. ").strip()

        normalized_lower = normalized_line.lower()

        return (
            not normalized_line
            or "`" in normalized_line
            or normalized_lower.startswith(NON_OBSERVATION_PREFIXES)
        )

    @staticmethod
    def _find_contradictory_percentages(
        *,
        answer: str,
        snapshot: EvidenceSnapshot,
    ) -> list[EvidenceValidationIssue]:
        issues: list[EvidenceValidationIssue] = []

        metric_specs = (
            (
                "cpu",
                "usage_percent",
                CPU_PERCENT_LINE_PATTERN,
                "contradictory_cpu_percent",
                "CPU",
            ),
            (
                "memory",
                "percent",
                MEMORY_PERCENT_LINE_PATTERN,
                "contradictory_memory_percent",
                "memory",
            ),
            (
                "system_disk",
                "percent",
                DISK_PERCENT_LINE_PATTERN,
                "contradictory_disk_percent",
                "system disk",
            ),
        )

        for (
            fact_name,
            value_name,
            line_pattern,
            issue_code,
            display_name,
        ) in metric_specs:
            facts = snapshot.normalized_facts.get(
                fact_name,
            )

            if not isinstance(
                facts,
                dict,
            ):
                continue

            expected_value = facts.get(
                value_name,
            )

            if isinstance(expected_value, bool) or not isinstance(
                expected_value,
                (
                    int,
                    float,
                ),
            ):
                continue

            expected = float(
                expected_value,
            )

            for raw_line in answer.splitlines():
                line = raw_line.strip()

                if EvidenceValidator._is_non_observation_line(
                    line,
                ):
                    continue

                normalized_line = line.lstrip("#*-0123456789. ").strip()

                if not line_pattern.search(
                    normalized_line,
                ):
                    continue

                for match in PERCENT_VALUE_PATTERN.finditer(
                    normalized_line,
                ):
                    observed = float(
                        match.group(
                            "value",
                        )
                    )

                    if (
                        abs(
                            observed - expected,
                        )
                        <= MEASUREMENT_TOLERANCE
                    ):
                        continue

                    issues.append(
                        EvidenceValidationIssue(
                            code=issue_code,
                            severity="error",
                            message=(
                                f"The answer reports {display_name} "
                                f"at {observed:g}%, but normalized "
                                f"direct evidence reports "
                                f"{expected:g}%."
                            ),
                            claim=line,
                            topic=fact_name,
                        )
                    )

                    break

        return issues

    @staticmethod
    def _find_contradictory_capacity_baselines(
        *,
        answer: str,
        snapshot: EvidenceSnapshot,
    ) -> list[EvidenceValidationIssue]:
        issues: list[EvidenceValidationIssue] = []
        seen_claims: set[tuple[str, str]] = set()

        capacity_specs = (
            (
                "memory",
                "total_gb",
                MEMORY_CAPACITY_BASELINE_PATTERN,
                "contradictory_memory_capacity_baseline",
                "memory",
            ),
            (
                "system_disk",
                "total_gb",
                DISK_CAPACITY_BASELINE_PATTERN,
                "contradictory_disk_capacity_baseline",
                "system disk",
            ),
        )

        for (
            fact_name,
            value_name,
            pattern,
            issue_code,
            display_name,
        ) in capacity_specs:
            facts = snapshot.normalized_facts.get(
                fact_name,
            )

            if not isinstance(
                facts,
                dict,
            ):
                continue

            expected_value = facts.get(
                value_name,
            )

            if isinstance(expected_value, bool) or not isinstance(
                expected_value,
                (
                    int,
                    float,
                ),
            ):
                continue

            expected = float(
                expected_value,
            )

            tolerance = max(
                CAPACITY_BASELINE_MIN_TOLERANCE_GB,
                abs(expected) * CAPACITY_BASELINE_TOLERANCE_RATIO,
            )

            for match in pattern.finditer(
                answer,
            ):
                observed = float(
                    match.group(
                        "value",
                    )
                )

                if (
                    abs(
                        observed - expected,
                    )
                    <= tolerance
                ):
                    continue

                claim = match.group(0)
                claim_key = (
                    issue_code,
                    " ".join(claim.lower().split()),
                )

                if claim_key in seen_claims:
                    continue

                seen_claims.add(
                    claim_key,
                )

                issues.append(
                    EvidenceValidationIssue(
                        code=issue_code,
                        severity="error",
                        message=(
                            f"The answer compares {display_name} "
                            f"against an unsupported "
                            f"{observed:g} "
                            f"{match.group('unit')} baseline, "
                            "while normalized direct evidence "
                            f"reports {expected:g} GB."
                        ),
                        claim=claim,
                        topic=fact_name,
                    )
                )

        return issues

    @staticmethod
    def _find_uninspected_measurements(
        *,
        answer: str,
        snapshot: EvidenceSnapshot,
    ) -> list[EvidenceValidationIssue]:
        issues: list[EvidenceValidationIssue] = []

        measurement_specs = (
            (
                "disk_io",
                DISK_IO_MEASUREMENT_PATTERN,
                "unsupported_disk_io_measurement",
                "disk-I/O",
            ),
            (
                "network",
                NETWORK_MEASUREMENT_PATTERN,
                "unsupported_network_measurement",
                "network",
            ),
        )

        inspected_topics = set(
            snapshot.inspected_topics,
        )

        for raw_line in answer.splitlines():
            line = raw_line.strip()

            if EvidenceValidator._is_non_observation_line(
                line,
            ):
                continue

            normalized_line = line.lstrip("#*-0123456789. ").strip()

            for (
                topic,
                pattern,
                issue_code,
                display_name,
            ) in measurement_specs:
                if topic in inspected_topics:
                    continue

                match = pattern.search(
                    normalized_line,
                )

                if not match:
                    continue

                issues.append(
                    EvidenceValidationIssue(
                        code=issue_code,
                        severity="error",
                        message=(
                            f"The answer provides a numeric "
                            f"{display_name} measurement even "
                            "though that topic was not directly "
                            "inspected."
                        ),
                        claim=line,
                        topic=topic,
                    )
                )

        return issues

    @staticmethod
    def _find_unsupported_docker_claims(
        answer: str,
    ) -> list[EvidenceValidationIssue]:
        issues: list[EvidenceValidationIssue] = []

        for pattern in DOCKER_ASSERTION_PATTERNS:
            match = pattern.search(
                answer,
            )

            if not match:
                continue

            issues.append(
                EvidenceValidationIssue(
                    code=("unsupported_docker_claim"),
                    severity="error",
                    message=(
                        "The answer asserts Docker "
                        "state without Docker-specific "
                        "tool evidence."
                    ),
                    claim=match.group(0),
                    topic="docker",
                )
            )

        return issues

    @staticmethod
    def _find_docker_state_lines(
        answer: str,
    ) -> list[EvidenceValidationIssue]:
        issues: list[EvidenceValidationIssue] = []

        recommendation_prefixes = (
            "run ",
            "check ",
            "verify ",
            "confirm ",
            "use ",
            "inspect ",
            "review ",
            "monitor ",
            "consider ",
        )

        for raw_line in answer.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            normalized_line = line.lstrip("#*-0123456789. ").strip()

            normalized_lower = normalized_line.lower()

            # Commands and recommendations are not
            # observations about current Docker state.
            if (
                normalized_lower.startswith(recommendation_prefixes)
                or "`" in normalized_line
            ):
                continue

            # A Docker state claim must mention both
            # Docker/container context and a state.
            if not DOCKER_TOPIC_PATTERN.search(normalized_line):
                continue

            if not DOCKER_STATE_PATTERN.search(normalized_line):
                continue

            issues.append(
                EvidenceValidationIssue(
                    code=("unsupported_docker_state"),
                    severity="error",
                    message=(
                        "The answer states Docker or "
                        "container status even though "
                        "Docker was not directly inspected."
                    ),
                    claim=line,
                    topic="docker",
                )
            )

        return issues

    @staticmethod
    def _find_unsupported_model_metadata(
        answer: str,
    ) -> list[EvidenceValidationIssue]:
        issues: list[EvidenceValidationIssue] = []

        for pattern in UNSUPPORTED_MODEL_METADATA_PATTERNS:
            match = pattern.search(
                answer,
            )

            if not match:
                continue

            issues.append(
                EvidenceValidationIssue(
                    code=("unsupported_model_metadata"),
                    severity="error",
                    message=(
                        "The answer states model metadata "
                        "that was not supplied by direct "
                        "tool evidence."
                    ),
                    claim=match.group(0),
                    topic="ollama",
                )
            )

        return issues

    @staticmethod
    def _find_unit_issues(
        answer: str,
    ) -> list[EvidenceValidationIssue]:
        issues: list[EvidenceValidationIssue] = []

        for match in RAW_SIZE_WITH_MB_PATTERN.finditer(answer):
            issues.append(
                EvidenceValidationIssue(
                    code=("suspicious_size_unit"),
                    severity="error",
                    message=(
                        "A large raw byte value appears to have been labelled as MB."
                    ),
                    claim=match.group(0),
                    topic="units",
                )
            )

        return issues

    @staticmethod
    def _format_bytes(
        value: Any,
    ) -> str:
        try:
            size = float(value)
        except (
            TypeError,
            ValueError,
        ):
            return "unknown"

        if size < 0:
            return "unknown"

        units = (
            "B",
            "KiB",
            "MiB",
            "GiB",
            "TiB",
        )

        unit_index = 0

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"

        return f"{size:.2f} {units[unit_index]}"


evidence_validator = EvidenceValidator()
