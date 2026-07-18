def test_agent_speak_package_is_importable() -> None:
    import agent_speak

    assert agent_speak.__version__ == "0.1.0"
