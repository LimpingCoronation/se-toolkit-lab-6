#!/usr/bin/env python3
"""Regression tests for the documentation agent (Task 2).

These tests verify that the agent correctly uses tools to answer questions
about the project documentation.

Usage:
    uv run pytest tests/test_agent.py -v
"""

import json
import subprocess
import sys
from pathlib import Path


def run_agent(question: str, timeout: int = 120) -> dict:
    """Run the agent with a question and return the parsed JSON output.

    Args:
        question: The question to ask the agent
        timeout: Timeout in seconds for the agent execution

    Returns:
        Parsed JSON output as a dictionary

    Raises:
        AssertionError: If the agent fails or produces invalid output
    """
    result = subprocess.run(
        [sys.executable, "agent.py", question],
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    # Check that agent exited successfully
    assert result.returncode == 0, (
        f"Agent exited with code {result.returncode}\n"
        f"stderr: {result.stderr}"
    )

    # Parse JSON output
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {e}\nstdout: {result.stdout}")

    return output


def test_merge_conflict_question():
    """Test that the agent uses read_file to answer about merge conflicts.

    Question: "How do you resolve a merge conflict?"
    Expected:
        - read_file in tool_calls
        - wiki/git.md or wiki/git-vscode.md in source (where merge conflict info is)
    """
    question = "How do you resolve a merge conflict?"

    output = run_agent(question)

    # Check that output has required fields
    assert "answer" in output, "Missing 'answer' field in output"
    assert "source" in output, "Missing 'source' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Check that read_file was used
    tools_used = {tc.get("tool") for tc in output["tool_calls"]}
    assert "read_file" in tools_used, (
        f"Expected 'read_file' in tool_calls, got: {tools_used}"
    )

    # Check that source references git.md or git-vscode.md (where merge conflict info is)
    source = output["source"]
    assert "wiki/git.md" in source or "wiki/git-vscode.md" in source, (
        f"Expected 'wiki/git.md' or 'wiki/git-vscode.md' in source, got: {source}"
    )

    # Check that answer is non-empty
    assert len(output["answer"]) > 0, "Answer should not be empty"

    print(f"✓ Test passed: answer={output['answer'][:100]}..., source={source}")


def test_wiki_files_question():
    """Test that the agent uses list_files to answer about wiki contents.

    Question: "What files are in the wiki?"
    Expected:
        - list_files in tool_calls
    """
    question = "What files are in the wiki?"

    output = run_agent(question)

    # Check that output has required fields
    assert "answer" in output, "Missing 'answer' field in output"
    assert "source" in output, "Missing 'source' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Check that list_files was used
    tools_used = {tc.get("tool") for tc in output["tool_calls"]}
    assert "list_files" in tools_used, (
        f"Expected 'list_files' in tool_calls, got: {tools_used}"
    )

    # Check that answer is non-empty
    assert len(output["answer"]) > 0, "Answer should not be empty"

    print(f"✓ Test passed: answer={output['answer'][:100]}..., source={output['source']}")


def test_framework_question():
    """Test that the agent uses read_file to answer about the backend framework.

    Question: "What framework does the backend use?"
    Expected:
        - read_file in tool_calls
        - Answer mentions FastAPI or the correct framework
    """
    question = "What framework does the backend use?"

    output = run_agent(question)

    # Check that output has required fields
    assert "answer" in output, "Missing 'answer' field in output"
    assert "source" in output, "Missing 'source' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Check that read_file was used (not query_api for static facts)
    tools_used = {tc.get("tool") for tc in output["tool_calls"]}
    assert "read_file" in tools_used, (
        f"Expected 'read_file' in tool_calls for static fact, got: {tools_used}"
    )

    # Check that answer mentions FastAPI or framework
    answer_lower = output["answer"].lower()
    assert "fastapi" in answer_lower or "framework" in answer_lower, (
        f"Expected answer to mention FastAPI or framework, got: {output['answer']}"
    )

    print(f"✓ Test passed: answer={output['answer'][:100]}..., source={output['source']}")


def test_items_count_question():
    """Test that the agent uses query_api to answer about item count.

    Question: "How many items are in the database?"
    Expected:
        - query_api in tool_calls
        - Answer contains a number
    """
    question = "How many items are in the database?"

    output = run_agent(question)

    # Check that output has required fields
    assert "answer" in output, "Missing 'answer' field in output"
    assert "source" in output, "Missing 'source' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Check that query_api was used (for live data)
    tools_used = {tc.get("tool") for tc in output["tool_calls"]}
    assert "query_api" in tools_used, (
        f"Expected 'query_api' in tool_calls for data query, got: {tools_used}"
    )

    # Check that answer contains a number
    import re
    numbers = re.findall(r"\d+", output["answer"])
    assert len(numbers) > 0, (
        f"Expected answer to contain a number, got: {output['answer']}"
    )

    print(f"✓ Test passed: answer={output['answer'][:100]}..., source={output['source']}")


if __name__ == "__main__":
    # Run tests when executed directly
    import pytest
    pytest.main([__file__, "-v"])
