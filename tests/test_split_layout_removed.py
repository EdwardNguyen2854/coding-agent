"""Tests asserting that the split-pane layout has been fully removed."""

import importlib
import inspect


def test_split_layout_not_importable():
    """split_layout module must not exist."""
    import importlib.util
    spec = importlib.util.find_spec("coding_agent.split_layout")
    assert spec is None, "coding_agent.split_layout should not be importable"


def test_renderer_takes_no_args():
    """Renderer() constructor must accept zero arguments."""
    from coding_agent.renderer import Renderer
    sig = inspect.signature(Renderer.__init__)
    # Only 'self' parameter
    params = [p for p in sig.parameters if p != "self"]
    assert params == [], f"Renderer.__init__ should take no args, got: {params}"


def test_no_captured_streaming_display_in_renderer():
    """CapturedStreamingDisplay must not be present in the renderer module."""
    import coding_agent.renderer as renderer_mod
    assert not hasattr(renderer_mod, "CapturedStreamingDisplay"), (
        "CapturedStreamingDisplay should have been removed from renderer"
    )


def test_no_make_sidebar_vertical_in_sidebar():
    """make_sidebar_vertical must not be present in the sidebar module."""
    import coding_agent.sidebar as sidebar_mod
    assert not hasattr(sidebar_mod, "make_sidebar_vertical"), (
        "make_sidebar_vertical should have been removed from sidebar"
    )


def test_no_set_output_file_in_permissions():
    """PermissionSystem.set_output_file must not exist."""
    from coding_agent.permissions import PermissionSystem
    assert not hasattr(PermissionSystem, "set_output_file"), (
        "set_output_file should have been removed from PermissionSystem"
    )
