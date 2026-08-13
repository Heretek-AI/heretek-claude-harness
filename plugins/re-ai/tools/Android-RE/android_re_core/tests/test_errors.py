"""Tests for the :mod:`android_re_core.errors` hierarchy."""

from __future__ import annotations

from android_re_core import errors


def test_root_error_to_dict():
    """AndroidReError.to_dict serializes all required fields."""
    e = errors.AndroidReError("boom", details={"k": "v"})
    d = e.to_dict()
    assert d["error"] == "android_re_error"
    assert d["message"] == "boom"
    assert d["details"] == {"k": "v"}


def test_hierarchy_codes():
    """Each error subclass has a distinct, namespaced code."""
    codes = {
        errors.AndroidReError: "android_re_error",
        errors.APKError: "apk_error",
        errors.APKTooLarge: "apk_too_large",
        errors.APKZipBomb: "apk_zip_bomb",
        errors.APKNotFound: "apk_not_found",
        errors.APKInvalid: "apk_invalid",
        errors.APKAlreadyOpen: "apk_already_open",
        errors.ProjectError: "project_error",
        errors.ProjectNotFound: "project_not_found",
        errors.ProjectClosed: "project_closed",
        errors.ToolError: "tool_error",
        errors.ToolNotFound: "tool_not_found",
        errors.ToolTimeout: "tool_timeout",
        errors.ToolFailed: "tool_failed",
        errors.DeviceError: "device_error",
        errors.FridaError: "frida_error",
    }
    for cls, expected in codes.items():
        assert cls.code == expected, f"{cls.__name__}.code should be {expected!r}, got {cls.code!r}"


def test_subclass_relationship():
    """All errors derive from AndroidReError so callers can except broadly."""
    for cls in (
        errors.APKError,
        errors.ProjectError,
        errors.ToolError,
        errors.DeviceError,
        errors.FridaError,
    ):
        assert issubclass(cls, errors.AndroidReError)


def test_specific_subclasses():
    """The leaf errors are correctly nested."""
    for cls in (
        errors.APKTooLarge,
        errors.APKZipBomb,
        errors.APKNotFound,
        errors.APKInvalid,
        errors.APKAlreadyOpen,
    ):
        assert issubclass(cls, errors.APKError)
    for cls in (errors.ProjectNotFound, errors.ProjectClosed):
        assert issubclass(cls, errors.ProjectError)
    for cls in (errors.ToolNotFound, errors.ToolTimeout, errors.ToolFailed):
        assert issubclass(cls, errors.ToolError)


def test_error_details_default_is_empty_dict():
    """If no details are passed, the details field is an empty dict, not None."""
    e = errors.AndroidReError("x")
    assert e.details == {}


def test_error_message_preserved():
    """The exception's str() and .message agree."""
    e = errors.APKTooLarge("too big", details={"size": 1000, "max": 500})
    assert "too big" in str(e)
    assert e.message == "too big"
