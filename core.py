from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Self
from dataclasses import dataclass, replace
import re


class Parser(ABC):
    @abstractmethod
    def parse_with_context(self, cxt: ParsingContext) -> ParsingContext:
        pass

    def parse(self, input: str) -> ParsingContext:
        ctx = ParsingContext(input=input, position=0)
        return self.parse_with_context(ctx)

    def map(self, fn) -> Self:
        def router(result):
            return pure(fn(result))

        return ForwardingParser(self, router)

    def map_err(self, fn) -> Self:
        return ErrorMappingParser(self, fn)

    def many(self) -> Self:
        return KleeneParser(self, 0)

    def between(self, left, right):
        return (left & self & right).map(lambda xs: xs[1])

    def at_least(self, min):
        return KleeneParser(self, min)

    def forward(self, router):
        return ForwardingParser(self, router)

    def separated_by(self, sep):
        return SeparatorParser(self, sep)

    def __and__(self, other: Self) -> Self:
        return SequentialParser([self, other])

    def __or__(self, other: Self) -> Self:
        return AlternatingParser([self, other])


@dataclass
class ParsingContext:
    input: str
    position: int
    result: any = None
    failed: bool = False
    error: str = ""

    def succeed(self, position: int, result: any) -> Self:
        return ParsingContext(input=self.input, position=position, result=result)

    def update_result(self, result: any) -> Self:
        return ParsingContext(input=self.input, position=self.position, result=result)

    def fail(self, error: str) -> Self:
        return ParsingContext(
            input=self.input, position=self.position, error=error, failed=True
        )


class PureParser(Parser):
    def __init__(self, result):
        self.result = result

    def parse_with_context(self, ctx: ParsingContext) -> ParsingContext:
        return ctx.update_result(self.result)


class LazyParser(Parser):
    def __init__(self, thunk):
        self.thunk = thunk

    def parse_with_context(self, ctx: ParsingContext) -> ParsingContext:
        parser = self.thunk()
        return parser.parse_with_context(ctx)


class StringParser(Parser):
    def __init__(self, string: str):
        self.string = string

    def parse_with_context(self, ctx: ParsingContext) -> ParsingContext:
        if ctx.failed:
            return ctx

        input = ctx.input[ctx.position :]

        if len(input) == 0:
            return ctx.fail(f"Tried to match '{self.string}', but got EOF")

        if input.startswith(self.string):
            return ctx.succeed(ctx.position + len(self.string), self.string)
        return ctx.fail(f"tried to match '{self.string}', found '{input}'")

    def __str__(self):
        return f"StringParser({self.string})"


class RegexParser(Parser):
    def __init__(self, pattern: str):
        self.pattern = pattern
        self.regex = re.compile(pattern)

    def parse_with_context(self, ctx: ParsingContext) -> ParsingContext:
        input = ctx.input[ctx.position :]
        match = self.regex.match(input)
        if match == None:
            return ctx.fail("Regex didn't match")
        result = match.group()
        return ctx.succeed(ctx.position + len(result), result)

    def __str__(self):
        return f"RegexParser(/{self.pattern}/)"


class SequentialParser(Parser):
    def __init__(self, parsers: list[Parser]):
        self.parsers = parsers

    def parse_with_context(self, ctx: ParsingContext) -> ParsingContext:
        results = []
        for parser in self.parsers:
            ctx = parser.parse_with_context(ctx)
            results += [ctx.result]
            if ctx.failed:
                return ctx
        return ctx.update_result(results)

    def __and__(self, other: Self) -> Self:
        return SequentialParser(self.parsers + [other])

    def __str__(self):
        return f"({' & '.join([str(parser) for parser in self.parsers])})"


class AlternatingParser(Parser):
    def __init__(self, parsers: list[Parser]):
        self.parsers = parsers

    def parse_with_context(self, ctx: ParsingContext) -> ParsingContext:
        for parser in self.parsers:
            next_ctx = parser.parse_with_context(ctx)
            if not next_ctx.failed:
                return next_ctx
        return ctx.fail(f"No alternative matched")

    def __or__(self, other: Self) -> Self:
        return AlternatingParser(self.parsers + [other])

    def __str__(self):
        return f"({' | '.join([str(parser) for parser in self.parsers])})"


class ErrorMappingParser(Parser):
    def __init__(self, parser, transform):
        self.parser = parser
        self.transform = transform

    def parse_with_context(self, ctx: ParsingContext) -> ParsingContext:
        ctx = self.parser.parse_with_context(ctx)
        if ctx.failed:
            return ctx.fail(self.transform(ctx.error, ctx.position))
        return ctx

    def __str__(self):
        return str(self.parser)


class KleeneParser(Parser):
    def __init__(self, parser, min=0):
        self.parser = parser
        self.min = min

    def parse_with_context(self, ctx: ParsingContext) -> ParsingContext:
        match_count = 0
        results = []
        while True:
            local_ctx = self.parser.parse_with_context(ctx)
            if local_ctx.failed:
                break
            ctx = local_ctx
            match_count += 1
            results += [ctx.result]
        if match_count < self.min:
            return ctx.fail(
                f"expected to match at least {self.min}x but matched {match_count}x"
            )
        return ctx.update_result(results)

    def __str__(self):
        return f"{str(self.parser)}[{self.min}]"


class ForwardingParser(Parser):
    def __init__(self, parser, router):
        self.parser = parser
        self.router = router

    def parse_with_context(self, ctx: ParsingContext) -> ParsingContext:
        ctx = self.parser.parse_with_context(ctx)
        if ctx.failed:
            return ctx

        next_parser = self.router(ctx.result)
        return next_parser.parse_with_context(ctx)


class SeparatorParser(Parser):
    def __init__(self, value: Parser, separator: Parser):
        self.value = value
        self.separator = separator

    def parse_with_context(self, ctx: ParsingContext) -> ParsingContext:
        results = []
        next_ctx = ctx
        while True:
            value_ctx = self.value.parse_with_context(next_ctx)
            if value_ctx.failed:
                break
            results += [value_ctx.result]
            next_ctx = value_ctx

            separator_ctx = self.separator.parse_with_context(next_ctx)
            if separator_ctx.failed:
                break
            next_ctx = separator_ctx

        return next_ctx.update_result(results)


def pure(r):
    return PureParser(r)


def string(s: string):
    return StringParser(s)


def regex(s: string):
    return RegexParser(s)


def letters():
    return RegexParser(r"^[a-zA-Z]+").map_err(lambda _err, _p: "Couldn't match letters")


def digits():
    return RegexParser(r"^[0-9]+").map_err(lambda _err, _p: "Couldn't match digits")


def whitespace():
    return RegexParser(r"\s*")


def lazy(thunk):
    return LazyParser(thunk)
