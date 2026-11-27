# Skill 加载与注册：解析 SKILL.md 的 YAML 元数据和正文，管理资源文件与工具权限。

"""Agent Skill packages backed by ``SKILL.md``.

Skills are prompt-time capabilities, not executable Python reviewers. Discovery
loads only name/description metadata; bodies and resources are exposed after a
Lead selects a skill for a worker.
"""
import hashlib
import os
import re
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Tuple

import yaml

from .reviewer import Reviewer


SKILL_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
MAX_SKILL_MD_BYTES = 128 * 1024
MAX_RESOURCE_BYTES = 1024 * 1024
MAX_RESOURCES = 100


# 规范化 Skill 资源路径并拒绝空段、点目录和上级目录引用。
def _safe_relative_path(value: str) -> str:
    value = str(value).replace("\\", "/").strip("/")
    if not value or value == "SKILL.md":
        raise ValueError("invalid skill resource path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("skill resource path escapes its package: %s" % value)
    return value


# 检查大小与 frontmatter 边界，用 YAML 安全加载器解析元数据并提取非空正文。
def _split_skill_markdown(content: str) -> Tuple[dict, str]:
    if len(content.encode("utf-8")) > MAX_SKILL_MD_BYTES:
        raise ValueError("SKILL.md exceeds %d bytes" % MAX_SKILL_MD_BYTES)
    normalized = content.replace("\r\n", "\n").lstrip("\ufeff")
    lines = normalized.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with YAML frontmatter")
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as exc:
        raise ValueError("SKILL.md frontmatter is not terminated") from exc
    try:
        # 只将 YAML 当数据解析，禁止通过自定义对象标签构造可执行 Python 对象。
        frontmatter = yaml.safe_load("\n".join(lines[1:end])) or {}
    except yaml.YAMLError as exc:
        raise ValueError("SKILL.md contains invalid YAML frontmatter") from exc
    if not isinstance(frontmatter, dict):
        raise ValueError("SKILL.md frontmatter must be an object")
    body = "\n".join(lines[end + 1:]).strip()
    if not body:
        raise ValueError("SKILL.md instructions must not be empty")
    return frontmatter, body


# 标准 Skill 包的不可变视图，包含正文、资源和工具权限。
@dataclass(frozen=True)
class AgentSkill:
    name: str
    description: str
    instructions: str
    content: str
    source: str = "disk"
    version: str = "1"
    directory: str = ""
    resource_paths: Tuple[str, ...] = ()
    resource_contents: Mapping[str, str] = field(default_factory=dict, repr=False)
    allowed_tools: Tuple[str, ...] = ()
    content_sha256: str = ""

    # 验证 Skill 名称、描述、权限及资源，并对规范化内容计算指纹。
    @classmethod
    def from_markdown(
        cls, content: str, source: str = "memory", version: str = "1",
        directory: str = "", resources: Optional[Mapping[str, str]] = None,
        expected_name: str = "",
    ) -> "AgentSkill":
        frontmatter, body = _split_skill_markdown(content)
        name = str(frontmatter.get("name", expected_name)).strip().lower()
        description = str(frontmatter.get("description", "")).strip()
        if expected_name and name != expected_name:
            raise ValueError("SKILL.md name must match its package directory")
        if not SKILL_NAME.fullmatch(name):
            raise ValueError("skill name must use lowercase letters, digits and hyphens")
        if not description or len(description) > 1536:
            raise ValueError("skill description must contain 1 to 1536 characters")
        raw_tools = frontmatter.get("allowed-tools", [])
        if isinstance(raw_tools, str):
            raw_tools = raw_tools.split()
        if not isinstance(raw_tools, list) or not all(isinstance(item, str) for item in raw_tools):
            raise ValueError("allowed-tools must be a string or an array of strings")
        resource_contents = {}
        for raw_path, value in dict(resources or {}).items():
            path = _safe_relative_path(raw_path)
            if not isinstance(value, str):
                raise ValueError("versioned skill resources must be UTF-8 text")
            if len(value.encode("utf-8")) > MAX_RESOURCE_BYTES:
                raise ValueError("skill resource exceeds size limit: %s" % path)
            resource_contents[path] = value
        if len(resource_contents) > MAX_RESOURCES:
            raise ValueError("skill package contains too many resources")
        normalized = content.replace("\r\n", "\n").lstrip("\ufeff").strip() + "\n"
        # 正文和资源都参与指纹；资源内容变化同样应被视为不同 Skill 版本。
        digest_parts = [normalized]
        for path in sorted(resource_contents):
            digest_parts.extend([path, "\0", resource_contents[path]])
        digest = hashlib.sha256("\0".join(digest_parts).encode("utf-8")).hexdigest()
        return cls(
            name=name, description=description, instructions=body, content=normalized,
            source=source, version=str(version), directory=os.path.abspath(directory) if directory else "",
            resource_paths=tuple(sorted(resource_contents)), resource_contents=resource_contents,
            allowed_tools=tuple(dict.fromkeys(raw_tools)), content_sha256=digest,
        )

    # 从磁盘 Skill 包读取正文和文本资源，拒绝符号链接并检查大小限制。
    @classmethod
    def from_directory(cls, directory: str) -> "AgentSkill":
        directory = os.path.abspath(directory)
        skill_path = os.path.join(directory, "SKILL.md")
        if os.path.islink(skill_path):
            raise ValueError("SKILL.md symlinks are not allowed")
        with open(skill_path, "r", encoding="utf-8") as handle:
            content = handle.read()
        resources: Dict[str, str] = {}
        for root, directories, files in os.walk(directory, followlinks=False):
            directories[:] = [item for item in directories if not os.path.islink(os.path.join(root, item))]
            for filename in files:
                path = os.path.join(root, filename)
                relative = os.path.relpath(path, directory).replace("\\", "/")
                if relative == "SKILL.md":
                    continue
                if os.path.islink(path):
                    raise ValueError("skill resource symlinks are not allowed: %s" % relative)
                if os.path.getsize(path) > MAX_RESOURCE_BYTES:
                    raise ValueError("skill resource exceeds size limit: %s" % relative)
                try:
                    with open(path, "r", encoding="utf-8") as handle:
                        resources[relative] = handle.read()
                except UnicodeDecodeError:
                    continue
        return cls.from_markdown(
            content, source="disk", directory=directory, resources=resources,
            expected_name=os.path.basename(directory).lower(),
        )

    # 从数据库制品中的 SKILL.md 和资源文件恢复可运行的 Skill。
    @classmethod
    def from_artifact(cls, artifact: dict, version: str = "1") -> "AgentSkill":
        if not isinstance(artifact, dict):
            raise ValueError("agent skill artifact must be an object")
        files = artifact.get("files") or {}
        if not isinstance(files, dict) or not isinstance(files.get("SKILL.md"), str):
            raise ValueError("agent skill artifact must contain files.SKILL.md")
        expected = str(artifact.get("name", "")).strip().lower()
        resources = {key: value for key, value in files.items() if key != "SKILL.md"}
        return cls.from_markdown(
            files["SKILL.md"], source="evolved-db", version=version,
            resources=resources, expected_name=expected,
        )

    # 仅提供名称与描述，Lead 选择后再加载完整指导内容。
    def catalog_entry(self) -> dict:
        return {"name": self.name, "description": self.description}

    # 提供 Worker 所需的 Skill 正文与资源目录，供按需使用。
    def runtime_entry(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "instructions": self.instructions, "resources": list(self.resource_paths),
        }

    # 确认资源在当前 Skill 中声明且路径有效，再读取受大小限制的文本。
    def read_resource(self, path: str) -> str:
        path = _safe_relative_path(path)
        if path not in self.resource_paths:
            raise FileNotFoundError("skill resource not found: %s/%s" % (self.name, path))
        if path in self.resource_contents:
            return self.resource_contents[path]
        absolute = os.path.abspath(os.path.join(self.directory, *path.split("/")))
        if not absolute.startswith(self.directory + os.sep):
            raise PermissionError("skill resource path escapes its package")
        with open(absolute, "r", encoding="utf-8") as handle:
            value = handle.read(MAX_RESOURCE_BYTES + 1)
        if len(value.encode("utf-8")) > MAX_RESOURCE_BYTES:
            raise ValueError("skill resource exceeds size limit: %s" % path)
        return value

    # 将 Skill 正文与全部资源打包成可持久化的版本制品。
    def to_artifact(self) -> dict:
        files = {"SKILL.md": self.content}
        for path in self.resource_paths:
            files[path] = self.read_resource(path)
        return {
            "schema_version": 2, "format": "agent-skill", "name": self.name,
            "description": self.description, "files": files,
            "content_sha256": self.content_sha256,
        }


# 扫描器注册元数据，供管理界面展示版本和权限信息。
@dataclass
class SkillInfo:
    name: str
    version: str
    description: str
    source: str
    sandboxed: bool = False
    permissions: tuple = ()
    kind: str = "scanner"


# 同时管理扫描器注册项与磁盘加载的 Agent Skill。
class SkillRegistry:
    """Registry for deterministic scanners and filesystem Agent Skills."""

    # 设置 Skill 根目录，初始化扫描器、注册元信息和 Agent Skill 容器，并创建重入锁。
    def __init__(self, skills_dir: str, *_legacy_args, **_legacy_kwargs):
        self.skills_dir = os.path.abspath(skills_dir)
        self._skills: Dict[str, Reviewer] = {}
        self._info: Dict[str, SkillInfo] = {}
        self._agent_skills: Dict[str, AgentSkill] = {}
        self._lock = threading.RLock()

    # 注册命名扫描器及版本描述，供后续扫描和管理列表使用。
    def register(
        self, name: str, reviewer: Reviewer, version: str = "1.0.0",
        description: str = "", source: str = "builtin", sandboxed: bool = False,
        permissions: tuple = (),
    ) -> None:
        if not name.replace("-", "_").isidentifier():
            raise ValueError("invalid scanner name: %s" % name)
        with self._lock:
            self._skills[name] = reviewer
            self._info[name] = SkillInfo(
                name, version, description, source, sandboxed, permissions, "scanner"
            )

    # 返回已注册的规则审查器，供扫描阶段调用。
    def reviewers(self) -> List[Reviewer]:
        with self._lock:
            return list(self._skills.values())

    # 返回已加载的 Agent Skill 集合，供 Lead 选择分派。
    def agent_skills(self) -> List[AgentSkill]:
        with self._lock:
            return list(self._agent_skills.values())

    # 按名称查找一个已加载的 Agent Skill。
    def get_agent_skill(self, name: str) -> Optional[AgentSkill]:
        with self._lock:
            return self._agent_skills.get(name)

    # 输出可供 Lead 选择的 Agent Skill 简要目录。
    def catalog(self) -> List[dict]:
        with self._lock:
            return [self._agent_skills[name].catalog_entry() for name in sorted(self._agent_skills)]

    # 移除指定名称的注册项，使后续列表与运行不再使用它。
    def unregister(self, name: str) -> None:
        with self._lock:
            self._skills.pop(name, None)
            self._info.pop(name, None)

    # 汇总扫描器与 Skill 的元数据，提供管理台所需的统一列表。
    def list(self) -> List[dict]:
        with self._lock:
            values = []
            for item in self._info.values():
                value = vars(item).copy()
                value["permissions"] = list(value["permissions"])
                values.append(value)
            values.extend({
                "name": skill.name, "version": skill.version,
                "description": skill.description, "source": skill.source,
                "sandboxed": False, "permissions": list(skill.allowed_tools),
                "kind": "agent-skill", "content_sha256": skill.content_sha256,
                "resources": list(skill.resource_paths),
            } for skill in self._agent_skills.values())
            return values

    # 重新扫描 Skill 目录，加载有效包并收集加载错误。
    def reload(self) -> List[dict]:
        os.makedirs(self.skills_dir, exist_ok=True)
        discovered: Dict[str, AgentSkill] = {}
        for entry in os.scandir(self.skills_dir):
            if not entry.is_dir(follow_symlinks=False):
                continue
            skill_path = os.path.join(entry.path, "SKILL.md")
            if not os.path.isfile(skill_path):
                continue
            skill = AgentSkill.from_directory(entry.path)
            if skill.name in discovered:
                raise ValueError("duplicate Agent Skill name: %s" % skill.name)
            discovered[skill.name] = skill
        with self._lock:
            self._agent_skills = discovered
        return self.list()
