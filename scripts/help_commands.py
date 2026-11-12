"""Command checks for operator help pages (H4): quoted commands must exist in the supplied tools.

Reads each tool's argparse calls from its source with `ast`; never imports or runs a tool.
Standard library only.
"""

from __future__ import annotations

import ast
import re
import shlex
from pathlib import Path

SCRIPTS_DIRECTORY = "scripts"
CLI_FILE = "backend/labadda/cli.py"
SHELL_BREAKS = {"|", "||", "&&", ";", ">", ">>", "2>&1"}
VALUELESS_ACTIONS = {"store_true", "store_false"}
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`[^`]*`")


class Tool:
    """The command line a script accepts, read from its argparse calls."""

    def __init__(self) -> None:
        self.options: dict[str, bool] = {"--help": False, "-h": False}  # option -> takes a value
        self.commands: dict[str, dict[str, bool]] = {}
        self.choices: set[str] = set()


def _text(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _names(node: ast.AST | None, loops: dict[str, list[str]]) -> list[str]:
    if isinstance(node, ast.Name):
        return loops.get(node.id, [])
    value = _text(node)
    return [value] if value else []


def _collect(node: ast.AST, loops: dict[str, list[str]], events: list) -> None:
    """Append (node, loop values) for every assignment and call, in source order."""
    if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
        values = [_text(item) for item in getattr(node.iter, "elts", [])]
        loops = {**loops, node.target.id: [v for v in values if v]}
    if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)) or isinstance(node, ast.Call):
        events.append((node, loops))
    for child in ast.iter_child_nodes(node):
        _collect(child, loops, events)


def _define_parser(tool: Tool, owners: dict[str, list[str]], assign: ast.Assign, loops: dict) -> None:
    call, target = assign.value, assign.targets[0]
    if not isinstance(target, ast.Name) or not isinstance(call, ast.Call):
        return
    if isinstance(call.func, ast.Attribute) and call.func.attr == "add_parser" and call.args:
        owners[target.id] = _names(call.args[0], loops)
        for name in owners[target.id]:
            tool.commands.setdefault(name, {})
    elif getattr(call.func, "attr", "") == "ArgumentParser":
        owners[target.id] = []


def _add_argument(tool: Tool, owners: dict[str, list[str]], call: ast.Call) -> None:
    owner = owners.get(getattr(call.func.value, "id", ""), [])
    flags = [flag for flag in map(_text, call.args) if flag and flag.startswith("-")]
    action = next((_text(k.value) for k in call.keywords if k.arg == "action"), None)
    for flag in flags:
        for scope in [tool.options] if not owner else [tool.commands[name] for name in owner]:
            scope[flag] = action not in VALUELESS_ACTIONS
    for keyword in call.keywords:
        if keyword.arg == "choices" and not flags and isinstance(keyword.value, ast.Tuple):
            tool.choices |= {v for v in map(_text, keyword.value.elts) if v}


def parse_tool(source: str) -> Tool:
    """Return the subcommands, choices and options a script's argparse code defines."""
    tool = Tool()
    events: list[tuple[ast.AST, dict[str, list[str]]]] = []
    _collect(ast.parse(source), {}, events)
    owners: dict[str, list[str]] = {}  # parser variable -> subcommand names it defines ([] = the root)
    for node, loops in events:
        if isinstance(node, ast.Assign):
            _define_parser(tool, owners, node, loops)
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            _add_argument(tool, owners, node)
    return tool


def operator_tools(root: Path) -> dict[str, Tool]:
    """Return the tool for each `scripts/<name>.py` and for `labadda`, keyed by command name."""
    tools = {}
    for path in sorted((root / SCRIPTS_DIRECTORY).glob("*.py")):
        tools[path.name] = parse_tool(path.read_text(encoding="utf-8"))
    cli = root / CLI_FILE
    if cli.is_file():
        tools["labadda"] = parse_tool(cli.read_text(encoding="utf-8"))
    return tools


def split_command(line: str) -> list[str]:
    """Return the words of a shell line up to the first pipe, redirect or comment."""
    lexer = shlex.shlex(line, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = "#"
    try:
        words = list(lexer)
    except ValueError:
        return []
    for index, word in enumerate(words):
        if word in SHELL_BREAKS:
            return words[:index]
    return words


def program_at(words: list[str]) -> tuple[int, str] | None:
    """Return (index of the first argument, tool name) when the words run one of the tools."""
    for index, word in enumerate(words):
        if word.endswith(".py") and "/" in word and word.split("/")[-2] == SCRIPTS_DIRECTORY:
            return index + 1, word.rsplit("/", 1)[-1]
        if word == "labadda" or (word == "labadda.cli" and index and words[index - 1] == "-m"):
            return index + 1, "labadda"
    return None


def check_command(name: str, number: int, words: list[str], tools: dict[str, Tool]) -> list[str]:
    """Return a problem for each unknown script, subcommand or option in one quoted command."""
    found = program_at(words)
    if found is None:
        return []
    start, script = found
    tool = tools.get(script)
    if tool is None:
        return [f"{name}:{number}: the command runs '{script}', which is not one of the supplied tools"]
    problems = []
    subcommands = set(tool.commands) | tool.choices
    chosen = None
    skip = False
    for argument in words[start:]:
        if skip:
            skip = False
        elif argument.startswith("-"):
            option = argument.split("=", 1)[0]
            scope = {**tool.options, **tool.commands.get(chosen or "", {})}
            if option not in scope:
                problems.append(f"{name}:{number}: '{script}' has no option {option}")
            skip = scope.get(option, False) and "=" not in argument
        elif chosen is None and subcommands:
            chosen = argument
            if argument not in subcommands:
                problems.append(f"{name}:{number}: '{script}' has no command '{argument}'")
    if subcommands and chosen is None:
        problems.append(f"{name}:{number}: '{script}' needs one of: {', '.join(sorted(subcommands))}")
    return problems


def command_lines(body: str, body_start: int) -> list[tuple[int, str]]:
    """Return (line number, command) for each fenced line (continuations joined) and code span."""
    found = []
    pending: tuple[int, str] | None = None
    inside_fence = False
    for number, line in enumerate(body.splitlines(), start=body_start):
        if FENCE.match(line):
            inside_fence = not inside_fence
        elif inside_fence:
            text = line.strip()
            start, joined = pending if pending else (number, "")
            pending = (start, joined + text[:-1] + " ") if text.endswith("\\") else None
            if pending is None:
                found.append((start, (joined + text).strip()))
        else:
            found += [(number, span[1:-1]) for span in INLINE_CODE.findall(line)]
    return found


def check_commands(page: Path, root: Path, body: str, body_start: int, tools: dict[str, Tool]) -> list[str]:
    """Return a problem for each quoted command or option that the supplied tools do not have (H4)."""
    name = str(page.relative_to(root))
    every_option = {option for tool in tools.values() for option in tool.options}
    for tool in tools.values():
        every_option |= {option for options in tool.commands.values() for option in options}
    problems = []
    for number, text in command_lines(body, body_start):
        if re.fullmatch(r"--[a-z][a-z-]*(=\S*)?", text):
            if text.split("=")[0] not in every_option:
                problems.append(f"{name}:{number}: no supplied tool has the option {text}")
        else:
            problems += check_command(name, number, split_command(text), tools)
    return problems
