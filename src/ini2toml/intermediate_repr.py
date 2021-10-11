"""Intermediate representations used by ``ini2toml`` when transforming between
the INI and TOML syntaxes.
"""
from collections import UserList
from dataclasses import dataclass, field
from enum import Enum
from itertools import chain
from pprint import pformat
from textwrap import indent
from types import MappingProxyType
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    cast,
)
from uuid import uuid4

T = TypeVar("T")
S = TypeVar("S")
R = TypeVar("R", bound="IntermediateRepr")

KV = Tuple[str, T]

NotGiven = Enum("NotGiven", "NOT_GIVEN")
NOT_GIVEN = NotGiven.NOT_GIVEN

EMPTY: Mapping = MappingProxyType({})


@dataclass(frozen=True)
class HiddenKey:
    _value: int = field(default_factory=lambda: uuid4().int)

    def __str__(self):
        return f"{self.__class__.__name__}()"

    __repr__ = __str__


class WhitespaceKey(HiddenKey):
    pass


class CommentKey(HiddenKey):
    pass


Key = Union[str, HiddenKey, Tuple[Union[str, HiddenKey], ...]]


class IntermediateRepr(MutableMapping):
    def __init__(
        self,
        elements: Mapping[Key, Any] = EMPTY,
        order: Sequence[Key] = (),
        inline_comment: str = "",
        **kwargs,
    ):
        el = chain(elements.items(), kwargs.items())
        self.elements: Dict[Key, Any] = {}
        self.order: List[Key] = []
        self.inline_comment = inline_comment
        self.elements.update(el)
        self.order.extend(order or self.elements.keys())
        elem_not_in_order = any(k not in self.order for k in self.elements)
        order_not_in_elem = any(k not in self.elements for k in self.order)
        if elem_not_in_order or order_not_in_elem:
            raise ValueError(f"{order} and {elements} need to have the same keys")

    def __repr__(self):
        inner = ",\n".join(
            indent(f"{k}={pformat(getattr(self, k))}", "    ")
            for k in ("elements", "order", "inline_comment")
        )
        return f"{self.__class__.__name__}(\n{inner}\n)"

    def __eq__(self, other):
        L = len(self)
        if not (
            isinstance(other, self.__class__)
            and self.inline_comment == other.inline_comment
            and len(other) == L
        ):
            return False
        self_ = [(str(k), v) for k, v in self.items()]
        other_ = [(str(k), v) for k, v in other.items()]
        return all(self_[i] == other_[i] for i in range(L))

    def rename(self, old_key: Key, new_key: Key, ignore_missing=False):
        if old_key == new_key:
            return self
        if new_key in self.order:
            raise ValueError(f"{new_key=} already exists")
        if old_key not in self.order and ignore_missing:
            return self
        i = self.order.index(old_key)
        self.order[i] = new_key
        self.elements[new_key] = self.elements.pop(old_key)
        return self

    def insert(self, i, key: Key, value: Any):
        if key in self.order:
            raise ValueError(f"{key=} already exists")
        self.order.insert(i, key)
        self.elements[key] = value

    def index(self, key: Key) -> int:
        return self.order.index(key)

    def append(self, key: Key, value: Any):
        self.insert(len(self.order), key, value)

    def copy(self: R) -> R:
        return self.__class__(self.elements.copy(), self.order[:], self.inline_comment)

    def replace_first_remove_others(
        self, existing_keys: Sequence[Key], new_key: Key, value: Any
    ):
        idx = [self.index(k) for k in existing_keys if k in self]
        if not idx:
            i = len(self)
        else:
            i = sorted(idx)[0]
            for key in existing_keys:
                self.pop(key, None)
        self.insert(i, new_key, value)
        return i

    def __getitem__(self, key: Key):
        return self.elements[key]

    def __setitem__(self, key: Key, value: Any):
        if key not in self.elements:
            self.order.append(key)
        self.elements[key] = value

    def __delitem__(self, key: Key):
        del self.elements[key]
        self.order.remove(key)

    def __iter__(self):
        return iter(self.order)

    def __len__(self):
        return len(self.order)


# These objects hold information about the processed values + comments
# in such a way that we can later convert them to TOML while still preserving
# the comments (if we want to).


@dataclass
class Commented(Generic[T]):
    value: Union[T, NotGiven] = field(default_factory=lambda: NOT_GIVEN)
    comment: Optional[str] = field(default_factory=lambda: None)

    def comment_only(self):
        return self.value is NOT_GIVEN

    def has_comment(self):
        return bool(self.comment)

    def value_or(self, fallback: S) -> Union[T, S]:
        return fallback if self.value is NOT_GIVEN else self.value


class CommentedList(Generic[T], UserList):
    def __init__(self, data: List[Commented[List[T]]]):
        super().__init__(data)
        self.comment: Optional[str] = None  # TODO: remove this workaround

    def as_list(self) -> list:
        out = []
        for entry in self:
            values = entry.value_or([])
            for value in values:
                out.append(value)
        return out


class CommentedKV(Generic[T], UserList):
    def __init__(self, data: List[Commented[List[KV[T]]]]):
        super().__init__(data)
        self.comment: Optional[str] = None  # TODO: remove this workaround

    def find(self, key: str) -> Optional[Tuple[int, int]]:
        for i, row in enumerate(self):
            for j, item in enumerate(row.value_or([])):
                if item[0] == key:
                    return (i, j)
        return None

    def as_dict(self) -> dict:
        out = {}
        for entry in self:
            values = (v for v in entry.value_or([cast(KV, ())]) if v)
            for k, v in values:
                out[k] = v
        return out

    def to_ir(self) -> IntermediateRepr:
        """:class:`CommentedKV` are usually intended to represent INI options, while
        class:`IntermediateRepr` are usually intended to represent INI sections.
        Therefore this function allows "promoting" an option-equivalent to a
        section-equivalent representation.
        """
        irepr = IntermediateRepr()
        for row in self:
            for key, value in row.value_or([]):
                irepr[key] = value
            if row.has_comment():
                irepr[key] = Commented(value, row.comment)

        return irepr
