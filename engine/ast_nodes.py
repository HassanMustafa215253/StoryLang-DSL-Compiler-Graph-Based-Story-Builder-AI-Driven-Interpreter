"""
AST (Abstract Syntax Tree) node definitions for StoryLang.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Union


@dataclass
class DescriptionNode:
    text: str
    line: int = 0


@dataclass
class ChoiceNode:
    label: str
    target: str      # scene name to transition to
    condition: Optional[str] = None   # variable that must be set
    line: int = 0


@dataclass
class IfNode:
    condition: "ConditionNode"
    then_target: Optional[str] = None
    then_block: List["Statement"] = field(default_factory=list)
    else_target: Optional[str] = None
    else_block: List["Statement"] = field(default_factory=list)
    line: int = 0


@dataclass
class SetNode:
    action: str
    variable: str
    value: Union[str, int, bool, None] = None
    delta: int = 0
    line: int = 0


@dataclass
class ConditionNode:
    kind: str
    variable: Optional[str] = None
    operator: Optional[str] = None
    value: Union[str, int, None] = None
    line: int = 0


@dataclass
class AIGenerateSceneNode:
    prompt: str
    line: int = 0


@dataclass
class AIGenerateOptionsNode:
    prompt: str
    line: int = 0


# Union of all statement types inside a scene
Statement = Union[
    DescriptionNode,
    ChoiceNode,
    IfNode,
    SetNode,
    AIGenerateSceneNode,
    AIGenerateOptionsNode,
]


@dataclass
class SceneNode:
    name: str
    statements: List[Statement] = field(default_factory=list)
    line: int = 0


@dataclass
class ProgramNode:
    scenes: List[SceneNode] = field(default_factory=list)