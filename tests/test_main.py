from agent.__main__ import _parse_args


def test_serve_listens_on_localhost_by_default():
    args = _parse_args(["serve"])

    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.config is None


def test_serve_takes_host_port_and_config():
    args = _parse_args(["serve", "--host", "0.0.0.0", "--port", "9000", "--config", "a.toml"])

    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.config == "a.toml"


def test_config_before_the_command_is_kept():
    assert _parse_args(["--config", "a.toml", "serve"]).config == "a.toml"


def test_in_process_chat_takes_config():
    args = _parse_args(["--config", "a.toml"])

    assert args.command is None
    assert args.config == "a.toml"
